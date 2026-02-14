# bCNC Qt Interface — User Guide

The Qt interface is an experimental alternative to the original Tkinter UI.
It provides the same core CNC workflow with dockable panels and a tabbed layout.

## Launching

**Quick start (venv recommended):**

    python -m venv .venv
    source .venv/bin/activate        # Linux/macOS (.venv\Scripts\activate on Windows)
    pip install -r requirements.txt  # core dependencies
    pip install PySide6              # Qt toolkit

    python -m bCNC.qt.app            # launch Qt interface
    python -m bCNC.qt.app file.gcode # launch Qt and open a file
    python -m bCNC                   # launch Tkinter interface (original)

Both commands should be run from the repository root.

The Qt app reads the same `~/.bCNC` configuration file as the Tkinter version.
Settings are shared — you can switch between UIs without losing configuration.

## Window Layout

The main window has two columns:

- **Left sidebar** — Tabbed dock (tabs on top) with Control, Editor, Probe,
  Tools, and Terminal panels
- **Central area** — Canvas showing toolpaths, probe data, and gantry position

All dock tabs can be dragged or closed via the View menu.
Window size, position, and dock arrangement are saved on close and
restored on the next launch.

## Control Panel (Left Sidebar)

### Connection
- Select serial port, baud rate, and click **Connect**
- Status indicator shows connection state (red/green)

### DRO (Digital Readout)
- Displays work coordinates (X, Y, Z) and machine coordinates
- Values update in real time when connected
- Fonts are configurable via the `[Font]` section in config: `dro.wpos` for work
  positions (default: `Sans,12,bold`), `dro.mpos` for machine positions (default:
  `Sans,12`). Format: `FontFamily,size[,bold][,italic]`
- **WCS selector** (G54-G59) — row of toggle buttons to switch workspace
  coordinate systems. The active WCS is highlighted automatically when the
  machine reports its parser state. Clicking a button sends the WCS command
  and refreshes the DRO.
- **Zero buttons** (X=0, Y=0, Z=0) — zero individual axes via G10 L20
- When 6-axis mode is enabled (`enable6axisopt=1` in config), A/B/C axes
  are shown with additional zero buttons (A=0, B=0, C=0)

### Spindle / Overrides
Real-time machine state and override controls.

**Readouts (updated live from GRBL status reports):**
- **Feed** — current feed rate (mm/min) and feed override percentage
- **Spindle** — current spindle speed (RPM) and spindle override percentage
- **Rapid** — rapid override percentage

**Override buttons:**
- **F-10 / F+10** — decrease/increase feed override by 10% (range 10-200%)
- **S-10 / S+10** — decrease/increase spindle override by 10% (range 10-200%)
- **Rapid** — cycle rapid override: 100% → 50% → 25% → 100%
- **Reset** — reset all overrides to 100%

**Spindle and coolant:**
- **Spindle ON/OFF** — toggle spindle (sends M3 S{rpm} or M5)
- **Flood** — turn on flood coolant (M8)
- **Mist** — turn on mist coolant (M7)
- **Cool Off** — turn off all coolant (M9)

All spindle and coolant commands are guarded — they are ignored when the
machine is not connected or not yet homed.

### Jog
- Arrow buttons for X/Y movement, Z+/Z- for vertical
- Step size selector (0.1, 1.0, 10.0 mm)
- When 6-axis mode is enabled, A+/A-/B+/B-/C+/C- buttons appear below the XY/Z pad
- **Home** — send homing cycle ($H)
- **Unlock** — clear alarm ($X)
- **Reset** — soft reset
- **Home All** — home all axes

### Custom Buttons
A grid of user-configurable macro buttons between Spindle/Overrides and Execution.
Each button can run multi-line G-code commands with variable substitution (`[safe]`,
`[prbx]`, etc.).

- **Click** a button to execute its command (empty buttons open the edit dialog)
- **Right-click** any button to edit its name, tooltip, and command
- Buttons are stored in the `[Buttons]` config section, shared with the Tkinter UI
- Commands are executed directly and support all Sender features
  (G-code, SENDHEX, `%wait`, variable substitution)

## Canvas (Center)

- **Scroll wheel** — zoom in/out
- **Middle-click drag** — pan
- **Click on path** — select block (highlights in editor)
- **Ctrl+click** — add to selection
- **Fit** button in toolbar — zoom to fit all geometry
- **Ctrl+0** or View > Fit to Content — fit all geometry
- Auto-fits to content when a file is loaded or imported

The canvas shows:
- Toolpaths colored by block (rapid=red, feed=blue/green)
- Gantry position crosshair (updates when connected)
- Probe data overlay (after autolevel scan)

## Editor Panel (Left Sidebar)

A tree view of G-code blocks and their lines.

### Expand / Collapse
- Double-click a block row to toggle its lines visible or hidden
- The tree arrow and the Expand toolbar button also work
- Block expand state is preserved across edits

### Selection
- Click a block to select it (highlights on canvas)
- Ctrl+click to multi-select
- Selection syncs bidirectionally with canvas

### Editing
- **Right-click context menu** — cut, copy, paste, delete, enable/disable
- **Edit menu** — Undo (Ctrl+Z), Redo (Ctrl+Shift+Z)
- Standard clipboard shortcuts: Ctrl+X, Ctrl+C, Ctrl+V

### File Operations
- **Ctrl+N** — New file
- **Ctrl+O** — Open (supports .ngc, .nc, .gcode, .dxf, .svg, .stl)
- **Ctrl+S** — Save
- **Ctrl+Shift+S** — Save As
- **Ctrl+I** — Import (merge into current file)
- **File > Open Recent** — recent files list

## Probe Panel (Left Sidebar)

The Probe dock has shared settings at the top and five tabs below.

### Shared Probe Settings (always visible)
- **Fast Probe Feed** — feed rate for initial fast probe pass
- **Probe Feed** — feed rate for final accurate probe
- **TLO** — Tool Length Offset display, **Set** sends G43.1Z to machine
- **Probe Command** — G38.2 through G38.5 selection

### Probe Tab
Single-direction probing and coordinate recording.

**Probe section:**
- Three direction fields (X, Y, Z) — enter distance to probe, leave empty to skip axis
- **Auto goto** — automatically move to probe contact point after probing
- **Goto** — rapid move to last probe coordinates (G53 G0)
- **Probe** — sends probe command (e.g. G38.2 X-10 F50)
- Result labels show last probe X/Y/Z coordinates

**Center section:**
- Enter ring/bore diameter, click **Center** to run a 4-touch center-finding sequence
- Probes left/right in X, then forward/back in Y, moves to computed center

**Record section:**
- Record machine movements as G-code by jogging to positions:
- **Z** checkbox — include Z coordinate in recorded moves
- **RAPID** — record G0 move to current position
- **FEED** — record G1 move to current position
- **POINT** — record safe-Z lift, rapid to position, plunge to Z0
- **CIRCLE** — record a full circle (G02) at current position with given radius
- **FINISH** — append M5, safe-Z retract, M2 (end program)

### Autolevel Tab
Grid-based Z surface scanning for PCB milling and similar work.

**Grid Configuration:**
- X/Y min, max, step (computed), N (number of points)
- Z min (probe depth limit), Z max (retract height)

**Actions:**
- **Get Margins** — fill grid bounds from loaded G-code file extents
- **Scan Margins** — probe the four corners to verify grid limits
- **Set Zero** — set current XY as autolevel Z reference
- **Clear** — delete all probe data
- **Autolevel** — modify loaded G-code to follow the probed surface
- **Scan** — run the full grid probe sequence

Status label shows scan progress (e.g. "15 / 25 points").

### Camera Tab
Live camera overlay for visual alignment, edge finding, and camera-to-spindle
offset registration. Requires OpenCV (`pip install opencv-python`).

**Camera Settings:**
- **Location** — where the camera feed appears on the canvas:
  - *Gantry* — follows the gantry position (with optional offset)
  - *Top-Left, Top, Top-Right, Left, Center, Right, Bottom-Left, Bottom,
    Bottom-Right* — fixed viewport anchor positions
- **Rotation** — rotate the camera image (degrees)
- **Haircross** — X/Y pixel offset for centering the crosshair on the image
- **Scale** — pixels-per-unit scaling factor for the camera feed
- **Crosshair** — diameter of the inner crosshair circle (machine units);
  **Get** reads the active endmill diameter
- **Offset** — DX, DY, Z offset from camera to spindle (machine units)

**Registration (camera-to-spindle offset):**
1. Jog the spindle to a visible target point, click **1. Spindle**
2. Jog until the camera crosshair is on the same point, click **2. Camera**
3. The DX/DY offset fields are computed automatically

**Controls:**
- **Switch To Camera** — toggles coordinate system between spindle and camera
  position (sends G92/G92.1 to shift work coordinates by the offset)
- **Edge** — enable Canny edge detection overlay on the video feed
- **Freeze** — blend-freeze the current frame as a semi-transparent overlay
- **Save** — save the current camera frame as `cameraNN.png`

**On/Off:**
- **Camera ON** — start live video capture and display on the canvas
- **Camera OFF** — stop capture and remove overlay from the canvas

If OpenCV is not installed, Camera ON shows a warning message (no crash).

### Orient Tab
Marker-based workpiece alignment. Place marker pairs that map machine positions
to G-code design positions, solve for rotation and translation, then transform
selected G-code blocks to align with the physical workpiece.

**Markers section:**
- **Marker** spinner — navigate through markers (1-based)
- **GCode** (X, Y) — the design position in the G-code file
- **WPos** (X, Y) — the actual machine position of that feature
- **Add** — enter add-marker mode: cursor changes to crosshair, click on the
  canvas to place a marker at the clicked G-code position using the current
  machine work position
- **Delete** — remove the currently selected marker
- **Clear** — remove all markers (with confirmation)

**Results section:**
- **Angle** — computed rotation angle in degrees
- **Offset** — computed X/Y translation offset
- **Error** — min, average, and max residual error across all markers
- **Orient** — apply the computed rotation+translation to selected blocks
  in the Editor (requires at least 2 markers and a valid solution)

**Canvas overlay:**
- Green crosses mark machine positions
- Red crosses mark G-code positions
- Blue dashed lines connect each pair
- Red circles show error magnitude (when errors are computed)
- Selected marker is drawn with thicker lines

**Workflow:**
1. Load a G-code file and identify reference features (holes, corners, etc.)
2. Jog the machine to each reference feature and click **Add** on the canvas
   at the corresponding G-code location — repeat for 2+ points
3. The angle, offset, and error are computed automatically
4. Select blocks in the Editor, click **Orient** to transform the G-code

Orient data can be saved/loaded as `.orient` files (one marker per line:
`xm ym x y`).

### Tool Tab
Manual tool change management for multi-tool jobs.

**Policy** — how M6 tool change commands are handled:
- Send M6 commands (pass through to controller)
- Ignore M6 commands
- Manual Tool Change (WCS) — pause, change, re-probe with work coordinates
- Manual Tool Change (TLO) — pause, change, re-probe with tool length offset
- Manual Tool Change (NoProbe) — pause for manual change, no re-probing

**Pause** — when to pause during tool change:
- ONLY before probing
- BEFORE & AFTER probing

**Positions:**
- **Change** (MX, MY, MZ) — machine position to move to for tool changes
- **Probe** (MX, MY, MZ) — machine position of the tool length probe
- **Get** buttons read current machine position into the fields

**Distance** — how far to probe downward when measuring tool length

**Calibrate** — runs a multi-speed probe sequence:
1. Move to tool change Z, then change XY, then probe XY, then probe Z
2. Fast probe down, retract, repeat with decreasing feed rates
3. Final slow probe, record tool height and machine Z
4. Return to tool change position

**Change** — run the full tool change cycle (delegates to CNC.toolChange)

## Tools Panel (Left Sidebar)

The Tools panel provides tool databases, CAM operations, and access to all plugins.
Select a tool or plugin from the categorized tree, configure its settings in the
form below, and click Execute.

### Tool Selector Tree

Tools are organized into categories:

- **Config** — CNC, Controller, Camera, Shortcut, Font, Color, Events
- **Database** — Material, EndMill, Stock (with Add/Delete/Clone/Rename buttons)
- **CAM** — Cut, Drill, Profile, Pocket, Tabs, plus CAM plugins (Trochoidal, etc.)
- **Generator** — SimpleLine, SimpleRectangle, Bowl, Spirograph, Gear, etc.
- **Artistic** — Halftone, Sketch, Pyrograph, etc.
- **Macros** — remaining plugins

### Variable Form

Each tool's settings are shown as a dynamic form. Field types include spinboxes
for numbers, checkboxes for booleans, dropdowns for lists/databases, color pickers,
and file browsers. Values are saved to config on tool switch or panel close.

### CAM Operations

Select one or more blocks in the Editor, then choose a CAM tool and click Execute:

- **Cut** — cut along selected paths with configurable strategy (flat, helical, ramp),
  depth, step-down, and bottom finishing passes
- **Drill** — convert closed paths to drill points at their center, with optional
  peck drilling, dwell, and depth settings
- **Profile** — generate an offset profile (inside or outside) of selected paths,
  with overcut, direction, and endmill compensation
- **Pocket** — clear all material inside selected closed paths using the configured
  endmill diameter and stepover percentage
- **Tabs** — add holding tabs (islands) along selected paths to keep parts in place
  during cutting, with configurable count, spacing, width, and height

### Database Tools

Material, EndMill, and Stock tools have a database of named entries.
Use the buttons below the tree to manage entries:

- **Add** — create a new entry with default values
- **Delete** — remove the current entry
- **Clone** — duplicate the current entry
- **Rename** — change the name of the current entry

### Plugins

All 42+ external plugins are loaded automatically from the `plugins/` directory.
Each plugin appears in the tree under its declared group. Select a plugin, fill in
its parameters, and click Execute to run it. The help panel at the bottom shows
documentation for the selected tool.

## Terminal Panel (Left Sidebar)

- **Buffer** — shows serial buffer status
- **Terminal log** — color-coded serial traffic (sent/received/ok/error)
- **Command entry** — type G-code or macros (RESET, HOME, RUN, etc.)
- Up/Down arrow keys for command history

## Help Menu

- **Documentation** (F1) — opens the bCNC GitHub page in your web browser
- **Check for Updates** — queries PyPI for the latest bCNC release; if a newer
  version is available, offers to open the download page
- **About bCNC** — shows version, author, and project links

## Web Pendant

The web pendant is a lightweight HTTP server that provides a mobile-friendly
interface for controlling the CNC machine from a phone or tablet.

- **Machine > Start Pendant** — starts the pendant server and shows the URL
  (e.g. `http://hostname:8080`). If already running, offers to open it locally.
- **Machine > Stop Pendant** — stops the pendant server

The pendant port defaults to 8080 and can be configured in `[Connection]
pendantport` in the config file.

## Running a Job

1. Open a G-code file (Ctrl+O)
2. Connect to your machine (Control panel > Connect)
3. Optionally run autolevel scan (Probe panel > Autolevel tab)
4. Click **Run** in the toolbar (or toolbar button)
5. Progress bar appears in status bar during execution
6. **Pause** / **Stop** to control execution

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+I | Import file |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z | Redo |
| Ctrl+X | Cut |
| Ctrl+C | Copy |
| Ctrl+V | Paste |
| Ctrl+0 | Fit canvas to content |
| F1 | Open documentation |
| Ctrl+Q | Quit |

## Configuration

All settings persist to `~/.bCNC` (INI format), shared with the Tkinter UI.
Probe settings are in the `[Probe]` section, connection in `[Connection]`, etc.
On close, the Qt app saves current panel values to the config file.
