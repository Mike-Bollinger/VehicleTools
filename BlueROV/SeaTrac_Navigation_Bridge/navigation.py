"""SeaTrac developer guide rev. 13 framing and navigation calculations."""

from dataclasses import dataclass
from datetime import datetime
import math
import struct

from geographiclib.geodesic import Geodesic
import pynmea2


@dataclass(frozen=True)
class BoatFix:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class AcousticFix:
    source_id: int
    yaw_deg: float
    easting_m: float
    northing_m: float
    depth_m: float
    enhanced: bool


@dataclass(frozen=True)
class Solution:
    latitude: float
    longitude: float
    depth_m: float
    forward_m: float
    starboard_m: float


def crc16(data: bytes) -> int:
    checksum = 0
    for value in data:
        checksum ^= value
        for _ in range(8):
            checksum = (checksum >> 1) ^ (0xA001 if checksum & 1 else 0)
    return checksum


def encode_command(payload: bytes) -> bytes:
    packet = payload + struct.pack('<H', crc16(payload))
    return b'#' + packet.hex().upper().encode('ascii') + b'\r\n'


def decode_frame(raw: str) -> bytes:
    text = raw.rstrip('\r\n')
    if not text.startswith('$') or len(text) < 7 or len(text[1:]) % 2:
        raise ValueError('Invalid SeaTrac response framing')
    if any(character not in '0123456789abcdefABCDEF' for character in text[1:]):
        raise ValueError('Non-hexadecimal SeaTrac response')
    packet = bytes.fromhex(text[1:])
    payload, received = packet[:-2], struct.unpack('<H', packet[-2:])[0]
    if crc16(payload) != received:
        raise ValueError('SeaTrac CRC mismatch')
    return payload


def parse_ping_response(payload: bytes, target_id: int) -> AcousticFix | None:
    if not payload or payload[0] != 0x42:
        return None
    if len(payload) < 17:
        raise ValueError('Truncated ACOFIX header')
    destination, source, flags, message_type, yaw, pitch, roll, depth, vos, rssi = (
        struct.unpack_from('<BBBBhhhHHh', payload, 1)
    )
    if flags & 0xE0:
        raise ValueError('Unsupported ACOFIX flags')
    offset = 17
    if flags & 0x01:
        offset += 10
    if flags & 0x02:
        if len(payload) <= offset:
            raise ValueError('Truncated USBL channel count')
        channels = payload[offset]
        offset += 1 + 2 * channels + 6
    if len(payload) < offset:
        raise ValueError('Truncated optional ACOFIX fields')
    if not flags & 0x04:
        if len(payload) != offset:
            raise ValueError('Unexpected ACOFIX data')
        return None
    if len(payload) != offset + 6:
        raise ValueError('Invalid ACOFIX position length')
    if source != target_id or flags & 0x10:
        return None
    easting, northing, remote_depth = struct.unpack_from('<hhh', payload, offset)
    return AcousticFix(source, yaw / 10, easting / 10, northing / 10,
                       remote_depth / 10, bool(flags & 0x08))


def parse_gps(raw: str) -> BoatFix | float | None:
    try:
        message = pynmea2.parse(raw.strip(), check=True)
        if message.sentence_type == 'GGA':
            quality = int(message.gps_qual)
            if quality not in (1, 2, 3, 4, 5):
                raise ValueError('GPS has no measured position fix')
            latitude = coordinate(message.lat, message.lat_dir, 90, 'N', 'S')
            longitude = coordinate(message.lon, message.lon_dir, 180, 'E', 'W')
            return BoatFix(latitude, longitude)
        if message.sentence_type == 'HDT':
            heading = float(message.heading)
            if message.hdg_true != 'T' or not math.isfinite(heading) or not 0 <= heading < 360:
                raise ValueError('Invalid true heading')
            return heading
    except (pynmea2.ParseError, AttributeError, TypeError) as error:
        raise ValueError(str(error)) from error
    return None


def coordinate(value: str, hemisphere: str, limit: int, positive: str, negative: str) -> float:
    degrees_digits = 2 if limit == 90 else 3
    if hemisphere not in (positive, negative) or len(value) < degrees_digits + 2:
        raise ValueError('Missing GPS coordinate')
    degrees = int(value[:degrees_digits])
    minutes = float(value[degrees_digits:])
    result = degrees + minutes / 60
    if not math.isfinite(result) or degrees < 0 or not 0 <= minutes < 60 or result > limit:
        raise ValueError('GPS coordinate out of range')
    return result if hemisphere == positive else -result


def solve(boat: BoatFix, heading_deg: float, fix: AcousticFix,
          mounting_yaw_deg: float = 0, lever_forward_m: float = 0,
          lever_starboard_m: float = 0) -> Solution:
    yaw = math.radians(fix.yaw_deg)
    local_forward = fix.northing_m * math.cos(yaw) + fix.easting_m * math.sin(yaw)
    local_starboard = fix.easting_m * math.cos(yaw) - fix.northing_m * math.sin(yaw)
    mount = math.radians(mounting_yaw_deg)
    forward = local_forward * math.cos(mount) - local_starboard * math.sin(mount)
    starboard = local_forward * math.sin(mount) + local_starboard * math.cos(mount)
    forward += lever_forward_m
    starboard += lever_starboard_m
    bearing = heading_deg + math.degrees(math.atan2(starboard, forward))
    position = Geodesic.WGS84.Direct(boat.latitude, boat.longitude, bearing,
                                   math.hypot(forward, starboard))
    return Solution(position['lat2'], position['lon2'], fix.depth_m, forward, starboard)


def nmea_coordinate(value: float, latitude: bool) -> tuple[str, str]:
    total_minutes = round(abs(value) * 60, 6)
    degrees, minutes = divmod(total_minutes, 60)
    width = 2 if latitude else 3
    hemisphere = ('N' if value >= 0 else 'S') if latitude else ('E' if value >= 0 else 'W')
    return f'{int(degrees):0{width}d}{minutes:09.6f}', hemisphere


def make_gga(solution: Solution, timestamp: datetime, surface_msl_m: float = 0) -> str:
    latitude, north_south = nmea_coordinate(solution.latitude, True)
    longitude, east_west = nmea_coordinate(solution.longitude, False)
    fields = (timestamp.strftime('%H%M%S.%f')[:-4], latitude, north_south,
              longitude, east_west, '1', '00', '',
              f'{surface_msl_m - solution.depth_m:.2f}', 'M', '', 'M', '', '')
    return str(pynmea2.GGA('GP', 'GGA', fields)) + '\r\n'