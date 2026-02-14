bCNC-QT
=======

**Qt-only fork of [vlachoudis/bCNC](https://github.com/vlachoudis/bCNC)**
**Original author:** Vasilis Vlachoudis ([@vlachoudis](https://github.com/vlachoudis))

An advanced fully featured g-code sender for GrblHAL / GRBL. Cross-platform
(Windows, Linux, Mac), written in Python with a PySide6 (Qt) interface.
Includes autoleveling, g-code editing, digitizing, CAM operations, camera
alignment, and 42+ plugins.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS (.venv\Scripts\activate on Windows)
pip install -e .             # core deps (pyserial, numpy, Pillow, opencv, etc.)
pip install PySide6          # Qt toolkit
```

### Launch

```bash
python -m bCNC                   # launch the app
python -m bCNC.qt.app            # alternative entry point
python -m bCNC.qt.app file.gcode # open a file on startup
```

All commands should be run from the repository root.

### Dependencies

- **Python 3.8+**
- **PySide6** — Qt toolkit
- **pyserial** — serial communication
- **numpy** — numeric computation
- **Pillow** — image processing (autolevel height map)
- **opencv-python** (optional) — camera overlay, edge detection

## Features

- **Dockable panel layout** — tabbed sidebar with canvas center area, persistent window state
- **3-axis and 6-axis** GUI modes (XYZ + ABC)
- **Digital Readout (DRO)** — live work/machine position display with configurable fonts
- **Import/export** G-code (`.ngc`, `.nc`, `.gcode`), DXF, SVG files
- **3D mesh slicing** — STL and PLY files (requires `numpy-stl`)
- **Fast G-code sender** — works on Raspberry Pi and old hardware
- **Workspace selection** — G54-G59 quick-switch with live highlight
- **User-configurable macro buttons** — multi-line G-code, right-click to edit
- **Spindle / override controls** — feed, spindle, rapid override with real-time display
- **Probing:**
  - Single-direction probing with auto-goto
  - Center finder with probing ring
  - **Autoleveling** — Z-probe grid scan with heatmap display
  - Jog-and-record digitizer (with camera support)
  - **Manual tool change** with automatic tool length probing
- **Camera alignment** — live OpenCV overlay, 10 anchor modes, edge detection,
  camera-to-spindle offset registration
- **Orientation alignment** — marker-based workpiece alignment with least-squares solve
- **CAM operations** — cut, drill, profile, pocket, tabs + 42 plugins
- **G-code editor** — tree view with block/line hierarchy, context menu, clipboard, undo/redo
- **Serial terminal** — color-coded log with command entry and history
- **Web pendant** — mobile-friendly HTTP interface for phone/tablet control

## Motion Controller Configuration

- We recommend **FluidNC** ([github](https://github.com/bdring/FluidNC),
  [wiki](http://wiki.fluidnc.com)) for new builds
- **GrblHAL** ([github](https://github.com/grblHAL)) is fully supported
  (original GRBL also works but is reaching end-of-life on 8-bit MCUs)
- GRBL should use **MPos** reporting: set `$10=3` (or `$10=1` as fallback)
- Default units are millimeters — ensure `$13=0` in GRBL
- See [GRBL v1.1 Configuration](https://github.com/gnea/grbl/wiki/Grbl-v1.1-Configuration)
  and [GrblHAL Compatibility Level](https://github.com/grblHAL/core/wiki/Compatibility-level)

## Configuration

Settings are stored in `~/.bCNC` (INI format). Most parameters can be modified
from the Tools panel (Config / Controller). 6-axis mode can be enabled in
Config (requires restart).

The default configuration template is `bCNC.ini` in the installation directory.

## Debugging

Log serial communication by changing the port to:

```
spy:///dev/ttyUSB0?file=serial_log.txt&raw
spy://COM1?file=serial_log.txt&raw
```

If no file is specified, the log goes to stderr. The `raw` option outputs
data directly instead of hex dump. See [pyserial URL handlers](https://pyserial.readthedocs.io/en/latest/url_handlers.html#spy).

## Documentation

- [USER-GUIDE.md](USER-GUIDE.md) — end-user guide for the Qt interface
- [DEV-GUIDE.md](DEV-GUIDE.md) — developer guide with architecture and conventions
- [CHANGELOG.md](CHANGELOG.md) — feature changelog

## See Also

- [cnc-simulator](https://harvie.github.io/cnc-simulator) ([github](https://github.com/Harvie/cnc-simulator))
- [CAMotics](https://camotics.org)
- [FreeCAD](https://freecad.org)

## Disclaimer

The software is made available "AS IS". It seems quite stable, but it is in
an early stage of development. Hence there should be plenty of bugs not yet
spotted. Please use/try it with care.
