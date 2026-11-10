# SeaTrac Navigation Bridge: Linux Setup

## Overview

This application replaces the live positioning bridge normally provided by PinPoint. It reads boat GPS GGA and true-heading HDT sentences, interrogates an ROV SeaTrac beacon through the topside X150, computes the ROV's WGS84 position, and sends checksummed GPGGA sentences over UDP.

- `main.py`: Tkinter GUI with Start/Stop controls and separate scrolling GPS and USBL feeds.
- `bridge.py`: two serial reader threads, acoustic polling, freshness checks, UDP delivery, and CSV logging.
- `navigation.py`: SeaTrac framing/CRC validation, PING response decoding, geodesic positioning, and NMEA generation.
- `test_navigation.py`: navigation, simulated-serial integration, real localhost UDP, logging, and GUI lifecycle tests.
- `requirements.txt`: Python dependencies.

The software is implemented and has passed automated tests on the development computer. Physical SeaTrac/GPS equipment, the target Linux desktop, and the pilot software have not been tested. Complete the commissioning checks below before using its output operationally.

## 1. Install Python on Linux

Python **3.10 or newer** is required. These commands target Ubuntu 22.04 or newer and Debian systems with a suitable Python version:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk
python3 --version
```

Run privileged installation commands yourself in a terminal on the Linux device. Other Linux distributions require equivalent packages from their package manager.

The GUI needs a graphical desktop session on the Linux computer. A plain SSH terminal without graphical forwarding will not display it. Check Tkinter with `python3 -m tkinter`; close the small test window afterward.

## 2. Transfer the Files and Install Dependencies

Transfer this entire `SeaTrac_Navigation_Bridge` folder to the Linux computer, for example to `~/VehicleTools/BlueROV/SeaTrac_Navigation_Bridge`. Alternatively, clone the repository there and navigate to this folder. Adjust the path below to match the actual location.

```bash
cd ~/VehicleTools/BlueROV/SeaTrac_Navigation_Bridge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The dependencies are GeographicLib for WGS84 geodesics, pynmea2 for NMEA parsing/generation, and pyserial for serial acquisition. Tkinter is installed through the Linux package manager, not pip. Installation requires network access unless the packages are available locally.

Activate the environment again whenever opening a new terminal:

```bash
cd ~/VehicleTools/BlueROV/SeaTrac_Navigation_Bridge
source .venv/bin/activate
```

Do not run the application or pip as root. To leave the environment, run `deactivate`.

## 3. Launch the Application

From this folder with the virtual environment activated:

```bash
python main.py
```

No instrument connections or UDP transmissions start until you press **Start**.

1. Select the GPS and SeaTrac serial device paths. Use **Refresh Ports** after connecting a device. The dropdowns are editable so you can paste a stable `/dev/serial/by-id/...` path.
2. Set each device's baud rate. GPS defaults to 4800 baud and one stop bit; change these to match your receiver. SeaTrac defaults to 115200 baud and always uses two stop bits.
3. Enter the ROV's actual beacon ID, UDP destination IPv4 address, and UDP port. Defaults are beacon ID 2 and `127.0.0.1:27000`.
4. Choose a writable log directory. The default is a `logs` folder next to the scripts.
5. Check the mounting/lever-arm settings described below. Keep **Send pings** and **Enhanced depth** checked for standalone enhanced USBL positioning.
6. Press **Start**. The app creates the timestamped log, opens both serial ports, and begins acquisition. Configuration is locked while running.
7. Check the two raw feeds and status. Valid, fresh GGA, HDT, and a position-bearing PING response are all required before UDP output starts. The position line shows the last transmitted coordinates, depth, age, and datagram count.
8. Press **Stop** before unplugging instruments or changing settings. Wait until Start is enabled again. Closing a running window asks to stop the bridge first.

The log filename uses the UTC time captured at the beginning of the Start callback, including microseconds: `navigation_YYYYMMDDTHHMMSS_ffffffZ.csv`. Each Start creates a new file, and an existing file is never overwritten. The full log path is displayed at the bottom of the window.

The left pane shows GPS and heading input. The right pane shows SeaTrac input, outgoing `TX` commands, and bracketed diagnostic messages. Drag the divider to resize the panes. Uncheck **Follow feeds** to inspect earlier lines. **Clear Feeds** clears only the display, not the CSV log. Displays retain a bounded history; a display-drop count indicates UI backlog, not removal of CSV records.

### Polling and Freshness Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Send pings | Enabled | Issue `CID_PING_SEND` requests to the configured ROV ID. Disable only when another controller is already generating PING responses on this link. |
| Enhanced depth | Enabled | Request `MSG_REQX` (USBL plus remote pressure depth). Uncheck for standard `MSG_REQU` USBL. |
| Ping interval | 2 s | Minimum start-to-start interval. Only one request is outstanding at a time; responses/timeouts can make the actual interval longer. |
| Reply timeout | 10 s | Host watchdog for a missing completion. Set at least as long as the X150's configured acoustic range timeout, including turnaround/processing margin. |
| Max input age | 3 s | Maximum receive age of GPS, heading, and queued acoustic data accepted for a new solution. Adjust for actual sensor update rates. |

The app does not change saved beacon settings or perform AHRS calibration. Configure compatible beacon IDs, acoustic parameters, velocity of sound, range timeout, and calibration before deployment using the manufacturer's tools/procedures. Stop other programs from controlling the same serial ports. There is no automatic reconnect: correct the problem and press Start again after an error.

## 4. Run the Tests

From this folder with the virtual environment activated:

```bash
python -m unittest -v test_navigation
```

These tests do not use attached instruments. They exercise protocol framing, CRC examples, optional fix fields, geodesic math, freshness rejection, fragmented simulated serial input, localhost UDP output, CSV contents, disconnect/error cleanup, and GUI controls. GUI tests are skipped if a graphical display is unavailable. Thirteen tests passed on the development computer; target Linux/hardware verification remains necessary.

### Optional Library Example

Paste this command into the Linux terminal while in this folder with the environment activated. It uses **synthetic data**, prints one GGA sentence, and does not read serial ports or send UDP packets:

```bash
python - <<'PY'
from datetime import datetime, timezone
from navigation import AcousticFix, BoatFix, make_gga, solve

boat = BoatFix(latitude=45.0, longitude=-123.0)
acoustic = AcousticFix(
    source_id=2,
    yaw_deg=0.0,
    easting_m=0.0,
    northing_m=100.0,
    depth_m=25.0,
    enhanced=True,
)
solution = solve(boat, heading_deg=90.0, fix=acoustic)
print(solution)
print(make_gga(solution, datetime.now(timezone.utc)), end='')
PY
```

With these inputs, the ROV is 100 m forward of a boat heading east, so its calculated position is approximately 100 m east of the boat. Depth is 25 m below the surface.

## 5. Serial Access and Instrument Setup

Connect the boat GPS and the topside X150's USB serial interface to the Linux computer. Find their device paths:

```bash
python -m serial.tools.list_ports -v
ls -l /dev/serial/by-id/
```

Prefer `/dev/serial/by-id/...` paths when available; `/dev/ttyUSB0` and `/dev/ttyUSB1` can swap after reconnecting. Some devices appear as `/dev/ttyACM0`. Record which path belongs to each instrument.

On Ubuntu/Debian, serial access commonly requires membership in the `dialout` group:

```bash
sudo usermod -aG dialout "$USER"
```

Log out completely and log back in afterward. Check membership with `id -nG`. On other distributions, check the device's owning group and use the distribution's serial-access procedure. Avoid granting everyone write access with `chmod 666`.

Close other programs using these ports. If a port is unexpectedly busy, check for GPS services or ModemManager before changing system services.

### Instrument Settings

- **GPS:** configure checksummed NMEA GGA and HDT output on the same serial feed. Match the receiver's configured baud rate and framing. The parser accepts recognized talker prefixes, including GN GGA and HE HDT, not just GP. HDT must report true heading; course over ground from RMC/VTG is not a substitute. Many single-antenna GPS receivers cannot supply true heading while stationary.
- **SeaTrac X150:** the developer guide specifies a default of **115200 baud, 8 data bits, no parity, 2 stop bits, no flow control (8N2)**. Verify the actual configured baud rate. The app explicitly uses two stop bits.
- **ROV X110:** verify its beacon ID and compatible acoustic settings. Enter that ID in **ROV ID**; 2 is only a default.
- **Ping requests:** the app actively sends USBL or enhanced USBL requests when **Send pings** is checked. Its position decoder handles `CID_PING_RESP` (`0x42`), not ECHO, NAV, TRACK, or generic diagnostic fixes. Unrelated messages remain visible/logged but do not produce positions.

## Coordinate and Depth Conventions

SeaTrac's `ACOFIX_T` position fields are Easting/Northing relative to the local beacon, already rotated using its magnetic heading and attitude. They are **not raw forward/starboard offsets**. The library reverses the fix's reported yaw to obtain horizontal local offsets, applies a mounting yaw correction, and rotates using the boat's true heading before projecting onto WGS84.

`solve()` accepts these optional installation corrections:

- `mounting_yaw_deg`: clockwise angle from the boat's forward axis to the local beacon's forward axis. Zero assumes alignment.
- `lever_forward_m` and `lever_starboard_m`: displacement from the GPS antenna to the topside acoustic head in boat coordinates, positive forward and starboard respectively.

The GUI exposes these as **Mount yaw**, **GPS to head forward**, and **GPS to head starboard**. Confirm signs and heading alignment against known positions before deployment. This uses the attitude-compensated horizontal position; it is not full three-dimensional lever-arm or vessel-motion compensation.

The bridge uses the latest accepted GPS/heading observations received before the acoustic response and checks their receive age with a monotonic clock. It does not interpolate, compensate acoustic travel latency, or synchronize instrument clocks. Invalid GGA/HDT messages invalidate the corresponding cached observation immediately. Stale or missing data pause output; the app never retransmits an old position as a new fix.

SeaTrac position depth is positive down from the surface. Enhanced fixes use the remote pressure-derived depth; standard USBL fixes use an acoustically resolved depth. `make_gga()` writes **altitude = surface_msl_m - depth_m**, because GGA's altitude field is height above mean sea level, not positive-down depth. The default assumes the water surface is at 0 m MSL. Supply a suitable surface elevation where necessary, and verify how the pilot software interprets altitude. This value is not bottom clearance.

The generated sentence has a checksum and CR/LF termination. Its fix-quality field is 1 as a compatibility convention for the derived position, with zero satellites and blank HDOP/geoid separation; it is not a claim that the submerged ROV has a GPS fix or a measure of acoustic accuracy. Check that the pilot software accepts these fields. GGA time is the host's UTC receive time for the acoustic line, not the boat's earlier GPS time. Keep the Linux system clock synchronized.

## UDP Output and Logs

Use `127.0.0.1:27000` only when the pilot software runs on the **same Linux computer**. Otherwise enter the pilot computer's reachable numeric IPv4 address and configured UDP port, and check its firewall. The app sends one ASCII GPGGA sentence per accepted acoustic position, as one UDP datagram; it does not listen for UDP acknowledgements. A successful send does not prove that the pilot received or accepted it.

**Configure the pilot software's navigation timeout.** The app stops sending when data is stale or rejected; it does not send an invalid-fix heartbeat. The pilot must not continue treating its last received position as current indefinitely.

CSV files contain UTC receive timestamps, the session start time, raw GPS GGA, raw heading, raw SeaTrac responses, boat coordinates, heading/input ages, accepted ROV coordinates/depth/offsets, generated GGA, and UDP send status. Every complete incoming serial line is logged, including unrelated or rejected messages; the `raw_input` and `event` columns identify the actual line source. Other raw columns retain the latest corresponding observations for correlation. START records include all session settings as JSON; transmitted commands, state transitions, ping timeouts, errors, and Stop are also recorded. Line endings are retained in quoted CSV fields, so use a CSV reader rather than treating each physical text line as one record.

Rows are flushed after each write, but not forced to physical disk with `fsync`; abrupt power loss can still lose buffered filesystem data. Serial disconnects, UDP send failures, log failures, oversized serial lines, or acquisition queue overflow stop the session and surface an error. Stop/forced quit can leave queued or partial serial input unprocessed. Inspect the error and log before restarting.

## Commissioning on the Linux Device

1. Run the tests and open the GUI on the actual desktop. Confirm both USB serial devices are accessible without root.
2. Start acquisition and verify checksummed GGA and true HDT in the left pane. Confirm that GPS no-fix conditions or heading loss pause new output.
3. Verify PING acknowledgements/responses and the correct source ID in the right pane. Resolve busy/timeout/CRC errors before proceeding.
4. With known geometry, compare calculated position and depth to independent measurements. Verify forward/starboard signs, heading/mounting offsets, lever arms, and the MSL/depth convention.
5. Confirm the pilot software receives GPGGA on the selected UDP address/port and marks navigation stale when transmission stops. UDP delivery is not acknowledged by this app.
6. Stop the bridge and inspect a CSV with a proper CSV viewer. Confirm raw inputs, solution coordinates, UTC timestamps, and send status are present.

Do not use the synthetic example as an operational navigation source. Hardware accuracy and installation alignment require independent checks.

## Troubleshooting

- **`ModuleNotFoundError`:** activate `.venv` and rerun `python -m pip install -r requirements.txt` from this folder.
- **Python errors at `| None`:** use Python 3.10 or newer and recreate the virtual environment with that interpreter.
- **Serial permission denied:** verify the device path, group permissions, and that you logged in again after adding group membership.
- **CRC mismatch or unreadable serial data:** check baud rate, SeaTrac 8N2 framing, complete line reception, and whether another process is reading the same device.
- **No accepted acoustic fix:** check source ID and position-valid flags. The parser returns `None` for other commands, fixes without position, other source IDs, and fixes rejected by SeaTrac's position filter.
- **No window:** launch `python main.py`, not `navigation.py`, from a graphical desktop with Tkinter installed. A `no display name` error usually means the session is headless.
- **Waiting for HDT:** verify that your GPS/heading instrument actually outputs true heading on this serial feed. Position or course-over-ground sentences alone cannot satisfy it.
- **Ping rejected/busy or timed out:** confirm the target ID, acoustic settings, range, and sound-speed setup. Ensure another controller is not issuing competing requests and that the host reply timeout is not shorter than the beacon's acoustic range timeout.
- **Pilot shows no position:** confirm the destination IP/port, pilot UDP listener, firewall, and whether it accepts zero satellites/blank HDOP in a derived GGA solution. No output is expected until all freshness gates pass.

## Protocol Reference

[Blueprint Subsea SeaTrac Developer Guide, revision 13](https://www.blueprintsubsea.com/downloads/seatrac/UM-140-D00221-13.pdf): sections 5.1-5.6 (serial framing and CRC), 6.3.13 (`ACOFIX_T`), and 8.1 (PING messages).