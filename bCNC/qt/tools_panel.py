# Qt Tools Panel - AppProxy, VariableForm, and ToolsPanel
#
# Provides the full Tools/Plugins page for the Qt app:
# - AppProxy: wraps sender/signals/editor for plugin.execute(app)
# - VariableForm: dynamic form builder from tool.variables
# - ToolsPanel: main UI with categorized tree, form, buttons, help

import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem,
    QPushButton, QScrollArea, QTextBrowser,
    QSplitter, QFormLayout,
    QDoubleSpinBox, QSpinBox, QCheckBox,
    QLineEdit, QPlainTextEdit, QComboBox,
    QFileDialog, QInputDialog, QColorDialog,
    QMessageBox, QApplication,
)

from CommandDispatcher import GCodeOperations
from tools_base import DataBase


class _EditorProxy:
    """Adapts Qt EditorPanel to the app.editor API plugins expect."""

    def __init__(self, editor_panel):
        self._ep = editor_panel

    def getSelectedBlocks(self):
        return self._ep.get_selected_blocks()

    def getCleanSelection(self):
        return self._ep.get_clean_selection()

    def fill(self):
        self._ep.fill()

    def selectBlocks(self, ids):
        self._ep.select_blocks(ids)

    def select(self, items, clear=False):
        if clear:
            self._ep.select_clear()
        if items:
            self._ep.select_items(items)

    def selectAll(self):
        self._ep.select_all()

    def selectClear(self):
        self._ep.select_clear()

    def activeBlock(self):
        sel = self._ep.get_selected_blocks()
        return sel[0] if sel else 0


class AppProxy:
    """Wraps sender/signals/editor/tools for plugin.execute(app).

    Provides the same API that ToolsPage plugins expect from the
    Tkinter Application object.
    """

    def __init__(self, sender, signals, tools_manager, editor_panel):
        self.sender = sender
        self.signals = signals
        self.tools = tools_manager
        self.editor = _EditorProxy(editor_panel)
        self._editor_panel = editor_panel
        self.gcode_ops = GCodeOperations(sender.gcode, tools_manager)

    @property
    def gcode(self):
        return self.sender.gcode

    @property
    def cnc(self):
        return self.sender.gcode.cnc

    def activeBlock(self):
        return self.editor.activeBlock()

    def refresh(self):
        self.editor.fill()
        self.signals.draw_requested.emit()

    def draw(self):
        self.signals.draw_requested.emit()

    def setStatus(self, msg):
        self.signals.status_message.emit(msg)

    def busy(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def notBusy(self):
        QApplication.restoreOverrideCursor()

    def run(self, lines=None):
        if lines:
            self.sender.runLines(lines)

    def sendGCode(self, cmd):
        self.sender.sendGCode(cmd)

    def executeOnSelection(self, cmd, blocksonly, *args):
        if blocksonly:
            items = self.editor.getSelectedBlocks()
        else:
            items = self.editor.getCleanSelection()
        if not items:
            QMessageBox.warning(
                None, _("Nothing to do"),
                _("Operation {} requires some gcode to be selected").format(
                    cmd))
            return

        self.busy()
        sel, status = self.gcode_ops.execute_on_items(cmd, items, *args)
        self.editor.fill()
        if sel is not None:
            if isinstance(sel, str):
                QMessageBox.critical(None, _("Operation error"), sel)
            else:
                self.editor.select(sel, clear=True)
        self.signals.draw_requested.emit()
        self.notBusy()
        self.setStatus(status)

    def profile(self, direction=None, offset=0.0, overcut=False,
                name=None, pocket=False):
        self.busy()
        blocks = self.editor.getSelectedBlocks()
        msg, computed_ofs = self.gcode_ops.profile(
            blocks, direction, offset, overcut, name, pocket)
        if msg:
            QMessageBox.warning(
                None, _("Open paths"), f"WARNING: {msg}")
        self.editor.fill()
        self.editor.selectBlocks(blocks)
        self.signals.draw_requested.emit()
        self.notBusy()
        self.setStatus(
            _("Profile block distance={:g}").format(computed_ofs))

    def pocket(self, name=None):
        self.busy()
        blocks = self.editor.getSelectedBlocks()
        msg = self.gcode_ops.pocket(blocks, name)
        if msg:
            QMessageBox.warning(
                None, _("Open paths"), _("WARNING: {}").format(msg))
        self.editor.fill()
        self.editor.selectBlocks(blocks)
        self.signals.draw_requested.emit()
        self.notBusy()

    def trochprofile_bcnc(self, cutDiam=0.0, direction=None, offset=0.0,
                          overcut=False, adaptative=False,
                          adaptedRadius=0.0, tooldiameter=0.0,
                          targetDepth=0.0, depthIncrement=0.0,
                          tabsnumber=0.0, tabsWidth=0.0, tabsHeight=0.0):
        self.busy()
        blocks = self.editor.getSelectedBlocks()
        msg, is_adaptative, computed_ofs = self.gcode_ops.trochprofile(
            blocks, cutDiam, direction, offset, overcut,
            adaptative, adaptedRadius, tooldiameter,
            targetDepth, depthIncrement,
            tabsnumber, tabsWidth, tabsHeight)
        if msg:
            QMessageBox.warning(
                None, _("Open paths"), f"WARNING: {msg}")
        if is_adaptative:
            QMessageBox.warning(
                None, _("Adaptative"),
                _("WARNING: Adaptive route generated, but Trocoidal still "
                  "does not implement it."))
        self.editor.fill()
        self.editor.selectBlocks(blocks)
        self.signals.draw_requested.emit()
        self.notBusy()


# =========================================================================
# VariableForm - dynamic form builder from tool.variables
# =========================================================================
class VariableForm(QWidget):
    """Builds a Qt form from a tool's variables list.

    Each variable (name, type, default, label[, help]) is mapped to
    the appropriate Qt widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._widgets = {}  # name -> widget
        self._tool = None
        self._tools_manager = None

    def populate(self, tool, tools_manager):
        """Clear the form and rebuild from tool.variables."""
        self._tool = tool
        self._tools_manager = tools_manager

        # Clear existing rows (removeRow removes both label and field)
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._widgets.clear()

        for var in tool.variables:
            n, t, d, lp = var[:4]
            value = tool[n]
            widget = self._create_widget(n, t, d, value, tool)
            self._widgets[n] = widget
            self._layout.addRow(lp, widget)

    def _create_widget(self, name, vtype, default, value, tool):
        """Create a Qt widget for the given variable type."""
        if vtype == "float":
            w = QDoubleSpinBox()
            w.setDecimals(4)
            w.setRange(-1e9, 1e9)
            try:
                w.setValue(float(value) if value != "" else float(default))
            except (ValueError, TypeError):
                w.setValue(0.0)
            return w

        if vtype == "mm":
            w = QDoubleSpinBox()
            w.setDecimals(4)
            w.setRange(-1e9, 1e9)
            try:
                v = float(value) if value != "" else float(default)
                if self._tools_manager and self._tools_manager.inches:
                    v /= 25.4
                w.setValue(v)
            except (ValueError, TypeError):
                w.setValue(0.0)
            return w

        if vtype == "int":
            w = QSpinBox()
            w.setRange(-1000000, 1000000)
            try:
                w.setValue(int(value) if value != "" else int(default))
            except (ValueError, TypeError):
                w.setValue(0)
            return w

        if vtype == "bool":
            w = QCheckBox()
            try:
                w.setChecked(bool(int(value)) if value != "" else bool(default))
            except (ValueError, TypeError):
                w.setChecked(False)
            return w

        if vtype == "text":
            w = QPlainTextEdit()
            w.setMaximumHeight(60)
            w.setPlainText(str(value) if value else str(default))
            return w

        if vtype == "file":
            return self._file_widget(value or default, save=False)

        if vtype == "output":
            return self._file_widget(value or default, save=True)

        if vtype == "color":
            return self._color_widget(value or default)

        if vtype == "list":
            w = QComboBox()
            w.setEditable(True)
            items = tool.listdb.get(name, [])
            w.addItems(items)
            if value and value in items:
                w.setCurrentText(str(value))
            elif value:
                w.setCurrentText(str(value))
            return w

        if vtype == "db":
            w = QComboBox()
            w.setEditable(True)
            if name == "name":
                items = tool.names()
            else:
                try:
                    ref_tool = self._tools_manager[name]
                    items = [""] + ref_tool.names()
                except KeyError:
                    items = []
            w.addItems(items)
            if value:
                w.setCurrentText(str(value))
            return w

        if "," in vtype:
            w = QComboBox()
            choices = [""] + vtype.split(",")
            w.addItems(choices)
            if value:
                w.setCurrentText(str(value))
            elif default:
                w.setCurrentText(str(default))
            return w

        # Default: string
        w = QLineEdit()
        w.setText(str(value) if value else str(default) if default else "")
        return w

    def _file_widget(self, value, save=False):
        """Create a line-edit + Browse button for file paths."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        line = QLineEdit(str(value) if value else "")
        btn = QPushButton("...")
        btn.setMaximumWidth(30)

        def browse():
            if save:
                path, _filt = QFileDialog.getSaveFileName(
                    self, _("Save File"), line.text())
            else:
                path, _filt = QFileDialog.getOpenFileName(
                    self, _("Open File"), line.text())
            if path:
                line.setText(path)

        btn.clicked.connect(browse)
        layout.addWidget(line)
        layout.addWidget(btn)
        container._line_edit = line
        return container

    def _color_widget(self, value):
        """Create a color swatch button."""
        btn = QPushButton()
        btn.setFixedHeight(24)
        btn._color_value = str(value) if value else "#000000"
        self._update_color_swatch(btn)

        def pick_color():
            color = QColorDialog.getColor(
                QColor(btn._color_value), self)
            if color.isValid():
                btn._color_value = color.name()
                self._update_color_swatch(btn)

        btn.clicked.connect(pick_color)
        return btn

    @staticmethod
    def _update_color_swatch(btn):
        try:
            btn.setStyleSheet(
                f"background-color: {btn._color_value}; border: 1px solid gray;")
            btn.setText(btn._color_value)
        except Exception:
            btn.setStyleSheet("")
            btn.setText("(invalid)")

    def read_values(self, tool):
        """Push all widget values back into tool[name]."""
        if not self._tool:
            return
        for var in tool.variables:
            n, t, d, lp = var[:4]
            w = self._widgets.get(n)
            if w is None:
                continue
            tool[n] = self._read_widget(w, t)

    def _read_widget(self, widget, vtype):
        """Extract the value from a widget given its type."""
        if vtype == "float":
            return widget.value()
        if vtype == "mm":
            v = widget.value()
            if self._tools_manager and self._tools_manager.inches:
                v *= 25.4
            return v
        if vtype == "int":
            return widget.value()
        if vtype == "bool":
            return int(widget.isChecked())
        if vtype == "text":
            return widget.toPlainText()
        if vtype in ("file", "output"):
            return widget._line_edit.text()
        if vtype == "color":
            return widget._color_value
        if vtype in ("list", "db") or "," in vtype:
            return widget.currentText()
        # str
        return widget.text()


# =========================================================================
# ToolsPanel - main panel with tree, form, buttons, help
# =========================================================================
class ToolsPanel(QWidget):
    """Tools panel providing tool/plugin selection, variable editing,
    execution, and database management."""

    # Categories for the tree
    _BUILTIN_CONFIG = ["CNC", "Controller", "Camera", "Shortcut",
                       "Font", "Color", "Events"]
    _BUILTIN_DB = ["Material", "EndMill", "Stock"]
    _BUILTIN_CAM = ["Cut", "Drill", "Profile", "Pocket", "Tabs"]
    _CAM_PLUGIN_GROUPS = ["CAM_Core+", "CAM_Core", "CAM"]
    _OTHER_PLUGIN_GROUPS = ["Generator", "Artistic", "Development"]

    def __init__(self, sender, signals, tools_manager, editor_panel,
                 parent=None):
        super().__init__(parent)
        self._sender = sender
        self._signals = signals
        self._tools_manager = tools_manager
        self._editor_panel = editor_panel

        self._app_proxy = AppProxy(
            sender, signals, tools_manager, editor_panel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Tool selector tree ---
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMaximumHeight(220)
        self._tree.setIndentation(16)
        self._build_tool_tree()
        self._tree.currentItemChanged.connect(self._on_tool_selected)
        layout.addWidget(self._tree)

        # --- Execute button ---
        self._exe_btn = QPushButton(_("Execute"))
        self._exe_btn.setStyleSheet(
            "font-weight: bold; color: darkred; padding: 4px;")
        self._exe_btn.clicked.connect(self._on_execute)
        self._exe_btn.setVisible(False)
        layout.addWidget(self._exe_btn)

        # --- Database buttons ---
        self._db_buttons = QWidget()
        db_layout = QHBoxLayout(self._db_buttons)
        db_layout.setContentsMargins(0, 0, 0, 0)
        db_layout.setSpacing(4)
        for label, slot in [
            (_("Add"), self._on_db_add),
            (_("Delete"), self._on_db_delete),
            (_("Clone"), self._on_db_clone),
            (_("Rename"), self._on_db_rename),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            db_layout.addWidget(btn)
        self._db_buttons.setVisible(False)
        layout.addWidget(self._db_buttons)

        # --- Splitter: form + help ---
        splitter = QSplitter(Qt.Orientation.Vertical)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._var_form = VariableForm()
        scroll.setWidget(self._var_form)
        splitter.addWidget(scroll)

        self._help_browser = QTextBrowser()
        self._help_browser.setMaximumHeight(150)
        self._help_browser.setReadOnly(True)
        splitter.addWidget(self._help_browser)

        layout.addWidget(splitter, 1)

        # Select initial tool
        self._select_tool_by_name(tools_manager._active)

    def _build_tool_tree(self):
        """Populate QTreeWidget with categorized tools."""
        self._tree.clear()
        self._tool_items = {}  # tool_name -> QTreeWidgetItem

        def add_category(label, tool_names):
            cat = QTreeWidgetItem(self._tree, [label])
            cat.setFlags(cat.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = cat.font(0)
            font.setBold(True)
            cat.setFont(0, font)
            for name in tool_names:
                key = name.upper()
                if key in self._tools_manager.tools:
                    item = QTreeWidgetItem(cat, [name])
                    item.setData(0, Qt.ItemDataRole.UserRole, name)
                    self._tool_items[key] = item
            return cat

        add_category(_("Config"), self._BUILTIN_CONFIG)
        add_category(_("Database"), self._BUILTIN_DB)
        cam_cat = add_category(_("CAM"), self._BUILTIN_CAM)

        # Collect plugins by group
        plugins = self._tools_manager.pluginList()
        grouped = {}
        for p in plugins:
            g = getattr(p, "group", "Macros")
            grouped.setdefault(g, []).append(p)

        # Merge CAM plugin groups into the built-in CAM category
        for group_name in self._CAM_PLUGIN_GROUPS:
            for p in grouped.pop(group_name, []):
                item = QTreeWidgetItem(cam_cat, [p.name])
                item.setData(0, Qt.ItemDataRole.UserRole, p.name)
                self._tool_items[p.name.upper()] = item

        # Other plugin groups get their own categories
        for group_name in self._OTHER_PLUGIN_GROUPS:
            group_plugins = grouped.pop(group_name, [])
            if group_plugins:
                cat = QTreeWidgetItem(self._tree, [group_name])
                cat.setFlags(cat.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                font = cat.font(0)
                font.setBold(True)
                cat.setFont(0, font)
                for p in group_plugins:
                    item = QTreeWidgetItem(cat, [p.name])
                    item.setData(0, Qt.ItemDataRole.UserRole, p.name)
                    self._tool_items[p.name.upper()] = item

        # Remaining plugins go into Macros
        remaining = []
        for plugins_list in grouped.values():
            remaining.extend(plugins_list)
        if remaining:
            remaining.sort(key=lambda p: p.name)
            cat = QTreeWidgetItem(self._tree, [_("Macros")])
            cat.setFlags(cat.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = cat.font(0)
            font.setBold(True)
            cat.setFont(0, font)
            for p in remaining:
                item = QTreeWidgetItem(cat, [p.name])
                item.setData(0, Qt.ItemDataRole.UserRole, p.name)
                self._tool_items[p.name.upper()] = item

        self._tree.expandAll()

    def _select_tool_by_name(self, name):
        """Select a tool in the tree by name."""
        key = name.upper()
        item = self._tool_items.get(key)
        if item:
            self._tree.setCurrentItem(item)

    def _on_tool_selected(self, current, previous):
        """Handle tool selection change."""
        if current is None:
            return
        name = current.data(0, Qt.ItemDataRole.UserRole)
        if name is None:
            return

        # Save previous tool values
        if previous is not None:
            prev_name = previous.data(0, Qt.ItemDataRole.UserRole)
            if prev_name:
                try:
                    prev_tool = self._tools_manager[prev_name]
                    self._var_form.read_values(prev_tool)
                except KeyError:
                    pass

        self._tools_manager.setActive(name)
        tool = self._tools_manager.getActive()

        # Call beforeChange (some tools like Controller query the machine)
        try:
            tool.beforeChange(self._app_proxy)
        except Exception:
            pass

        # Populate form
        self._var_form.populate(tool, self._tools_manager)

        # Show/hide execute button
        has_exe = "exe" in tool.buttons
        self._exe_btn.setVisible(has_exe)
        if has_exe:
            self._exe_btn.setText(name)

        # Show/hide database buttons
        is_db = isinstance(tool, DataBase)
        self._db_buttons.setVisible(is_db)

        # Update help text
        self._update_help(tool)

    def _update_help(self, tool):
        """Update the help browser with tool documentation."""
        parts = []
        if hasattr(tool, "help") and tool.help:
            # Strip image references (#name) from help text
            for line in tool.help.splitlines():
                if line.startswith("#") and " " not in line:
                    continue
                parts.append(line)

        # Add variable help from 5th element
        var_help = []
        for var in tool.variables:
            if len(var) > 4 and var[4]:
                var_help.append(f"<b>{var[0].upper()}</b> ({var[3]}): {var[4]}")

        if var_help:
            parts.append("")
            parts.append("<b>=== Module options ===</b>")
            for vh in var_help:
                parts.append(vh)
                parts.append("")

        if parts:
            self._help_browser.setHtml(
                "<br>".join(parts).replace("\n", "<br>"))
        else:
            doc = getattr(tool, "__doc__", None) or ""
            self._help_browser.setPlainText(doc)

    def _on_execute(self):
        """Execute the active tool."""
        tool = self._tools_manager.getActive()
        self._var_form.read_values(tool)
        tool.save()
        try:
            tool.execute(self._app_proxy)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(
                self, _("Execution error"),
                f"{tool.name}: {e}")

    def _on_db_add(self):
        tool = self._tools_manager.getActive()
        if not isinstance(tool, DataBase):
            return
        tool.add(rename=False)
        # Re-populate form after add
        self._var_form.populate(tool, self._tools_manager)

    def _on_db_delete(self):
        tool = self._tools_manager.getActive()
        if not isinstance(tool, DataBase):
            return
        tool.delete()
        self._var_form.populate(tool, self._tools_manager)

    def _on_db_clone(self):
        tool = self._tools_manager.getActive()
        if not isinstance(tool, DataBase):
            return
        tool.clone()
        self._var_form.populate(tool, self._tools_manager)

    def _on_db_rename(self):
        tool = self._tools_manager.getActive()
        if not isinstance(tool, DataBase):
            return
        current_name = tool["name"] if tool.current is not None else ""
        new_name, ok = QInputDialog.getText(
            self, _("Rename"), _("New name:"),
            text=current_name)
        if ok and new_name:
            tool["name"] = new_name
            self._var_form.populate(tool, self._tools_manager)

    def saveConfig(self):
        """Save current tool values before closing."""
        tool = self._tools_manager.getActive()
        self._var_form.read_values(tool)
        self._tools_manager.saveConfig()
