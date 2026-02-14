# bCNC Qt Interface — Developer Guide

Architecture, conventions, and how to extend the Qt interface.

## Getting Started

```bash
git clone https://github.com/vlachoudis/bCNC.git
cd bCNC
python -m venv .venv
source .venv/bin/activate        # Linux/macOS (.venv\Scripts\activate on Windows)
pip install -r requirements.txt  # core deps (pyserial, numpy, etc.)
pip install PySide6              # Qt toolkit

python -m bCNC                   # launch Tkinter UI
python -m bCNC.qt.app            # launch Qt UI
python -m bCNC.qt.app file.gcode # launch Qt UI and open a file
```

Both commands should be run from the repository root.

## Repository Structure

```
bCNC/
  __main__.py              # Tkinter entry point
  Sender.py                # Backend: serial comm, G-code queue, run loop
  CNC.py                   # CNC class: G-code parser, vars dict, tool change
  Helpers.py               # Must be imported first (installs _() builtin)
  utils_core.py            # Config helpers, metadata, paths (no tkinter)
  Utils.py                 # Re-exports utils_core + tkinter UI utilities
  tools_base.py            # Tool base classes + built-in tools (no tkinter)
  ToolsPage.py             # Re-exports tools_base + lazy-loads Tkinter UI

  # Phase 1 — Decoupled backend (toolkit-independent)
  EventBus.py              # Pub/sub signal system
  MachineState.py          # Observable CNC.vars wrapper, batch updates
  CommandDispatcher.py     # G-code operation routing
  FileManager.py           # File I/O with EventBus notifications

  # Phase 2 — Canvas math (toolkit-independent)
  ViewTransform.py         # 3D→2D projection, coordinate transforms
  PathGeometry.py          # Grid, margin, axis geometry generation
  SceneGraph.py            # Drawing primitives, scene layers

  # Phase 3 — Qt UI
  qt/
    __init__.py
    app.py                 # QApplication entry point
    signals.py             # AppSignals — central signal hub
    main_window.py         # QMainWindow, menus, toolbar, docks
    canvas_widget.py       # QGraphicsView canvas, toolpath rendering
    control_panel.py       # DRO, connection, jog controls
    terminal_panel.py      # Serial log, command entry
    serial_monitor.py      # QTimer polling loop (Sender → signals)
    editor_model.py        # QAbstractItemModel for block/line tree
    editor_panel.py        # QTreeView editor with context menu
    probe_panel.py         # ProbePanel (tabs), ProbeCommonWidget, ProbeTab, ToolTab
    autolevel_panel.py     # AutolevelTab (grid scan)
    camera_overlay.py      # CameraOverlay — video feed on QGraphicsScene
    camera_tab.py          # CameraTab — settings, controls, registration
    orient_overlay.py      # OrientOverlay — marker pairs on QGraphicsScene
    orient_tab.py          # OrientTab — marker management, solve, apply
    tools_manager.py       # ToolsManager — Tkinter-free tool/plugin loader
    tools_panel.py         # AppProxy, VariableForm, ToolsPanel

  # Tkinter UI (original, still functional)
  bmain.py                 # Application(Tk, Sender)
  ControlPage.py           # DRO, jog, state
  EditorPage.py            # G-code list editor
  ProbePage.py             # Probe, autolevel, camera, tool
  FilePage.py              # File ops, pendant, serial config
  TerminalPage.py          # Serial terminal
  ToolsPage.py             # Re-exports tools_base + lazy Tkinter UI classes
  CNCCanvas.py             # Tkinter canvas

  controllers/             # GRBL0, GRBL1, SMOOTHIE, G2Core
  plugins/                 # 43 CAM/utility plugins
  lib/                     # tkExtra, rexx, etc.
```

## Architecture Overview

### Composition, Not Inheritance

The Tkinter app uses `Application(Tk, Sender)` — the window IS the sender.
The Qt app uses composition: `MainWindow` owns a `Sender` instance.

```
QApplication
  └─ MainWindow(QMainWindow)
       ├─ self.sender = Sender()        # backend
       ├─ self.signals = AppSignals()    # signal hub
       ├─ self.serial_monitor            # QTimer → signals
       ├─ self.canvas_panel              # central widget
       └─ left dock (tabs on top):
            ├─ self.control_panel        # DRO, connection, jog
            ├─ self.editor_panel         # block/line tree editor
            ├─ self.probe_panel          # probe/autolevel/camera/orient/tool
            ├─ self.tools_manager        # ToolsManager (tool/plugin loader)
            ├─ self.tools_panel          # plugin UI, form builder
            └─ self.terminal_panel       # serial log, command entry

canvas_panel
  ├─ self.camera_overlay                 # CameraOverlay (scene items, QTimer)
  └─ self.orient_overlay                 # OrientOverlay (marker scene items)

probe_panel
  ├─ self.camera_tab                     # CameraTab (wired to camera_overlay)
  └─ self.orient_tab                     # OrientTab (wired to orient_overlay + editor)
```

### Signal Flow

The serial monitor polls Sender queues on a QTimer and emits Qt signals.
Panels connect to signals — no direct panel-to-panel communication.

```
Sender (backend thread)
  │
  ▼
SerialMonitor._poll()          # QTimer, 200ms interval
  ├─ _drain_log()              → serial_buffer/send/receive/ok/error/run_end/clear
  ├─ _update_position()        → state_changed, position_updated
  ├─ _update_g_state()         → g_state_updated
  ├─ _update_probe()           → probe_updated
  ├─ _update_generic()         → generic_update(str)
  └─ _update_run_progress()    → run_progress, buffer_fill
```

### CNC.vars — Global State Bus

`CNC.vars` is a class-level dict on `CNC` (defined in CNC.py ~line 681).
It holds all machine state: positions, probe results, feed rates, tool data.

Key patterns:
- Sender's serial thread writes to CNC.vars (from GRBL responses)
- Serial monitor reads CNC.vars and emits signals
- UI panels read CNC.vars in signal handlers to update displays
- UI panels write to CNC.vars before sending G-code commands

Important keys:
```
wx, wy, wz          # Work position
wa, wb, wc          # Work position (ABC axes, 6-axis mode)
mx, my, mz          # Machine position
ma, mb, mc          # Machine position (ABC axes, 6-axis mode)
state, color         # Machine state string and display color
prbx, prby, prbz    # Last probe contact coordinates
prbfeed, fastprbfeed # Probe feed rates
prbcmd               # Probe command (G38.2, etc.)
TLO                  # Tool length offset
toolchangex/y/z      # Tool change machine position
toolprobex/y/z       # Tool probe machine position
tooldistance         # Tool probe distance
toolheight, toolmz   # Calibrated tool measurements
safe                 # Safe Z height
xmin, xmax, ymin, ymax  # G-code bounding box
```

### Config Persistence

Config uses Python's ConfigParser via `utils_core.py` (Qt) or `Utils.py` (Tkinter):
```python
Utils.getFloat("Probe", "feed", 10.0)    # read with default
Utils.setFloat("Probe", "feed", value)    # write
Utils.getInt("Probe", "xn", 5)
Utils.setStr("Connection", "port", "/dev/ttyUSB0")
Utils.getBool("Probe", "autogoto", False)
```

Qt files and backend files (Sender, FileManager, Camera, Pendant,
_GenericController) use `import utils_core as Utils` — same API, no tkinter
dependency.  Tkinter UI files use `import Utils` which re-exports everything
from utils_core plus tkinter-specific helpers (fonts, icons, dialogs).

Config file: `~/.bCNC` (INI format). Shared between Tkinter and Qt UIs.
Both modules share the same `config` singleton — changes made through either
are visible to the other.

### Layout Persistence

Window geometry and dock state are saved/restored via `QMainWindow.saveState()`
and `saveGeometry()`, stored as base64 in `[QtLayout]`. Every QDockWidget and
QToolBar must have a unique `objectName` set for this to work.
`Utils.saveConfiguration()` is called in `closeEvent` to flush to disk.

## Conventions

### Adding a New Panel

1. Create `bCNC/qt/my_panel.py`
2. Constructor signature: `__init__(self, sender, signals, parent=None)`
3. Store `self.sender` and `self.signals`
4. Connect to signals in constructor: `self.signals.some_signal.connect(self._handler)`
5. Add `loadConfig()` / `saveConfig()` methods using Utils
6. In `main_window.py`:
   - Import the panel
   - Create a QDockWidget, set the panel as its widget
   - Add to left dock area, tabify with existing docks
   - Add toggle action to View menu
   - Call `saveConfig()` in `closeEvent()`
   - Add to `_set_widgets_enabled()` if panel should disable during runs

### Adding a New Signal

1. Add to `AppSignals` in `signals.py` with a comment
2. Emit from the appropriate source (usually `serial_monitor.py`)
3. Connect in the consuming panel's constructor

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase` — panel classes end with `Panel` or `Tab`
- Signals: `snake_case` matching the Tkinter event they replace
- Private methods: `_on_<action>` for signal/button handlers
- Config keys: match existing Tkinter keys in `[Section]` for compatibility

### Shared Probe Settings Pattern

ProbeCommonWidget is shared across Probe, Autolevel, and Tool tabs:
```python
# In ProbePanel.__init__:
self.probe_common = ProbeCommonWidget(sender)
self.autolevel_tab.set_probe_common(self.probe_common)

# In any tab before sending probe commands:
self._probe_common.apply_to_cnc()  # pushes feed/cmd into CNC.vars
```

### Sending G-code

```python
# Single command (queued, non-blocking):
self.sender.sendGCode("G0 X10 Y20")

# Multi-line sequence (starts a run):
lines = ["G91", "G38.2 Z-10 F50", "%wait", "G90"]
if not self.sender.runLines(lines):
    QMessageBox.warning(self, "Cannot Run", "Not connected or already running.")
```

Special line prefixes in runLines sequences:
- `%wait` — wait for previous command to complete
- `%global varname; varname=expr` — set a CNC.vars variable
- `%update varname` — emit generic_update signal (triggers UI refresh)
- `[varname]` — runtime variable substitution from CNC.vars

## Module Reference

| Module | Classes | Purpose |
|--------|---------|---------|
| `app.py` | `main()` | Entry point, QApplication setup, path config |
| `signals.py` | `AppSignals` | 40+ Qt signals replacing Tk virtual events |
| `main_window.py` | `MainWindow` | Window, docks, menus, toolbar, file ops |
| `canvas_widget.py` | `CNCGraphicsView`, `CNCScene`, `CanvasPanel` | Toolpath visualization |
| `control_panel.py` | `DROWidget`, `ConnectionWidget`, `JogWidget`, `StateWidget`, `MacroEditDialog`, `MacroButtonsWidget`, `ControlPanel` | Machine control, macro buttons |
| `terminal_panel.py` | `TerminalPanel` | Serial log and command entry |
| `serial_monitor.py` | `SerialMonitor` | QTimer bridge: Sender queues → signals |
| `editor_model.py` | `GCodeTreeModel` | QAbstractItemModel for block/line tree |
| `editor_panel.py` | `EditorPanel` | QTreeView with toolbar and context menu |
| `probe_panel.py` | `ProbeCommonWidget`, `ProbeTab`, `ToolTab`, `ProbePanel` | Tabbed probe container |
| `autolevel_panel.py` | `AutolevelTab` | Grid scan config and actions |
| `camera_overlay.py` | `CameraOverlay` | Camera video feed on QGraphicsScene |
| `camera_tab.py` | `CameraTab` | Camera settings, controls, registration |
| `orient_overlay.py` | `OrientOverlay` | Orient marker pairs on QGraphicsScene |
| `orient_tab.py` | `OrientTab` | Marker management, solve, apply orient |
| `tools_manager.py` | `ToolsManager`, `_NoOpListbox` | Tkinter-free tool/plugin loader |
| `tools_panel.py` | `AppProxy`, `_EditorProxy`, `VariableForm`, `ToolsPanel` | Tool UI, form builder, plugin execution |

## What's Not Yet Ported

### Lower Priority
- **Advanced toolbar/ribbon** — Tkinter uses CNCRibbon with configurable groups

### Not Needed
- **Controllers** — work unchanged via Sender backend (GRBL0/1, SMOOTHIE, G2Core)
- **G-code parser** — CNC.py is toolkit-independent
- **Pendant backend** — Pendant.py has no UI dependency

## Testing

### Syntax check all Qt files
```bash
python -c "
import py_compile
for f in ['bCNC/qt/signals.py', 'bCNC/qt/serial_monitor.py',
          'bCNC/qt/autolevel_panel.py', 'bCNC/qt/probe_panel.py',
          'bCNC/qt/camera_overlay.py', 'bCNC/qt/camera_tab.py',
          'bCNC/qt/orient_overlay.py', 'bCNC/qt/orient_tab.py',
          'bCNC/qt/tools_manager.py', 'bCNC/qt/tools_panel.py',
          'bCNC/qt/main_window.py', 'bCNC/qt/app.py']:
    py_compile.compile(f, doraise=True)
    print(f'OK: {f}')
"
```

### Import check with real dependencies
```bash
PYTHONPATH=bCNC:bCNC/lib:bCNC/controllers:bCNC/plugins python -c "
import Helpers
from bCNC.qt.tools_panel import ToolsPanel
print('OK')
"
```

### Full integration test
```bash
python -m bCNC.qt.app
```
Verify: window opens, docks are visible, tabs work, no console errors.
