# PHINS Binary Data Parser

## Overview
This script parses PHINS (Photonics Inertial Navigation System) Standard v2 binary files and converts them to CSV and ESRI shapefiles for GIS analysis.

## Background on PHINS

### What is PHINS?
PHINS (Photonics Inertial Navigation System) is a high-performance Fiber Optic Gyro (FOG) based inertial navigation system manufactured by iXBlue (now Exail). The PHINS C7 is commonly used in underwater vehicles, surface vessels, and other applications requiring precise navigation.

### PHINS Standard v2 Protocol
The PHINS Standard v2 protocol is a binary data format that includes:

- **INS (Inertial Navigation System) messages**: Real-time navigation data
- **Attitude data**: Heading, pitch, roll
- **Position data**: Latitude, longitude, altitude
- **Velocity data**: Speed over ground
- **Status information**: System health and quality metrics

## Binary Message Structure

### Message Format
Each PHINS Standard v2 message follows this structure:

```
[STX] [MSG_ID] [LENGTH] [PAYLOAD] [CHECKSUM]
```

- **STX (1 byte)**: Start marker (0x02)
- **MSG_ID (1 byte)**: Message identifier
- **LENGTH (2 bytes)**: Payload length (little-endian)
- **PAYLOAD (variable)**: Message data
- **CHECKSUM (2 bytes)**: CRC or simple checksum

### Common Message IDs

| ID | Name | Description |
|----|------|-------------|
| 0x01 | INS_TIME | Timestamp (Unix time) |
| 0x03 | INS_ATTITUDE_HEADING | Heading, pitch, roll |
| 0x04 | INS_POSITION | Latitude, longitude, altitude |
| 0x05 | INS_SPEED | Velocity components |
| 0x06 | INS_ALTITUDE | Depth/altitude |
| 0x07 | INS_STATUS | System status |

### Data Types
- **Doubles (8 bytes)**: Used for positions, angles, velocities
- **Floats (4 bytes)**: Used for some sensor data
- **Integers (4 bytes)**: Used for timestamps and counters
- **Little-endian byte order**: Standard for PHINS protocol

## Usage

### Running the Script

1. **Launch the GUI**:
   ```powershell
   python PHINS_BinaryToSHP.py
   ```

2. **Add PHINS binary files**:
   - Click "Add PHINS Binary File"
   - Browse to your .bin, .phins, or .dat files
   - Add multiple files for batch processing

3. **Select output location** (optional):
   - Click "Change" next to Output Folder
   - Choose a destination folder
   - Default: Creates "NavProducts" folder in source directory

4. **Process files**:
   - Click "Process Files"
   - Progress bar shows processing status
   - Results window displays success/errors

### Output Files

For each processed file (e.g., `DIVE001_PHINS.bin`):

1. **CSV File**: `DIVE001_PHINS_Nav_Formatted.csv`
   - Tab-separated values
   - Columns: mission_time, heading, latitude, longitude, depth, heading_rate, altitude
   - Compatible with MSN005 format

2. **Shapefile**: `Dissolved_DIVE001.shp` (+ .dbf, .shx, .prj)
   - WGS84 coordinate system (EPSG:4326)
   - Polyline geometry representing vehicle track
   - Attributes: DIVE (mission ID), Length_m (track length in meters)

## Troubleshooting

### Common Issues

**1. "No navigation data extracted from file"**
- The binary file may not be PHINS Standard v2 format
- File may be corrupted
- Check file extension and size

**2. "Not enough valid navigation points"**
- Binary file contains insufficient position messages
- Data may be filtered out due to invalid coordinates
- Check that file contains actual mission data (not just system startup)

**3. ArcPy errors**
- Ensure ArcGIS Pro Python environment is activated
- Check that output folder has write permissions
- Verify ArcGIS license is available

### File Format Variants

PHINS systems can output several formats:
- **Standard v1**: Older protocol (not supported)
- **Standard v2**: Supported by this script
- **Standard v3**: Newer protocol (may require updates)
- **Custom formats**: Require manufacturer documentation

If you have PHINS files that don't parse correctly, you may need:
1. The specific protocol documentation from Exail/iXBlue
2. Sample files with known message structure
3. The PHINS configuration used during data collection

## Alternative Approaches

### If Binary Parsing Fails

1. **Check for ASCII output**:
   - PHINS systems can often output NMEA-0183 sentences
   - Look for .txt or .log files with readable text
   - NMEA sentences start with $ (e.g., $GPGGA, $GPRMC)

2. **Use manufacturer software**:
   - Exail provides PHINStools for data export
   - Can convert binary to CSV or other formats
   - May require Windows environment

3. **Contact manufacturer**:
   - Exail support can provide protocol documentation
   - May have Python libraries for parsing
   - Can clarify message structure for your specific PHINS model

## Technical Details

### Coordinate System
- **Input**: PHINS outputs latitude/longitude in decimal degrees
- **Output shapefile**: WGS84 (EPSG:4326)
- **Altitude**: Can be height above ellipsoid or depth (negative)

### Timestamp Handling
- PHINS time is typically Unix timestamp (seconds since 1970-01-01 UTC)
- Script converts to mission_time (epoch seconds)
- Assumes UTC timezone

### Data Quality
The parser attempts to extract all available messages but:
- Skips malformed messages
- Filters invalid coordinates (NaN, Inf)
- Requires minimum 2 points for line creation
- Reports processing statistics

## Extending the Parser

### Adding New Message Types

To parse additional PHINS messages:

```python
# Define message ID
MSG_INS_NEW = 0x08

# Add parsing function
def _parse_new_message(self, payload):
    if len(payload) >= 16:
        value1 = struct.unpack('<d', payload[0:8])[0]
        value2 = struct.unpack('<d', payload[8:16])[0]
        
        if not hasattr(self, 'current_record'):
            self.current_record = {}
        
        self.current_record['new_field'] = value1
```

### Custom Output Format

To modify CSV output columns, edit the `process_phins_file` function:

```python
# Add custom columns
output_data['custom_field'] = nav_data.get('custom_field', 0.0)
```

## References

- **iXBlue/Exail**: [www.exail.com](https://www.exail.com)
- **PHINS C7**: High-performance INS for demanding applications
- **Binary protocol**: Proprietary format, documentation available from manufacturer
- **Similar tool**: See `Remus_NavTXTToSHP.py` for text-based navigation parsing

## Two PHINS File Variants

In practice, iXBlue/Exail PHINS units are seen producing **two different**
`.bin` layouts, and each needs its own script:

| Script | File layout | Sentence example |
|---|---|---|
| `Remus_PHINS_BinaryToSHP.py` | Proprietary `IX`-header binary messages (STX/MSG_ID/LENGTH/PAYLOAD/CHECKSUM) | raw bytes, no `$` text |
| `Remus_PHINS_StdV2_ToSHP.py` | NMEA-0183-style ASCII sentences with embedded null-byte padding | `$HEHDT,22.78162,T*15`, `$PIXSE,POSITI,...` |

If `Remus_PHINS_BinaryToSHP.py` prints `WARNING: File appears to contain
ASCII/NMEA data!`, use `Remus_PHINS_StdV2_ToSHP.py` on that file instead. It
parses `$HEHDT` (heading), `$PIXSE,ATITUD` (roll/pitch), `$PIXSE,POSITI`
(lat/lon/altitude), `$PIXSE,DEPIN_` (depth), `$PIXSE,LOGDVL` (altitude above
bottom) and `$PIXSE,TIME__` (timestamp) sentences, interpolates them onto the
position timestamps, and writes the same CSV/shapefile outputs described
above.

## Version History

- **v1.0** (2025-12-08): Initial release
- **v1.1** (2026-09-30): Added `Remus_PHINS_StdV2_ToSHP.py` for the NMEA-style
  PHINS Standard v2 variant
  - Basic PHINS Standard v2 parsing
  - GUI for batch processing
  - CSV and shapefile output

## Author

Mike Bollinger - 2025

## Notes

This parser is based on publicly available information about PHINS systems and common binary protocol structures. For production use with critical data, verify output against manufacturer-provided tools and consult Exail technical documentation for your specific PHINS model and firmware version.
