# bCNC-QT — Project Instructions for Claude

## Project Overview

CNC controller GUI app (Python 3.8+, PySide6). Qt-only fork of
[vlachoudis/bCNC](https://github.com/vlachoudis/bCNC) — all Tkinter code
has been removed.

- **Entry point:** `bCNC/qt/app.py` — `MainWindow` owns `Sender` (composition)
- **Launch:** `python -m bCNC` or `python -m bCNC.qt.app`

## Critical Import Order

`Helpers.py` **must** be imported before `utils_core.py` — it installs the `_()` builtin via `gettext.install()`. Every file that uses `_()` relies on this.

```python
import Helpers  # FIRST — installs _() builtin
import utils_core as Utils  # config helpers, metadata, path utilities
from CNC import CNC
```

`tools_base.py` contains all tool classes (`_Base`, `DataBase`, `Plugin`, and 15 built-in tools). `ToolsPage.py` is a thin re-export shim (`from tools_base import *`) kept for plugin compatibility.

## Architecture

### Composition Pattern

```
QApplication
  └─ MainWindow(QMainWindow)
       ├─ self.sender = Sender()        # backend (serial, G-code queue)
       ├─ self.signals = AppSignals()    # central signal hub (45+ signals)
       ├─ self.serial_monitor            # QTimer → polls Sender → emits signals
       ├─ self.canvas_panel              # central widget (QGraphicsView)
       └─ left dock (tabs on top):
            ├─ self.control_panel        # DRO, connection, jog
            ├─ self.editor_panel         # QTreeView block/line editor
            ├─ self.probe_panel          # 5 tabs: Probe/Autolevel/Camera/Orient/Tool
            ├─ self.tools_panel          # plugins, CAM ops
            └─ self.terminal_panel       # serial log, command entry
```

### CNC.vars — Global State Bus

`CNC.vars` is a class-level dict on `CNC` (CNC.py ~line 681). All machine state flows through it:
- Sender's serial thread **writes** (from GRBL responses)
- SerialMonitor **reads** and emits Qt signals
- UI panels **read** in signal handlers, **write** before sending commands

Key vars: `wx/wy/wz` (work pos), `mx/my/mz` (machine pos), `state`, `prbx/prby/prbz`, `prbfeed`, `prbcmd`, `TLO`, `safe`

### Signal Flow

No direct panel-to-panel communication. Everything goes through `AppSignals`:

```
Sender (backend thread) → SerialMonitor._poll() (QTimer 200ms) → Qt signals → panels
```

## Key File Locations

| Layer | Files |
|-------|-------|
| Backend | `Sender.py`, `CNC.py`, `EventBus.py`, `MachineState.py`, `CommandDispatcher.py`, `FileManager.py`, `utils_core.py`, `tools_base.py` |
| Canvas math | `ViewTransform.py`, `PathGeometry.py`, `SceneGraph.py` |
| Qt UI | `qt/{app,signals,main_window,canvas_widget,control_panel,terminal_panel,serial_monitor,editor_panel,editor_model,probe_panel,autolevel_panel,camera_overlay,camera_tab,orient_overlay,orient_tab,tools_manager,tools_panel}.py` |
| Controllers | `controllers/{GRBL0,GRBL1,SMOOTHIE,G2Core}.py` |
| Plugins | `plugins/` (42+ CAM/utility plugins) |

## Conventions

### Adding a New Panel/Tab

1. Create `bCNC/qt/my_panel.py`
2. Constructor: `__init__(self, sender, signals, parent=None)`
3. Connect to signals in constructor
4. Add `loadConfig()` / `saveConfig()` using `Utils.getFloat/setFloat` etc.
5. In `main_window.py`: create dock, add to View menu, wire signals, save on close

### Adding a New Signal

1. Add to `AppSignals` in `signals.py` with a comment
2. Emit from the appropriate source (usually `serial_monitor.py` or a panel)
3. Connect in the consuming panel's constructor

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase` — panels end with `Panel` or `Tab`
- Signals: `snake_case`
- Handlers: `_on_<action>` for signal/button slots
- Config keys: match existing keys in `[Section]` for compatibility

### Sending G-code

```python
self.sender.sendGCode("G0 X10 Y20")             # single command
self.sender.runLines(["G91", "G38.2 Z-10 F50"])  # multi-line sequence
```

Special prefixes in runLines: `%wait`, `%global var; var=expr`, `%update var`, `[var]` substitution.

## Testing

### Syntax check
```bash
python -c "import py_compile; py_compile.compile('bCNC/qt/my_file.py', doraise=True)"
```

### Import check
```bash
PYTHONPATH=bCNC:bCNC/lib python -c "import Helpers; from bCNC.qt.my_module import MyClass; print('OK')"
```

### Full integration test
```bash
PYTHONPATH=bCNC:bCNC/lib:bCNC/controllers:bCNC/plugins python -c "
import os, sys; os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import Helpers; import utils_core as Utils; Utils.loadConfiguration()
from PySide6.QtWidgets import QApplication; app = QApplication(sys.argv)
from Sender import Sender; sender = Sender()
sender._ui_set_status = lambda msg: None
sender._ui_disable = lambda: None
sender._ui_enable = lambda: None
sender._ui_show_info = lambda t, m: None
from qt.main_window import MainWindow; w = MainWindow(sender)
tk = [m for m in sys.modules if 'tkinter' in m.lower()]
assert not tk, f'tkinter loaded: {tk}'
print('OK')
"
```

### Unit tests
```bash
python -m unittest tests.test_qt_control_panel -v
```

### Launch the app
```bash
python -m bCNC
```

## Remaining Work

- **Advanced toolbar/ribbon** — configurable groups (tracked in DEV-GUIDE.md)

## Documentation Files

- `CHANGELOG.md` — feature changelog (update when adding features)
- `USER-GUIDE.md` — end-user guide for the Qt interface
- `DEV-GUIDE.md` — developer guide with architecture and conventions
- `README.md` — project overview

Update all four when adding significant new features.
