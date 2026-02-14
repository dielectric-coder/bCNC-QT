# bCNC changelog

There are too much commits, so i've created this brief overview of new features in bCNC.

## Bug Fixes & Stability (post-initial commit)

Comprehensive code review and fixes across 19 files (38 individual fixes).

- **Sender.py**: Fixed serial thread crash on empty queue (break→pass), added
  daemon thread + `threading.Event` for clean shutdown, `thread.join(timeout=2)`
  replaces `time.sleep(1)`, `os.system`→`subprocess.run` (no shell injection),
  `in ("Idle")`→`== "Idle"`, file handle leaks in loadHistory/saveHistory,
  empty-string guards in executeGcode/executeCommand, added missing
  `import subprocess`
- **main_window.py**: Thread-safe UI callbacks routed through Qt signals instead
  of direct widget mutation from background threads, blocking HTTP update check
  moved to QThread, auto-zoom on file load (including DXF/SVG import)
- **CNC.py**: `fmt()` precision format fix (`>{d}f`→`.{d}f`), feedmode stores
  `"G94"`/`"G93"` strings instead of bare ints, Probe.add() off-by-one
  (`i > xn`→`i >= xn`), Python 3 `list(map(...))`, mutable default arg
  `blocks=[]`→`blocks=None`, svgArc closure variable fix (`yc/xc`→`cy/cx`),
  Probe.load()/save() file handle leaks fixed with `with` statements
- **terminal_panel.py**: Command history Up/Down now works — event filter on
  QLineEdit instead of unreachable keyPressEvent on parent widget
- **camera_overlay.py**: `reset_items()` prevents dangling C++ pointers after
  scene.clear()
- **canvas_widget.py**: Moved 3 inline imports (QPolygonF, QPainterPath,
  QGraphicsPathItem, QImage, QPixmap) to top-level for performance, auto-fit
  only on file load (not every redraw), copy xyz before mutation in rapid draw,
  added "Fit" button to canvas toolbar
- **editor_panel.py**: `delete_block()` uses `get_clean_selection()` to prevent
  index corruption when blocks and their lines are both selected, block
  expand/collapse changed from single-click to double-click to avoid interfering
  with selection
- **probe_panel.py**: `setFloat`→`setStr` for probe command string
- **MachineState.py**: Lock around `_batch_depth` increment/decrement
- **EventBus.py**: try/except around each callback in `emit()` so one failure
  doesn't kill remaining subscribers
- **utils_core.py**: Config save uses `with` statement, removed debug
  `print("new-config", ...)`, fixed locale directory typo (`"locales"`→`"locale"`)
- **tools_manager.py**: Plugin loading catches `Exception` instead of only
  `(ImportError, AttributeError)`
- **control_panel.py**: Macro buttons execute via `executeCommand()` directly
  instead of indirect pendant queue
- **Helpers.py**: `gettext.install(True, ...)`→`gettext.install("bCNC", ...)`
  (correct domain name instead of boolean)
- **ViewTransform.py**: Guard against division by zero when zoom==0
- **PathGeometry.py**: Guard against spacing<=0 infinite loop in grid generation
- **SceneGraph.py**: Removed dead TkCanvasRenderer class (108 lines of
  Tkinter-only code)
- **serial_monitor.py**: Snapshot `_update` flag before checking to avoid
  TOCTOU race
- **signals.py**: Added `ui_disable`, `ui_enable`, `ui_show_info` signals for
  thread-safe Sender→UI communication

## Qt Migration (in progress)

Backend decoupling and experimental Qt (PySide6) interface.

- utils_core.py — tkinter-free config/utility module extracted from Utils.py;
  Qt files and backend files (Sender, FileManager, Camera, Pendant,
  _GenericController) import `utils_core as Utils` to avoid the
  Utils → Ribbon → tkExtra → tkinter import chain.
  Circular import between Ribbon ↔ Utils resolved with `hasattr` guard.

- tools_base.py — toolkit-independent tool base classes (_Base, DataBase,
  Plugin, and all 15 built-in tool classes) extracted from ToolsPage.py.
  ToolsPage.py re-exports everything and lazily loads Tkinter UI classes
  only when accessed.  Qt files import from tools_base directly.
  Camera.py: PIL.ImageTk lazy-loaded to avoid tkinter at import time.
  Plugins: removed top-level tkinter imports from driller, tile, Random,
  simpleTranslate, simpleRotate, LaserCut, endmilloffset, spiral,
  stlSlicer, and trochoidal_3D — messagebox calls replaced with
  app.setStatus(), making the Qt app fully tkinter-free at runtime.

- Phase 1 — Decouple backend from Tkinter
  - EventBus: toolkit-independent pub/sub signal system
  - MachineState: observable wrapper around CNC.vars with thread-safe batch updates
  - CommandDispatcher: extracted GCode operation routing from bmain.py
  - FileManager: file I/O with EventBus notifications
  - Clean Sender: removed tkinter imports, replaced widget refs with UI callbacks

- Phase 2 — Extract portable canvas math
  - ViewTransform: 3D projection, coordinate transforms, zoom/fit
  - PathGeometry: grid, margins, axes, gantry geometry generation
  - SceneGraph: drawing primitives, scene layers, toolkit-independent renderer

- Phase 3 — Qt UI shell
  - Application entry point (`python -m bCNC.qt.app`)
  - Main window with dockable panels, menus, toolbar, status bar
  - Canvas: QGraphicsView-based CNC visualization with zoom/pan
  - Control panel: DRO, connection widget, jog controls, per-axis zero buttons
  - Spindle / Overrides panel: real-time feed rate and spindle RPM display,
    feed/spindle/rapid override controls (+/-10%, rapid cycle 100/50/25%, reset),
    spindle on/off toggle, flood/mist/coolant-off buttons — all guarded against
    sending commands when not connected
  - Workspace selection: G54-G59 quick-switch buttons in the Position group,
    with live highlight tracking via `$G` parser state updates
  - DRO font customization: work and machine position fonts loaded from `[Font]`
    config section (`dro.wpos`, `dro.mpos`), shared with Tkinter settings
  - 6-axis (ABC) support: conditional DRO rows, jog buttons, and zero buttons
    when `enable6axisopt` is enabled in config (matches Tkinter 6-axis mode)
  - Terminal: serial log with command entry and history
  - Serial monitor: QTimer-based polling replacing Tk.after() loop
  - Editor: QTreeView with block/line hierarchy, context menu, clipboard, undo/redo
  - Probe panel: tabbed Probe/Autolevel/Tool with shared probe settings
  - Bidirectional selection sync between canvas and editor
  - Tools panel: full plugin system, tool database (Material/EndMill/Stock),
    CAM operations (Cut/Profile/Pocket/Drill/Tabs), and all 42+ external plugins
    with dynamic form builder and AppProxy for plugin compatibility
  - Camera tab: live OpenCV video overlay on canvas with cyan crosshair/circles,
    10 anchor modes (gantry-following + 9 viewport positions), camera-to-spindle
    offset registration, edge detection, frame freeze/save, coordinate switching
  - Orient tab: marker-based workpiece alignment — place marker pairs mapping
    machine positions to G-code design positions, least-squares solve for
    rotation + translation, canvas overlay with green/red crosses and error
    circles, apply orientation transform to selected blocks
  - Help menu: Documentation link (F1), Check for Updates (queries PyPI),
    About dialog
  - User-configurable macro buttons: 3-column grid of custom buttons loaded from
    `[Buttons]` config (shared with Tkinter), click to execute multi-line G-code,
    right-click to edit name/tooltip/command
  - Pendant controls: Start/Stop Pendant in Machine menu with status messages
  - Canvas rendering fixes: correct draw order (paths first, then grid/workarea),
    fit-to-content zooms to toolpaths instead of the full workarea, cosmetic pens
    for consistent line widths at any zoom level
  - Command-line file loading: `python -m bCNC.qt.app <file.gcode>`
  - Editor expand/collapse: double-clicking a block row expands/collapses its
    lines; tree arrows also sync with block.expand state
  - Two-column layout: all panels (Control, Editor, Probe, Tools, Terminal)
    tabbed in a single left sidebar with tabs on top; canvas fills the
    central area
  - Persistent window layout: window size, position, dock arrangement, and
    tab order saved to `[QtLayout]` in config on close, restored on launch

## 0.9.16
- Breaking changes:
  - Python3.8 is the lowest supported version. Starting bCNC with any prior version will fail. [#1719](https://github.com/vlachoudis/bCNC/issues/1719)
  - tkinter-gl is now required

## 0.9.15

- New features
  - Python 3 is (mostly) supported now #228
  - 6 axis support #1384
  - Can load SVG files (~only paths without transformations~ improved by tatarize, see
    wiki) #902 #1312
  - Can slice 3D meshes in STL and PLY formats (with minor limitations) #901
  - Can export 3D scan (autolevel probe) data in XYZ format suitable for meshlab poisson
    surface reconstruction
  - Support for helical and ramp cutting #590
  - New style of tabs implemented using "islands" with support for arbitrary shapes and
    pockets #220
  - Interactive value entry is now possible in g-code scripting #1256
  - DRO entry can now handle math formulas like: `sqrt(safe)+1`, `sin(pi**2)` or
    `3.175/2` #789
  - Drag Knife postprocessor and simulator plugin #975
  - Jog digitizer to create drawing by recording points while jogging #929
  - ArcFit plugin can interpolate lots of small segments using one long line/arc #921
  - DrillMark plugin to laser engrave markers for manual drilling #1128
  - More plugins: find center of path, close path, flatten path, scaling, randomize...
  - Start cycle can now be triggered by hardware button connected to arduino #885
- Improvements
  - Restructured UI #1057 and more
  - Better autodetection of serial ports (with device names, ids and without restarting
    bCNC)
  - Disabled blocks are commented-out in exported g-code #767
  - Lots of small improvements and experimental/development features like "trochoidal"
    (see git)
  - Added button to activate GRBL sleep mode (= disable motors) #1099
  - Added button to trigger GRBL door alarm
  - Added button to scan autoleveling margins (to see what will be probed)
  - Added some useful jog buttons
  - Added framework to show help text and images for each plugin #806
- Bug Fixes
  - Proper path direction detection and climb/conventional support #881
  - Proper handling of G91 when moving/rotating g-code #915
- Development and release engineering
  - Created PyPI package for bCNC #964
    - This means bCNC now installs as `pip install bCNC` and launches as
      `python -m bCNC` (see wiki!)
  - Added .bat script to build .exe package of bCNC #437
  - Support for individual motion controllers is now in form of separate plugins #1020
  - Added some basic Travis-CI tests #1117
- New bugs
  - We've hidden few secret bugs in our code as a challenge for you to find and report
    :-)

## 0.9.14

- Currently there is no changelog for 0.9.14 and older releases
- You can still find some info in github issues and history
  https://github.com/vlachoudis/bCNC/commits/master
