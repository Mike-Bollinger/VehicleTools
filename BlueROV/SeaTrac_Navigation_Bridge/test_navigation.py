from datetime import datetime, timezone
import csv
from pathlib import Path
import queue
import socket
import struct
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from geographiclib.geodesic import Geodesic
import pynmea2

from bridge import BridgeWorker, Config, LineBuffer, NavigationState
from main import BridgeApp
from navigation import (AcousticFix, BoatFix, crc16, decode_frame, encode_command,
                        make_gga, nmea_coordinate, parse_gps, parse_ping_response, solve)


def response(flags=0x0F, source=2, yaw=900):
    payload = b'\x42' + struct.pack('<BBBBhhhHHh', 1, source, flags, 7,
                                     yaw, 0, 0, 10, 15000, -500)
    if flags & 1:
        payload += struct.pack('<IiH', 100, 1000, 1000)
    if flags & 2:
        payload += struct.pack('<Bhhhhhh', 3, -500, -500, -500, 0, 0, 100)
    if flags & 4:
        payload += struct.pack('<hhh', 1000, 0, 250)
    return payload


class NavigationTests(unittest.TestCase):
    def test_published_crc_examples(self):
        for payload, expected in [(b'\x02', b'#0281C1\r\n'),
                                  (b'\x15', b'#15C1CF\r\n'),
                                  (b'\x10\x00', b'#10000DC0\r\n'),
                                  (b'\x40\x02', b'#4002B001\r\n')]:
            self.assertEqual(encode_command(payload), expected)
        self.assertEqual(crc16(b'123456789'), 0xBB3D)

    def test_frame_and_optional_fields(self):
        for flags in (4, 5, 6, 7, 15):
            payload = response(flags)
            raw = '$' + encode_command(payload).decode()[1:]
            fix = parse_ping_response(decode_frame(raw), 2)
            self.assertEqual(fix.depth_m, 25)
            self.assertEqual(fix.easting_m, 100)
        self.assertIsNone(parse_ping_response(response(0), 2))
        self.assertIsNone(parse_ping_response(response(0x1F), 2))
        self.assertIsNone(parse_ping_response(response(source=3), 2))
        for length in range(len(response())):
            with self.assertRaises(ValueError):
                parse_ping_response(response()[:length], 2) if length else decode_frame('$')

    def test_bad_crc_and_hex(self):
        for raw in ('$420000', '$42ZZ00', '$42 0000', '#0281C1'):
            with self.assertRaises(ValueError):
                decode_frame(raw)

    def test_heading_rotation_and_geodesic(self):
        boat = BoatFix(45, -123)
        fix = parse_ping_response(response(), 2)
        for heading in (0, 90, 180, 270):
            solution = solve(boat, heading, fix)
            inverse = Geodesic.WGS84.Inverse(45, -123, solution.latitude, solution.longitude)
            self.assertAlmostEqual(inverse['s12'], 100, places=6)
            self.assertAlmostEqual((inverse['azi1'] - heading + 180) % 360 - 180, 0, places=6)
        solution = solve(boat, 0, fix, 90, 0, 10)
        self.assertAlmostEqual(solution.forward_m, 0, places=6)
        self.assertAlmostEqual(solution.starboard_m, 110, places=6)

    def test_gps_and_generated_gga(self):
        raw = str(pynmea2.GGA('GN', 'GGA', ('120000', '4500.0000', 'N',
                         '12300.0000', 'W', '1', '10', '1', '0', 'M', '0', 'M', '', '')))
        self.assertEqual(parse_gps(raw), BoatFix(45, -123))
        self.assertEqual(parse_gps(str(pynmea2.HDT('HE', 'HDT', ('90.0', 'T')))), 90)
        with self.assertRaises(ValueError):
            parse_gps(raw[:-1] + ('1' if raw[-1] != '1' else '2'))
        solution = solve(BoatFix(-45, 179.9999), 90,
                         AcousticFix(2, 0, 0, 100, 25, True))
        output = make_gga(solution, datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
        parsed = pynmea2.parse(output, check=True)
        self.assertEqual(parsed.talker, 'GP')
        self.assertEqual(float(parsed.altitude), -25)
        self.assertEqual(parsed.lat_dir, 'S')
        self.assertEqual(parsed.lon_dir, 'W')
        self.assertTrue(output.endswith('\r\n'))
        self.assertEqual(nmea_coordinate(12 + 59.9999999 / 60, True)[0], '1300.000000')


def gps_sentences(quality='1'):
    position = str(pynmea2.GGA('GN', 'GGA', ('120000', '4500.0000', 'N',
                       '12300.0000', 'W', quality, '10', '1', '0', 'M', '0', 'M', '', '')))
    heading = str(pynmea2.HDT('HE', 'HDT', ('90.0', 'T')))
    return position + '\r\n', heading + '\r\n'


class FakeSerial:
    def __init__(self):
        self.chunks = queue.Queue()
        self.pending = b''
        self.writes = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.pending)

    def read(self, size):
        if not self.pending:
            try:
                chunk = self.chunks.get(timeout=0.05)
            except queue.Empty:
                return b''
            if isinstance(chunk, Exception):
                raise chunk
            self.pending = chunk
        result, self.pending = self.pending[:size], self.pending[size:]
        return result

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.closed = True


class BridgeTests(unittest.TestCase):
    def test_fragmented_serial_lines_and_limits(self):
        lines = LineBuffer()
        self.assertEqual(lines.feed(b'$GNG'), [])
        self.assertEqual(lines.feed(b'GA,one\r'), [])
        self.assertEqual(lines.feed(b'\n$HEHDT,two\r\n'), ['$GNGGA,one\r\n', '$HEHDT,two\r\n'])
        with self.assertRaises(ValueError):
            lines.feed(b'x' * 8193)

    def test_configuration_rejects_invalid_values(self):
        for overrides in ({'usbl_port': '/gps'}, {'max_age': float('nan')},
                          {'udp_host': 'localhost'}, {'udp_port': 0}, {'target_id': 101},
                          {'gps_stopbits': 3}, {'reply_timeout': 0}, {'ping_interval': 0}):
            config = {'gps_port': '/gps', 'usbl_port': '/usbl'}
            config.update(overrides)
            with self.assertRaises(ValueError):
                Config(**config).validate()

    def test_freshness_and_invalid_fix_gates(self):
        state = NavigationState(Config('/gps', '/usbl', max_age=3))
        position, heading = gps_sentences()
        self.assertIsNone(state.acoustic(response(), 100, 100)[0])
        state.gps(position, 100)
        self.assertIsNone(state.acoustic(response(), 100, 100)[0])
        state.gps(heading, 100)
        self.assertIsNotNone(state.acoustic(response(), 101, 101)[0])
        self.assertIsNone(state.acoustic(response(), 104, 104)[0])
        state.gps(position, 104)
        self.assertIn('heading', state.acoustic(response(), 104, 104)[2])
        state.gps(heading, 104)
        self.assertIsNone(state.acoustic(response(), 100, 104)[0])
        self.assertIsNone(state.acoustic(response(), 103, 104)[0])
        bad_position, _ = gps_sentences('0')
        with self.assertRaises(ValueError):
            state.gps(bad_position, 104)
        self.assertIsNone(state.boat)
        state.gps(position, 104)
        with self.assertRaises(ValueError):
            state.gps('$HEHDT,nan,T*00', 104)
        self.assertIsNone(state.heading)

    def make_worker(self, directory, udp_port, active_ping=True, socket_factory=None):
        gps, usbl = FakeSerial(), FakeSerial()
        calls = []

        def factory(**settings):
            calls.append(settings)
            return gps if settings['port'] == '/gps' else usbl

        config = Config('/gps', '/usbl', udp_port=udp_port, log_directory=directory,
                        active_ping=active_ping, max_age=3)
        pressed = datetime(2026, 11, 9, 12, 34, 56, 123456, tzinfo=timezone.utc)
        worker = BridgeWorker(config, pressed, serial_factory=factory, socket_factory=socket_factory)
        return worker, gps, usbl, calls

    def await_gps(self, worker):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            source, raw = worker.display.get(timeout=3)
            if source == 'GPS' and raw.startswith('$HEHDT'):
                return
        self.fail('GPS was not processed')

    def test_serial_to_real_udp_and_csv(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1', 0))
            receiver.settimeout(3)
            worker, gps, usbl, calls = self.make_worker(directory, receiver.getsockname()[1])
            gps.chunks.put(''.join(gps_sentences()).encode('ascii'))
            worker.start()
            try:
                self.await_gps(worker)
                frame = b'$' + encode_command(response())[1:]
                usbl.chunks.put(b'$420000\r\n' + frame[:12])
                usbl.chunks.put(frame[12:])
                packet, address = receiver.recvfrom(1024)
                decoded = pynmea2.parse(packet.decode('ascii'), check=True)
                self.assertEqual(float(decoded.altitude), -25)
                self.assertGreater(decoded.longitude, -123)
                self.assertTrue(packet.endswith(b'\r\n'))
            finally:
                worker.stop()
                worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(worker.snapshot()['error'], '')
            self.assertEqual(worker.snapshot()['sent'], 1)
            self.assertTrue(gps.closed and usbl.closed)
            self.assertEqual(calls[0]['stopbits'], 1)
            self.assertEqual(calls[1]['stopbits'], 2)
            self.assertEqual(usbl.writes, [encode_command(bytes((0x40, 2, 6)))])
            path = Path(directory) / 'navigation_20261109T123456_123456Z.csv'
            with path.open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['event'], 'START')
            self.assertIn('"gps_port": "/gps"', rows[0]['config_json'])
            self.assertEqual(rows[-1]['event'], 'STOP')
            successful = [row for row in rows if row['udp_sent'] == '1']
            self.assertEqual(len(successful), 1)
            self.assertEqual(successful[0]['raw_gps'], gps_sentences()[0])
            self.assertEqual(successful[0]['raw_heading'], gps_sentences()[1])
            self.assertEqual(successful[0]['raw_seatrac'], frame.decode('ascii'))
            self.assertEqual(successful[0]['gga'], packet.decode('ascii'))
            self.assertTrue(any(row['message'] == 'SeaTrac CRC mismatch' for row in rows))

    def test_serial_disconnect_stops_session(self):
        with tempfile.TemporaryDirectory() as directory:
            worker, gps, usbl, calls = self.make_worker(directory, 27000, active_ping=False)
            gps.chunks.put(OSError('Device disconnected'))
            worker.start()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertIn('Device disconnected', worker.snapshot()['error'])
            self.assertTrue(gps.closed and usbl.closed)
            self.assertEqual(usbl.writes, [])
            with Path(worker.snapshot()['log']).open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[-1]['event'], 'ERROR')

    def test_udp_failure_is_logged_and_stops(self):
        class BrokenSocket:
            def __enter__(self):
                return self

            def __exit__(self, *exception):
                pass

            def settimeout(self, value):
                pass

            def sendto(self, *args):
                raise OSError('UDP unavailable')

        with tempfile.TemporaryDirectory() as directory:
            worker, gps, usbl, calls = self.make_worker(directory, 27000,
                socket_factory=lambda *args: BrokenSocket())
            gps.chunks.put(''.join(gps_sentences()).encode('ascii'))
            worker.start()
            try:
                self.await_gps(worker)
                usbl.chunks.put(b'$' + encode_command(response())[1:])
                worker.join(timeout=3)
            finally:
                worker.stop()
                worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertIn('UDP unavailable', worker.snapshot()['error'])
            self.assertEqual(worker.snapshot()['sent'], 0)
            with Path(worker.snapshot()['log']).open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            failed = [row for row in rows if row['message'].startswith('UDP failed:')]
            self.assertEqual(len(failed), 1)
            self.assertTrue(failed[0]['gga'].startswith('$GPGGA'))
            self.assertEqual(failed[0]['udp_sent'], '0')


class GUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Graphical display unavailable: {error}')
        self.root.withdraw()
        with patch('main.list_ports.comports', return_value=[]):
            self.app = BridgeApp(self.root)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.app.worker is not None:
            self.app.worker.stop()
            self.app.worker.join(timeout=3)
        self.root.after_cancel(self.app.poll_id)
        self.root.destroy()

    def poll(self):
        self.root.after_cancel(self.app.poll_id)
        self.app.poll()

    def test_invalid_configuration_does_not_start(self):
        with patch('main.messagebox.showerror') as error:
            self.app.start()
        error.assert_called_once()
        self.assertIsNone(self.app.worker)
        self.assertFalse(self.app.start_button.instate(['disabled']))

    def test_start_stop_controls_feeds_and_timestamp(self):
        gps, usbl = FakeSerial(), FakeSerial()
        gps.chunks.put(''.join(gps_sentences()).encode('ascii'))
        with tempfile.TemporaryDirectory() as directory:
            for name, value in (('gps_port', '/gps'), ('usbl_port', '/usbl'),
                                ('log_directory', directory), ('active_ping', False)):
                self.app.values[name].set(value)

            def create_worker(config, pressed_at):
                return BridgeWorker(config, pressed_at,
                    serial_factory=lambda **settings: gps if settings['port'] == '/gps' else usbl)

            before = datetime.now(timezone.utc)
            with patch('main.BridgeWorker', side_effect=create_worker):
                self.app.start()
            after = datetime.now(timezone.utc)
            worker = self.app.worker
            self.assertTrue(before <= worker.pressed_at <= after)
            self.assertTrue(self.app.start_button.instate(['disabled']))
            self.assertTrue(self.app.gps_port.instate(['disabled']))
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                source, text = worker.display.get(timeout=3)
                self.app.append(source, text)
                if text.startswith('$HEHDT'):
                    break
            self.assertIn('$GNGGA', self.app.feeds['GPS'].get('1.0', 'end'))
            self.assertIn('$HEHDT', self.app.feeds['GPS'].get('1.0', 'end'))
            self.app.stop()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.poll()
            self.assertFalse(self.app.start_button.instate(['disabled']))
            self.assertTrue(self.app.stop_button.instate(['disabled']))
            self.assertFalse(self.app.gps_port.instate(['disabled']))
            expected = worker.pressed_at.strftime('navigation_%Y%m%dT%H%M%S_%fZ.csv')
            self.assertEqual(Path(worker.snapshot()['log']).name, expected)
            self.assertIn(expected, self.app.log_status.get())


if __name__ == '__main__':
    unittest.main()