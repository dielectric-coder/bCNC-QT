# Qt Main Window - QMainWindow replacing Application(Tk, Sender)
#
# Provides menu bar, toolbar, dock panels (control, terminal),
# central canvas, and status bar.

import base64
import os
import socket
import sys
import webbrowser

from PySide6.QtCore import Qt, QByteArray, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QTabWidget,
    QLabel, QProgressBar, QMenuBar, QToolBar,
    QFileDialog, QMessageBox,
)

import Pendant

import utils_core as Utils
from CNC import CNC, GCode

from .signals import AppSignals
from .canvas_widget import CanvasPanel
from .control_panel import ControlPanel
from .terminal_panel import TerminalPanel
from .serial_monitor import SerialMonitor
from .probe_panel import ProbePanel
from .editor_panel import EditorPanel
from .tools_manager import ToolsManager
from .tools_panel import ToolsPanel


FILETYPES_FILTER = (
    "All accepted (*.ngc *.cnc *.nc *.tap *.gcode *.dxf *.probe "
    "*.orient *.stl *.svg);;"
    "G-Code (*.ngc *.cnc *.nc *.tap *.gcode);;"
    "DXF (*.dxf);;"
    "SVG (*.svg);;"
    "Probe (*.probe *.xyz);;"
    "Orient (*.orient);;"
    "STL (*.stl);;"
    "All files (*)"
)


class MainWindow(QMainWindow):
    """Main application window.

    Owns the Sender, wires Qt signals, and manages layout.
    Does NOT inherit from Sender — uses composition instead.
    """

    def __init__(self, sender):
        super().__init__()
        self.sender = sender
        self.signals = AppSignals()

        self.setWindowTitle(
            f"{Utils.__prg__} {Utils.__version__} [Qt]")
        self.resize(1200, 800)
        self.setContentsMargins(4, 0, 4, 0)

        # Wire Sender UI callbacks — all route through signals for thread safety
        sender._ui_set_status = lambda msg: self.signals.status_message.emit(msg)
        sender._ui_disable = lambda: self.signals.ui_disable.emit()
        sender._ui_enable = lambda: self.signals.ui_enable.emit()
        sender._ui_show_info = lambda title, msg: self.signals.ui_show_info.emit(title, msg)
        self.signals.ui_disable.connect(lambda: self._set_widgets_enabled(False))
        self.signals.ui_enable.connect(lambda: self._set_widgets_enabled(True))
        self.signals.ui_show_info.connect(
            lambda title, msg: QMessageBox.information(self, title, msg))

        # --- Dock tabs on top ---
        self.setTabPosition(
            Qt.DockWidgetArea.LeftDockWidgetArea,
            QTabWidget.TabPosition.North)

        # --- Central widget: Canvas ---
        self.canvas_panel = CanvasPanel(self.signals)
        self.canvas_panel.setMinimumWidth(400)
        self.setCentralWidget(self.canvas_panel)

        # --- Dock: Control panel (left) ---
        self.control_dock = QDockWidget("Control", self)
        self.control_dock.setObjectName("ControlDock")
        self.control_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.control_panel = ControlPanel(sender, self.signals)
        self.control_dock.setWidget(self.control_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.control_dock)

        # --- Dock: Editor panel (left, tabified with control) ---
        self.editor_dock = QDockWidget("Editor", self)
        self.editor_dock.setObjectName("EditorDock")
        self.editor_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.editor_panel = EditorPanel(sender.gcode, self.signals)
        self.editor_dock.setWidget(self.editor_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.editor_dock)
        self.tabifyDockWidget(self.control_dock, self.editor_dock)

        # --- Dock: Probe panel (left, tabified) ---
        self.probe_dock = QDockWidget("Probe", self)
        self.probe_dock.setObjectName("ProbeDock")
        self.probe_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.probe_panel = ProbePanel(sender, self.signals)
        self.probe_dock.setWidget(self.probe_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.probe_dock)
        self.tabifyDockWidget(self.editor_dock, self.probe_dock)

        # --- Dock: Tools panel (left, tabified) ---
        self.tools_manager = ToolsManager(sender.gcode)
        self.tools_manager.loadConfig()

        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setObjectName("ToolsDock")
        self.tools_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.tools_panel = ToolsPanel(
            sender, self.signals, self.tools_manager, self.editor_panel)
        self.tools_dock.setWidget(self.tools_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.tools_dock)
        self.tabifyDockWidget(self.probe_dock, self.tools_dock)

        # --- Dock: Terminal panel (left, tabified) ---
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_dock.setObjectName("TerminalDock")
        self.terminal_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.terminal_panel = TerminalPanel(sender, self.signals)
        self.terminal_dock.setWidget(self.terminal_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.terminal_dock)
        self.tabifyDockWidget(self.tools_dock, self.terminal_dock)

        # Start with Control tab active
        self.control_dock.raise_()

        # --- Wire camera tab ↔ canvas overlay ---
        self.probe_panel.camera_tab.set_camera_overlay(
            self.canvas_panel.camera_overlay)

        # --- Wire orient tab ↔ canvas overlay + editor ---
        self.probe_panel.orient_tab.set_orient_overlay(
            self.canvas_panel.orient_overlay)
        self.probe_panel.orient_tab.set_editor_panel(self.editor_panel)

        # --- Status bar ---
        self._setup_statusbar()

        # --- Menu bar ---
        self._setup_menubar()

        # --- Toolbar ---
        self._setup_toolbar()

        # --- Serial monitor ---
        self.serial_monitor = SerialMonitor(sender, self.signals)
        self.serial_monitor.start()

        # --- Wire signals ---
        self.signals.status_message.connect(self._on_status_message)
        self.signals.canvas_coords.connect(self._on_canvas_coords)
        self.signals.run_progress.connect(self._on_run_progress)
        self.signals.buffer_fill.connect(self._on_buffer_fill)
        self.signals.draw_requested.connect(self._on_draw)
        self.signals.view_changed.connect(self._on_draw)
        self.signals.position_updated.connect(
            self.canvas_panel.update_gantry)

        # Execution signals
        self.signals.run_requested.connect(self._on_run)
        self.signals.stop_requested.connect(self._on_stop)
        self.signals.pause_requested.connect(self._on_pause)

        # Editor signals
        self.signals.file_loaded.connect(self.editor_panel.fill)
        self.signals.file_loaded.connect(self._on_file_loaded)

        # Selection sync: editor → canvas, canvas → editor
        self.signals.selection_changed.connect(
            self._on_editor_selection_changed)
        self.signals.canvas_block_clicked.connect(
            self._on_canvas_block_clicked)

        # Probe / autolevel signals
        self.signals.draw_probe.connect(self._on_draw_probe)
        self.signals.serial_run_end.connect(self._on_run_end)

        # Orient signals
        self.signals.orient_add_marker_mode.connect(
            self.canvas_panel.enter_add_orient_mode)
        self.signals.draw_orient.connect(self._on_draw_orient)

        # --- Restore saved window geometry and dock layout ---
        self._restore_layout()

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self._status_label = QLabel("Ready")
        self.statusbar.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self._progress_bar)

        self._buffer_bar = QProgressBar()
        self._buffer_bar.setMaximumWidth(80)
        self._buffer_bar.setMaximumHeight(16)
        self._buffer_bar.setRange(0, 100)
        self._buffer_bar.setFormat("%v%")
        self._buffer_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self._buffer_bar)

        self._sel_label = QLabel("")
        self._sel_label.setMinimumWidth(90)
        self._sel_label.setStyleSheet("color: darkblue;")
        self.statusbar.addPermanentWidget(self._sel_label)

        self._coord_x = QLabel("X: 0.000")
        self._coord_x.setMinimumWidth(80)
        self._coord_x.setStyleSheet("color: darkred;")
        self._coord_y = QLabel("Y: 0.000")
        self._coord_y.setMinimumWidth(80)
        self._coord_y.setStyleSheet("color: darkred;")
        self._coord_z = QLabel("Z: 0.000")
        self._coord_z.setMinimumWidth(80)
        self._coord_z.setStyleSheet("color: darkred;")
        self.statusbar.addPermanentWidget(self._coord_x)
        self.statusbar.addPermanentWidget(self._coord_y)
        self.statusbar.addPermanentWidget(self._coord_z)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _setup_menubar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._on_new_file)
        file_menu.addAction(new_action)

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._build_recent_menu()

        import_action = QAction("&Import...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_file)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        reload_action = QAction("&Reload", self)
        reload_action.triggered.connect(self._on_reload)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Machine menu
        machine_menu = menubar.addMenu("&Machine")

        connect_action = QAction("&Connect/Disconnect", self)
        connect_action.triggered.connect(
            self.control_panel.connection._on_connect)
        machine_menu.addAction(connect_action)

        machine_menu.addSeparator()

        home_action = QAction("&Home", self)
        home_action.triggered.connect(lambda: self.sender.home())
        machine_menu.addAction(home_action)

        unlock_action = QAction("&Unlock", self)
        unlock_action.triggered.connect(lambda: self.sender.unlock())
        machine_menu.addAction(unlock_action)

        reset_action = QAction("Soft &Reset", self)
        reset_action.triggered.connect(lambda: self.sender.softReset())
        machine_menu.addAction(reset_action)

        machine_menu.addSeparator()

        pendant_start_action = QAction("Start &Pendant", self)
        pendant_start_action.triggered.connect(self._on_start_pendant)
        machine_menu.addAction(pendant_start_action)

        pendant_stop_action = QAction("Sto&p Pendant", self)
        pendant_stop_action.triggered.connect(self._on_stop_pendant)
        machine_menu.addAction(pendant_stop_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        view_menu.addAction(self.control_dock.toggleViewAction())
        view_menu.addAction(self.editor_dock.toggleViewAction())
        view_menu.addAction(self.probe_dock.toggleViewAction())
        view_menu.addAction(self.tools_dock.toggleViewAction())
        view_menu.addAction(self.terminal_dock.toggleViewAction())

        view_menu.addSeparator()

        fit_action = QAction("&Fit to Content", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self.canvas_panel.view.fit_to_content)
        view_menu.addAction(fit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        cut_action = QAction("Cu&t", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self.editor_panel.cut)
        edit_menu.addAction(cut_action)

        copy_action = QAction("&Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.editor_panel.copy)
        edit_menu.addAction(copy_action)

        paste_action = QAction("&Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.editor_panel.paste)
        edit_menu.addAction(paste_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        docs_action = QAction("&Documentation", self)
        docs_action.setShortcut(QKeySequence("F1"))
        docs_action.triggered.connect(
            lambda: webbrowser.open(Utils.__www__))
        help_menu.addAction(docs_action)

        help_menu.addSeparator()

        updates_action = QAction("Check for &Updates...", self)
        updates_action.triggered.connect(self._on_check_updates)
        help_menu.addAction(updates_action)

        help_menu.addSeparator()

        about_action = QAction("&About bCNC", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setObjectName("MainToolBar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction("New", self)
        new_action.triggered.connect(self._on_new_file)
        toolbar.addAction(new_action)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self._on_open_file)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        run_action = QAction("Run", self)
        run_action.triggered.connect(self.signals.run_requested.emit)
        toolbar.addAction(run_action)

        pause_action = QAction("Pause", self)
        pause_action.triggered.connect(self.signals.pause_requested.emit)
        toolbar.addAction(pause_action)

        stop_action = QAction("Stop", self)
        stop_action.triggered.connect(self.signals.stop_requested.emit)
        toolbar.addAction(stop_action)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _check_modified(self):
        """Prompt user to save unsaved changes.

        Returns True if the caller should abort (user cancelled).
        """
        if self.sender.gcode.isModified():
            ans = QMessageBox.question(
                self,
                _("File modified"),
                _("Gcode was modified do you want to save it first?"),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if ans == QMessageBox.StandardButton.Cancel:
                return True
            if ans == QMessageBox.StandardButton.Yes:
                self.sender.saveAll()

        if (not self.sender.gcode.probe.isEmpty()
                and not self.sender.gcode.probe.saved):
            ans = QMessageBox.question(
                self,
                _("Probe File modified"),
                _("Probe was modified do you want to save it first?"),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if ans == QMessageBox.StandardButton.Cancel:
                return True
            if ans == QMessageBox.StandardButton.Yes:
                if self.sender.gcode.probe.filename == "":
                    self._on_save_as()
                else:
                    self.sender.gcode.probe.save()

        return False

    def _on_new_file(self):
        if self.sender.running:
            return
        if self._check_modified():
            return
        self.sender.gcode.init()
        self.sender.gcode.headerFooter()
        self.editor_panel.fill()
        self._on_draw()
        self._update_title()

    def _on_open_file(self):
        if self._check_modified():
            return
        filename, _filt = QFileDialog.getOpenFileName(
            self, "Open G-Code File", "", FILETYPES_FILTER)
        if filename:
            self.sender.load(filename)
            Utils.addRecent(filename)
            self.signals.file_loaded.emit(filename)
            self._on_draw()
            self.editor_panel.select_all()
            self._update_title()
            self._build_recent_menu()
            self._on_status_message(_("'{}' loaded").format(filename))
            if filename.lower().endswith(".orient"):
                self._on_draw_orient()
                self.probe_panel.orient_tab.refresh()

    def _on_import_file(self):
        filename, _filt = QFileDialog.getOpenFileName(
            self, _("Import Gcode/DXF file"), "",
            "G-Code (*.ngc *.nc *.gcode);;"
            "DXF (*.dxf);;"
            "SVG (*.svg);;"
            "All files (*)")
        if not filename:
            return
        fn, ext = os.path.splitext(filename)
        ext = ext.lower()
        gcode = GCode()
        if ext == ".dxf":
            gcode.importDXF(filename)
        elif ext == ".svg":
            gcode.importSVG(filename)
        else:
            gcode.load(filename)
        blocks = gcode.blocks
        if not blocks:
            return
        sel = self.editor_panel.get_selected_blocks()
        pos = sel[-1] if sel else None
        undoinfo = self.sender.gcode.insBlocksUndo(pos, blocks)
        self.sender.gcode.addUndo(undoinfo)
        self.editor_panel.fill()
        self._on_draw()
        self.canvas_panel.view.fit_to_content()

    def _on_reload(self):
        if not self.sender.gcode.filename:
            return
        if self._check_modified():
            return
        self.sender.load(self.sender.gcode.filename)
        self.signals.file_loaded.emit(self.sender.gcode.filename)
        self._on_draw()
        self._update_title()
        self._on_status_message(
            _("'{}' reloaded").format(self.sender.gcode.filename))

    def _on_save_file(self):
        if self.sender.gcode.filename:
            self.sender.save(self.sender.gcode.filename)
            Utils.addRecent(self.sender.gcode.filename)
            self._update_title()
            self._build_recent_menu()
            self._on_status_message(
                _("'{}' saved").format(self.sender.gcode.filename))
        else:
            self._on_save_as()

    def _on_save_as(self):
        filename, _filt = QFileDialog.getSaveFileName(
            self, "Save G-Code File", "", FILETYPES_FILTER)
        if filename:
            self.sender.save(filename)
            Utils.addRecent(filename)
            self._update_title()
            self._build_recent_menu()
            self._on_status_message(_("'{}' saved").format(filename))

    def _build_recent_menu(self):
        """Rebuild the Open Recent submenu from config."""
        self._recent_menu.clear()
        for i in range(Utils._maxRecent):
            filename = Utils.getRecent(i)
            if filename is None:
                break
            label = f"{i + 1}  {os.path.basename(filename)}"
            action = self._recent_menu.addAction(label)
            action.setToolTip(filename)
            idx = i
            action.triggered.connect(
                lambda checked=False, n=idx: self._on_load_recent(n))
        if self._recent_menu.isEmpty():
            no_recent = self._recent_menu.addAction("(no recent files)")
            no_recent.setEnabled(False)

    def _on_load_recent(self, index):
        filename = Utils.getRecent(index)
        if filename is None:
            return
        if self._check_modified():
            return
        self.sender.load(filename)
        Utils.addRecent(filename)
        self.signals.file_loaded.emit(filename)
        self._on_draw()
        self._update_title()
        self._build_recent_menu()
        self._on_status_message(_("'{}' loaded").format(filename))

    def _update_title(self):
        """Update window title to reflect current filename."""
        fname = self.sender.gcode.filename
        if fname:
            self.setWindowTitle(
                f"{Utils.__prg__} {Utils.__version__}: {fname} [Qt]")
        else:
            self.setWindowTitle(
                f"{Utils.__prg__} {Utils.__version__} [Qt]")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _on_run(self):
        if self.sender.serial is None:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to a machine first.")
            return
        self.sender.run()

    def _on_stop(self):
        self.sender.stopRun()

    def _on_pause(self):
        self.sender.pause()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------
    def _on_status_message(self, msg):
        self._status_label.setText(msg)

    def _on_canvas_coords(self, x, y, z):
        fmt = "%.3f" if not CNC.inch else "%.4f"
        self._coord_x.setText(f"X: {fmt % x}")
        self._coord_y.setText(f"Y: {fmt % y}")
        self._coord_z.setText(f"Z: {fmt % z}")

    def _on_run_progress(self, completed, total):
        if total > 0:
            self._progress_bar.setVisible(True)
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(completed)
        else:
            self._progress_bar.setVisible(False)

    def _on_buffer_fill(self, percent):
        self._buffer_bar.setVisible(True)
        self._buffer_bar.setValue(int(percent))

    def _on_undo(self):
        self.sender.gcode.undo()
        self.editor_panel.fill()
        self._on_draw()

    def _on_redo(self):
        self.sender.gcode.redo()
        self.editor_panel.fill()
        self._on_draw()

    def _on_editor_selection_changed(self):
        """Editor selection changed → highlight on canvas + update status."""
        blocks = self.editor_panel.get_selected_blocks()
        self.canvas_panel.highlight_selection(blocks)
        n = len(blocks)
        self._sel_label.setText(f"Sel: {n} block{'s' if n != 1 else ''}" if n else "")

    def _on_canvas_block_clicked(self, bid, ctrl):
        """Canvas path clicked → select in editor."""
        if ctrl:
            self.editor_panel.add_to_selection([bid])
        else:
            self.editor_panel.select_blocks([bid])

    def _on_file_loaded(self, filename):
        """After a file is loaded, rebuild and fit to content."""
        self._on_draw()
        self.canvas_panel.view.fit_to_content()

    def _on_draw(self):
        """Rebuild the canvas from current gcode."""
        self.canvas_panel.rebuild(self.sender.gcode, self.sender.cnc)
        # Re-apply selection highlight (rebuild clears all scene state)
        blocks = self.editor_panel.get_selected_blocks()
        if blocks:
            self.canvas_panel.highlight_selection(blocks)
        # Re-draw orient markers (rebuild clears overlay items)
        self.canvas_panel.draw_orient(self.sender.gcode.orient)

    def _on_draw_probe(self):
        """Draw probe overlay on canvas."""
        self.canvas_panel.draw_probe(self.sender.gcode.probe)

    def _on_draw_orient(self):
        """Draw orient markers on canvas."""
        self.canvas_panel.draw_orient(self.sender.gcode.orient)

    def _on_run_end(self, msg):
        """Re-enable UI when a run (including probe scan) ends."""
        self._set_widgets_enabled(True)
        self._progress_bar.setVisible(False)
        self._buffer_bar.setVisible(False)

    # ------------------------------------------------------------------
    # Pendant
    # ------------------------------------------------------------------
    def _on_start_pendant(self):
        started = Pendant.start(self.sender)
        host = f"http://{socket.gethostname()}:{Pendant.port}"
        if started:
            QMessageBox.information(
                self, _("Pendant"),
                _("Pendant started:") + "\n" + host)
        else:
            ans = QMessageBox.question(
                self, _("Pendant"),
                _("Pendant already started:") + "\n" + host
                + "\n" + _("Would you like to open it locally?"),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No)
            if ans == QMessageBox.StandardButton.Yes:
                webbrowser.open(host, new=2)

    def _on_stop_pendant(self):
        if Pendant.stop():
            QMessageBox.information(
                self, _("Pendant"), _("Pendant stopped"))

    # ------------------------------------------------------------------
    # Help menu
    # ------------------------------------------------------------------
    def _on_check_updates(self):
        """Check PyPI for newer bCNC version (non-blocking)."""
        import json
        import http.client as http_client

        class _UpdateWorker(QThread):
            finished = Signal(str, str)  # (latest_version, error_msg)

            def run(self):
                try:
                    h = http_client.HTTPSConnection("pypi.org", timeout=10)
                    h.request("GET", "/pypi/bCNC/json", None,
                              {"User-Agent": "bCNC"})
                    r = h.getresponse()
                    if r.status == 200:
                        data = json.loads(r.read().decode("utf-8"))
                        self.finished.emit(data["info"]["version"], "")
                    else:
                        self.finished.emit(
                            "", _("Error {} in connection").format(r.status))
                except Exception as e:
                    self.finished.emit("", str(e))

        def _on_result(latest, error):
            if error:
                QMessageBox.warning(
                    self, _("Update Check Failed"), error)
            elif self._is_newer(Utils.__version__, latest):
                ans = QMessageBox.question(
                    self, _("Update Available"),
                    _("A newer version is available:") + f"\n\n"
                    f"Installed: {Utils.__version__}\n"
                    f"Available: {latest}\n\n"
                    + _("Open download page?"),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No)
                if ans == QMessageBox.StandardButton.Yes:
                    webbrowser.open("https://pypi.org/project/bCNC/")
            else:
                QMessageBox.information(
                    self, _("Up to Date"),
                    _("You are running the latest version.")
                    + f"\n\nVersion: {Utils.__version__}")

        self._update_worker = _UpdateWorker()
        self._update_worker.finished.connect(_on_result)
        self._update_worker.start()

    @staticmethod
    def _is_newer(current, latest):
        """Return True if latest version is newer than current."""
        try:
            cv = list(map(int, current.split(".")))
            lv = list(map(int, latest.split(".")))
            for c, l in zip(cv, lv):
                if l > c:
                    return True
                if l < c:
                    return False
            return len(lv) > len(cv)
        except (ValueError, AttributeError):
            return False

    def _on_about(self):
        """Show About dialog."""
        QMessageBox.about(
            self,
            _("About {} v{}").format(Utils.__prg__, Utils.__version__),
            f"<h3>{Utils.__prg__} v{Utils.__version__}</h3>"
            f"<p>An advanced fully featured g-code sender for GRBL.</p>"
            f"<p><b>Author:</b> Vasilis Vlachoudis</p>"
            f"<p><b>Website:</b> <a href='{Utils.__www__}'>"
            f"{Utils.__www__}</a></p>"
            f"<p><b>Email:</b> {Utils.__email__}</p>")

    # ------------------------------------------------------------------
    # Widget enable/disable for run mode
    # ------------------------------------------------------------------
    def _set_widgets_enabled(self, enabled):
        self.control_panel.setEnabled(enabled)
        self.probe_panel.setEnabled(enabled)
        self.editor_panel.setEnabled(enabled)
        self.tools_panel.setEnabled(enabled)
        self.menuBar().setEnabled(enabled)

    # ------------------------------------------------------------------
    # Layout save / restore
    # ------------------------------------------------------------------
    def _save_layout(self):
        """Save window geometry and dock state to config."""
        section = "QtLayout"
        if not Utils.config.has_section(section):
            Utils.config.add_section(section)
        geo = base64.b64encode(
            self.saveGeometry().data()).decode("ascii")
        state = base64.b64encode(
            self.saveState().data()).decode("ascii")
        Utils.config.set(section, "geometry", geo)
        Utils.config.set(section, "state", state)

    def _restore_layout(self):
        """Restore window geometry and dock state from config."""
        section = "QtLayout"
        if not Utils.config.has_section(section):
            return
        try:
            geo = Utils.config.get(section, "geometry")
            self.restoreGeometry(
                QByteArray(base64.b64decode(geo)))
        except Exception:
            pass
        try:
            state = Utils.config.get(section, "state")
            self.restoreState(
                QByteArray(base64.b64decode(state)))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        """Clean shutdown: save config, stop serial monitor, close connection."""
        if self._check_modified():
            event.ignore()
            return
        self._save_layout()
        self.canvas_panel.camera_overlay.stop()
        self.tools_panel.saveConfig()
        self.probe_panel.saveConfig()
        self.serial_monitor.stop()
        self.sender.quit()
        if self.sender.serial is not None:
            self.sender.close()
        Utils.saveConfiguration()
        event.accept()
