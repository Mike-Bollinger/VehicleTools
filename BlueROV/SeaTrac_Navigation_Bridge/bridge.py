"""Threaded serial acquisition, freshness gating, UDP delivery, and CSV logging."""

from contextlib import ExitStack
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import queue
import socket
import threading
import time

import serial

from navigation import (BoatFix, decode_frame, encode_command, make_gga,
                        parse_gps, parse_ping_response, solve)


@dataclass(frozen=True)
class Config:
    gps_port: str
    usbl_port: str
    gps_baud: int = 4800
    usbl_baud: int = 115200
    gps_stopbits: int = 1
    target_id: int = 2
    udp_host: str = '127.0.0.1'
    udp_port: int = 27000
    log_directory: str = 'logs'
    active_ping: bool = True
    enhanced_ping: bool = True
    ping_interval: float = 2.0
    reply_timeout: float = 10.0
    max_age: float = 3.0
    mounting_yaw: float = 0.0
    lever_forward: float = 0.0
    lever_starboard: float = 0.0
    surface_msl: float = 0.0

    def validate(self):
        if not self.gps_port.strip() or not self.usbl_port.strip():
            raise ValueError('Select both serial ports.')
        if os.path.realpath(self.gps_port) == os.path.realpath(self.usbl_port):
            raise ValueError('GPS and USBL must use different serial devices.')
        for baud in (self.gps_baud, self.usbl_baud):
            if not isinstance(baud, int) or not 1200 <= baud <= 4000000:
                raise ValueError('Baud rates must be integers between 1200 and 4000000.')
        if self.gps_stopbits not in (1, 2):
            raise ValueError('GPS stop bits must be 1 or 2.')
        if not isinstance(self.target_id, int) or not 1 <= self.target_id <= 100:
            raise ValueError('ROV beacon ID must be between 1 and 100.')
        if not isinstance(self.udp_port, int) or not 1 <= self.udp_port <= 65535:
            raise ValueError('UDP port must be between 1 and 65535.')
        try:
            ipaddress.IPv4Address(self.udp_host)
        except ipaddress.AddressValueError as error:
            raise ValueError('UDP destination must be a numeric IPv4 address.') from error
        for name in ('ping_interval', 'reply_timeout', 'max_age', 'mounting_yaw',
                     'lever_forward', 'lever_starboard', 'surface_msl'):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f'{name} must be finite.')
        if not 0.5 <= self.ping_interval <= 120:
            raise ValueError('Ping interval must be between 0.5 and 120 seconds.')
        if not 1 <= self.reply_timeout <= 120:
            raise ValueError('Reply timeout must be between 1 and 120 seconds.')
        if not 0.1 <= self.max_age <= 60:
            raise ValueError('Maximum input age must be between 0.1 and 60 seconds.')
        if not self.log_directory.strip():
            raise ValueError('Select a log directory.')


@dataclass(frozen=True)
class InputLine:
    source: str
    text: str
    utc: datetime
    received: float


class NavigationState:
    def __init__(self, config):
        self.config = config
        self.boat = None
        self.heading = None
        self.gps_time = None
        self.heading_time = None
        self.raw_gps = ''
        self.raw_heading = ''
        self.raw_usbl = ''

    def gps(self, text, received):
        sentence = text.split(',', 1)[0]
        try:
            parsed = parse_gps(text)
        except ValueError:
            if sentence.endswith('GGA'):
                self.boat = None
                self.raw_gps = text
            if sentence.endswith('HDT'):
                self.heading = None
                self.raw_heading = text
            raise
        if isinstance(parsed, BoatFix):
            self.boat, self.gps_time, self.raw_gps = parsed, received, text
        elif isinstance(parsed, float):
            self.heading, self.heading_time, self.raw_heading = parsed, received, text

    def readiness(self, now):
        if self.boat is None:
            return 'Waiting for valid GPS GGA'
        if self.heading is None:
            return 'Waiting for valid true heading HDT'
        if not 0 <= now - self.gps_time <= self.config.max_age:
            return 'GPS GGA is stale; UDP output paused'
        if not 0 <= now - self.heading_time <= self.config.max_age:
            return 'True heading HDT is stale; UDP output paused'
        return ''

    def acoustic(self, payload, received, now):
        fix = parse_ping_response(payload, self.config.target_id)
        if fix is None:
            return None, None, 'No accepted ROV position in this message'
        reason = self.readiness(now)
        if reason:
            return None, fix, reason
        if not 0 <= now - received <= self.config.max_age:
            return None, fix, 'Acoustic input queue is stale; fix discarded'
        if self.gps_time > received or self.heading_time > received:
            return None, fix, 'GPS/heading newer than acoustic reception; fix discarded'
        solution = solve(self.boat, self.heading, fix, self.config.mounting_yaw,
                         self.config.lever_forward, self.config.lever_starboard)
        return solution, fix, 'Position accepted'


class LineBuffer:
    def __init__(self):
        self.pending = bytearray()

    def feed(self, chunk):
        self.pending.extend(chunk)
        result = []
        while b'\n' in self.pending:
            end = self.pending.index(b'\n') + 1
            if end > 8192:
                raise ValueError('Serial line exceeds 8192 bytes; check baud/framing.')
            result.append(bytes(self.pending[:end]).decode('ascii', errors='backslashreplace'))
            del self.pending[:end]
        if len(self.pending) > 8192:
            raise ValueError('Unterminated serial line exceeds 8192 bytes.')
        return result


LOG_FIELDS = (
    'timestamp_utc', 'session_start_utc', 'event', 'raw_input', 'raw_gps',
    'raw_heading', 'raw_seatrac', 'boat_latitude', 'boat_longitude', 'heading_true_deg',
    'gps_age_s', 'heading_age_s', 'rov_latitude', 'rov_longitude', 'depth_m',
    'forward_m', 'starboard_m', 'enhanced_depth', 'gga', 'udp_sent', 'message', 'config_json',
)


class BridgeWorker(threading.Thread):
    def __init__(self, config, pressed_at, serial_factory=None, socket_factory=None):
        super().__init__(name='SeaTrac bridge', daemon=True)
        config.validate()
        self.config = config
        self.pressed_at = pressed_at
        self.serial_factory = serial_factory or serial.Serial
        self.socket_factory = socket_factory or socket.socket
        self.stop_requested = threading.Event()
        self.inputs = queue.Queue(maxsize=4096)
        self.reader_errors = queue.Queue()
        self.display = queue.Queue(maxsize=1000)
        self.lock = threading.Lock()
        self.details = {'status': 'Opening connections...', 'log': '', 'sent': 0,
                        'solution': '', 'last_output': None, 'error': '', 'display_dropped': 0}

    def snapshot(self):
        with self.lock:
            return dict(self.details)

    def update(self, **values):
        with self.lock:
            self.details.update(values)

    def stop(self):
        self.stop_requested.set()

    def show(self, source, text):
        try:
            self.display.put_nowait((source, text))
        except queue.Full:
            try:
                self.display.get_nowait()
            except queue.Empty:
                pass
            self.display.put_nowait((source, text))
            with self.lock:
                self.details['display_dropped'] += 1

    def read_port(self, port, source):
        lines = LineBuffer()
        try:
            while not self.stop_requested.is_set():
                chunk = port.read(min(port.in_waiting or 1, 4096))
                if not chunk:
                    continue
                for text in lines.feed(chunk):
                    event = InputLine(source, text, datetime.now(timezone.utc), time.monotonic())
                    try:
                        self.inputs.put(event, timeout=0.25)
                    except queue.Full as error:
                        raise RuntimeError('Input queue full; stopped to avoid silent log loss.') from error
        except Exception as error:
            if not self.stop_requested.is_set():
                self.reader_errors.put(f'{source}: {error}')
                self.stop_requested.set()

    def run(self):
        readers = []
        try:
            with ExitStack() as stack:
                directory = Path(self.config.log_directory).expanduser()
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / self.pressed_at.strftime('navigation_%Y%m%dT%H%M%S_%fZ.csv')
                logfile = stack.enter_context(path.open('x', newline='', encoding='utf-8'))
                writer = csv.DictWriter(logfile, fieldnames=LOG_FIELDS)
                writer.writeheader()
                self.update(log=str(path.resolve()))
                state = NavigationState(self.config)

                def log(event, text='', utc=None, received=None, solution=None,
                        fix=None, gga='', sent=False, message='', configuration=''):
                    now = time.monotonic() if received is None else received
                    row = dict(timestamp_utc=(utc or datetime.now(timezone.utc)).isoformat(),
                               session_start_utc=self.pressed_at.isoformat(), event=event,
                               raw_input=text, raw_gps=state.raw_gps,
                               raw_heading=state.raw_heading, raw_seatrac=state.raw_usbl,
                               heading_true_deg='' if state.heading is None else state.heading,
                               gga=gga, udp_sent=int(sent), message=message,
                               config_json=configuration)
                    if state.boat is not None:
                        row.update(boat_latitude=state.boat.latitude, boat_longitude=state.boat.longitude)
                    for column, seen in (('gps_age_s', state.gps_time),
                                         ('heading_age_s', state.heading_time)):
                        if seen is not None:
                            row[column] = f'{now - seen:.3f}'
                    if solution is not None:
                        row.update(rov_latitude=f'{solution.latitude:.9f}',
                                   rov_longitude=f'{solution.longitude:.9f}',
                                   depth_m=solution.depth_m, forward_m=solution.forward_m,
                                   starboard_m=solution.starboard_m)
                    if fix is not None:
                        row['enhanced_depth'] = int(fix.enhanced)
                    writer.writerow(row)
                    logfile.flush()

                log('START', configuration=json.dumps(asdict(self.config), sort_keys=True))
                try:
                    gps_port = stack.enter_context(self.serial_factory(
                        port=self.config.gps_port, baudrate=self.config.gps_baud,
                        bytesize=8, parity='N', stopbits=self.config.gps_stopbits,
                        timeout=0.2, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False))
                    usbl_port = stack.enter_context(self.serial_factory(
                        port=self.config.usbl_port, baudrate=self.config.usbl_baud,
                        bytesize=8, parity='N', stopbits=2, timeout=0.2, write_timeout=1,
                        xonxoff=False, rtscts=False, dsrdtr=False))
                    udp = stack.enter_context(self.socket_factory(socket.AF_INET, socket.SOCK_DGRAM))
                    udp.settimeout(1)
                    for port, source in ((gps_port, 'GPS'), (usbl_port, 'USBL')):
                        reader = threading.Thread(target=self.read_port, args=(port, source), daemon=True)
                        readers.append(reader)
                        reader.start()
                    self.process(state, usbl_port, udp, log)
                    if not self.reader_errors.empty():
                        raise RuntimeError(self.reader_errors.get_nowait())
                    log('STOP', message='Operator stopped bridge')
                except Exception as error:
                    log('ERROR', message=str(error))
                    raise
                finally:
                    self.stop_requested.set()
                    for reader in readers:
                        reader.join(timeout=1)
        except Exception as error:
            self.update(error=str(error), status=f'Stopped: {error}')
        else:
            self.update(status='Stopped')
        finally:
            self.stop_requested.set()

    def process(self, state, usbl_port, udp, log):
        next_ping = time.monotonic()
        pending_until = None
        acoustic_time = None
        last_notice = ''
        while not self.stop_requested.is_set():
            now = time.monotonic()
            if pending_until is not None and now >= pending_until:
                log('PING_TIMEOUT', message='No completed ping; check acoustic range timeout/settings')
                self.show('USBL', '[Ping response timeout]\n')
                pending_until = None
            if self.config.active_ping and pending_until is None and now >= next_ping:
                command = encode_command(bytes((0x40, self.config.target_id,
                                                0x06 if self.config.enhanced_ping else 0x04)))
                if usbl_port.write(command) != len(command):
                    raise OSError('Incomplete SeaTrac command write')
                log('USBL_TX', text=command.decode('ascii'))
                self.show('USBL', 'TX ' + command.decode('ascii'))
                pending_until = now + self.config.reply_timeout
                next_ping = now + self.config.ping_interval
            reason = state.readiness(now)
            if not reason and (acoustic_time is None or now - acoustic_time > self.config.max_age):
                reason = 'Waiting for fresh accepted USBL position; no UDP output'
            notice = reason or 'Running; forwarding accepted positions'
            self.update(status=notice)
            if notice != last_notice:
                log('STATE', message=notice)
                last_notice = notice
            try:
                event = self.inputs.get(timeout=0.05)
            except queue.Empty:
                continue
            self.show(event.source, event.text)
            solution = fix = None
            gga = ''
            sent = False
            message = ''
            try:
                if event.source == 'GPS':
                    state.gps(event.text, event.received)
                else:
                    state.raw_usbl = event.text
                    payload = decode_frame(event.text)
                    if payload[0] == 0x40:
                        if len(payload) != 3:
                            raise ValueError('Invalid PING_SEND acknowledgement')
                        if payload[2] == self.config.target_id and payload[1] != 0:
                            pending_until = None
                            message = f'PING_SEND rejected, status 0x{payload[1]:02X}'
                    elif payload[0] == 0x43:
                        if len(payload) != 3:
                            raise ValueError('Invalid PING_ERROR message')
                        if payload[2] == self.config.target_id:
                            pending_until = None
                            message = f'Acoustic ping failed, status 0x{payload[1]:02X}'
                    elif payload[0] == 0x42:
                        if len(payload) > 2 and payload[2] == self.config.target_id:
                            pending_until = None
                        solution, fix, message = state.acoustic(payload, event.received, time.monotonic())
                        if solution is not None:
                            gga = make_gga(solution, event.utc, self.config.surface_msl)
                            packet = gga.encode('ascii')
                            try:
                                if udp.sendto(packet, (self.config.udp_host, self.config.udp_port)) != len(packet):
                                    raise OSError('Incomplete UDP datagram')
                            except OSError as error:
                                log(event.source, event.text, event.utc, event.received,
                                    solution, fix, gga, False, f'UDP failed: {error}')
                                raise
                            sent = True
                            acoustic_time = time.monotonic()
                            count = self.snapshot()['sent'] + 1
                            self.update(sent=count, last_output=acoustic_time,
                                        solution=f'{solution.latitude:.7f}, {solution.longitude:.7f}  '
                                                 f'Depth {solution.depth_m:.1f} m')
            except ValueError as error:
                message = str(error)
            log(event.source, event.text, event.utc, event.received,
                solution, fix, gga, sent, message)
            if message and solution is None:
                self.show(event.source, f'[{message}]\n')