# Qt Editor Panel - port of CNCList.py CNCListbox + EditorPage.py
#
# Two-level QTreeView showing gcode blocks and lines with
# toolbar, filter, selection/mutation methods, and clipboard support.

import json
import re

from PySide6.QtCore import Qt, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeView, QLineEdit, QToolBar, QToolButton,
    QMenu, QAbstractItemView,
    QApplication, QColorDialog,
)

from CNC import CNC, Block

from .editor_model import GCodeTreeModel

MAXINT = 1000000000


class EditorPanel(QWidget):
    """G-code editor panel with block/line tree view."""

    def __init__(self, gcode, signals, parent=None):
        super().__init__(parent)
        self.gcode = gcode
        self.signals = signals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # --- Toolbar ---
        self._setup_toolbar(layout)

        # --- Filter ---
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter blocks...")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self._filter_edit)

        # --- Model ---
        self._model = GCodeTreeModel(gcode)
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setRecursiveFilteringEnabled(True)
        self._proxy.setFilterRole(Qt.ItemDataRole.DisplayRole)

        # --- Tree view ---
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed)
        self._tree.setAnimated(False)
        self._tree.setIndentation(16)
        self._tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(
            self._show_context_menu)
        layout.addWidget(self._tree)

        # Selection change signal
        self._tree.selectionModel().selectionChanged.connect(
            self._on_selection_changed)

        # Double-click on a block row toggles expand/collapse
        self._tree.doubleClicked.connect(self._on_clicked)
        # Sync block.expand when user uses the tree arrow directly
        self._tree.expanded.connect(self._on_tree_expanded)
        self._tree.collapsed.connect(self._on_tree_collapsed)

        # --- Keyboard shortcuts ---
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _setup_toolbar(self, layout):
        toolbar = QToolBar()
        toolbar.setIconSize(toolbar.iconSize())
        toolbar.setMovable(False)

        # Add dropdown (line/block)
        add_btn = QToolButton()
        add_btn.setText("Add")
        add_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        add_menu = QMenu(add_btn)
        add_menu.addAction("Add Line", self.insert_line)
        add_menu.addAction("Add Block", self.insert_block)
        add_btn.setMenu(add_menu)
        toolbar.addWidget(add_btn)

        act = toolbar.addAction("Delete", self.delete_block)
        act.setToolTip("Delete selected blocks/lines")

        act = toolbar.addAction("Clone", self.clone)
        act.setToolTip("Clone selected blocks/lines")

        toolbar.addSeparator()

        act = toolbar.addAction("Enable", self.toggle_enable)
        act.setToolTip("Toggle enable/disable")

        act = toolbar.addAction("Expand", self.toggle_expand)
        act.setToolTip("Toggle expand/collapse")

        toolbar.addSeparator()

        act = toolbar.addAction("Up", self.order_up)
        act.setToolTip("Move selection up")

        act = toolbar.addAction("Down", self.order_down)
        act.setToolTip("Move selection down")

        act = toolbar.addAction("Invert", self.invert_blocks)
        act.setToolTip("Invert block order")

        layout.addWidget(toolbar)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------
    def _setup_shortcuts(self):
        def _sc(key, slot):
            s = QShortcut(QKeySequence(key), self._tree)
            s.setContext(Qt.ShortcutContext.WidgetShortcut)
            s.activated.connect(slot)

        _sc("Delete", self.delete_block)
        _sc("Ctrl+D", self.clone)
        _sc("Ctrl+E", self.toggle_expand)
        _sc("Ctrl+L", self.toggle_enable)
        _sc("Ctrl+Up", self.order_up)
        _sc("Ctrl+Down", self.order_down)
        _sc("Insert", self.insert_item)
        _sc("Ctrl+Return", self.insert_item)

    # ------------------------------------------------------------------
    # Fill / refresh
    # ------------------------------------------------------------------
    def fill(self, *_args):
        """Rebuild tree from gcode.blocks."""
        self._model.refresh()
        self._sync_expand_state()

    # ------------------------------------------------------------------
    # Selection methods
    # ------------------------------------------------------------------
    def get_selection(self):
        """Return [(bid, lid_or_None), ...] for selected items."""
        result = []
        for proxy_idx in self._tree.selectionModel().selectedIndexes():
            src_idx = self._proxy.mapToSource(proxy_idx)
            item = self._model.item_id(src_idx)
            if item is not None:
                result.append(item)
        return result

    def get_selected_blocks(self):
        """Return sorted unique block ids that have any selection."""
        blocks = {}
        for bid, lid in self.get_selection():
            blocks[bid] = True
        return sorted(blocks.keys())

    def get_clean_selection(self):
        """Return selection with lines omitted if their block is also selected."""
        items = list(self.get_selection())
        if not items:
            return items
        blocks = {}
        i = 0
        while i < len(items):
            bid, lid = items[i]
            if lid is None:
                blocks[bid] = True
                i += 1
            elif blocks.get(bid, False):
                del items[i]
            else:
                i += 1
        return items

    def select_all(self):
        self._tree.selectAll()

    def select_clear(self):
        self._tree.clearSelection()

    def select_invert(self):
        sel_model = self._tree.selectionModel()
        # Iterate all top-level (block) items
        for row in range(self._proxy.rowCount()):
            block_idx = self._proxy.index(row, 0)
            sel_model.select(
                block_idx,
                sel_model.SelectionFlag.Toggle)
            # Also toggle children
            for child_row in range(self._proxy.rowCount(block_idx)):
                child_idx = self._proxy.index(child_row, 0, block_idx)
                sel_model.select(
                    child_idx,
                    sel_model.SelectionFlag.Toggle)

    def select_layer(self):
        """Select all blocks with the same name as currently selected."""
        for bid in self.get_selected_blocks():
            name = self.gcode.blocks[bid].nameNop()
            for i, bl in enumerate(self.gcode.blocks):
                if name == bl.nameNop():
                    idx = self._proxy.mapFromSource(
                        self._model.block_index(i))
                    if idx.isValid():
                        self._tree.selectionModel().select(
                            idx,
                            self._tree.selectionModel().SelectionFlag.Select)

    def add_to_selection(self, block_ids):
        """Add blocks to current selection (for ctrl-click from canvas)."""
        sel = self._tree.selectionModel()
        for bid in block_ids:
            idx = self._proxy.mapFromSource(self._model.block_index(bid))
            if idx.isValid():
                sel.select(idx, sel.SelectionFlag.Select)
        if block_ids:
            last = self._proxy.mapFromSource(
                self._model.block_index(block_ids[-1]))
            if last.isValid():
                self._tree.scrollTo(last)

    def select_blocks(self, block_ids):
        """Select specific blocks by id."""
        self._tree.clearSelection()
        sel = self._tree.selectionModel()
        for bid in block_ids:
            idx = self._proxy.mapFromSource(self._model.block_index(bid))
            if idx.isValid():
                sel.select(idx, sel.SelectionFlag.Select)
        if block_ids:
            first = self._proxy.mapFromSource(
                self._model.block_index(block_ids[0]))
            if first.isValid():
                self._tree.scrollTo(first)

    def select_items(self, items):
        """Select specific (bid, lid_or_None) items."""
        self._tree.clearSelection()
        sel = self._tree.selectionModel()
        first_idx = None
        for bid, lid in items:
            if lid is None:
                idx = self._proxy.mapFromSource(
                    self._model.block_index(bid))
            else:
                idx = self._proxy.mapFromSource(
                    self._model.line_index(bid, lid))
            if idx.isValid():
                sel.select(idx, sel.SelectionFlag.Select)
                if first_idx is None:
                    first_idx = idx
        if first_idx is not None:
            self._tree.scrollTo(first_idx)

    # ------------------------------------------------------------------
    # Mutation methods
    # ------------------------------------------------------------------
    def insert_item(self):
        """Insert line or block depending on what's active."""
        sel = self.get_selection()
        if not sel:
            self.insert_block()
            return
        bid, lid = sel[-1]
        if lid is None:
            self.insert_block()
        else:
            self.insert_line()

    def insert_block(self):
        """Insert a new block after the current selection."""
        sel = self.get_selection()
        if sel:
            bid = sel[-1][0] + 1
        else:
            bid = len(self.gcode.blocks)

        block = Block()
        block.expand = True
        block.append("g0 x0 y0")
        block.append("g1 z0")
        block.append(CNC.zsafe())
        self.gcode.addUndo(self.gcode.addBlockUndo(bid, block))
        self._on_modified()
        self.select_blocks([bid])

    def insert_line(self):
        """Insert a new empty line after the current selection."""
        sel = self.get_selection()
        if not sel:
            self.insert_block()
            return
        bid, lid = sel[-1]
        if lid is None:
            lid = 0
        else:
            lid += 1
        self.gcode.addUndo(self.gcode.insLineUndo(bid, lid, ""))
        self._on_modified()
        # Start editing the new line
        idx = self._proxy.mapFromSource(self._model.line_index(bid, lid))
        if idx.isValid():
            self._tree.setCurrentIndex(idx)
            self._tree.edit(idx)

    def delete_block(self):
        """Delete selected blocks and lines."""
        sel = self.get_clean_selection()
        if not sel:
            return
        undoinfo = []
        for bid, lid in reversed(sel):
            if isinstance(lid, int):
                undoinfo.append(self.gcode.delLineUndo(bid, lid))
            else:
                undoinfo.append(self.gcode.delBlockUndo(bid))
        self.gcode.addUndo(undoinfo)
        self._on_modified()

    def clone(self):
        """Clone selected blocks/lines."""
        sel = self.get_selection()
        if not sel:
            return
        undoinfo = []
        pos = sel[-1][0] + 1
        new_blocks = []
        for bid, lid in reversed(sel):
            if lid is None:
                undoinfo.append(self.gcode.cloneBlockUndo(bid, pos))
                for i in range(len(new_blocks)):
                    new_blocks[i] += 1
                new_blocks.append(pos)
            else:
                undoinfo.append(self.gcode.cloneLineUndo(bid, lid))
        self.gcode.addUndo(undoinfo)
        self._on_modified()
        if new_blocks:
            self.select_blocks(new_blocks)

    def toggle_expand(self):
        """Toggle expand/collapse for selected blocks."""
        sel = self.get_selection()
        if not sel:
            return
        expand = None
        blocks_seen = set()
        undoinfo = []
        for bid, lid in sel:
            if bid in blocks_seen:
                continue
            blocks_seen.add(bid)
            if expand is None:
                expand = not self.gcode.blocks[bid].expand
            undoinfo.append(self.gcode.setBlockExpandUndo(bid, expand))
        if undoinfo:
            self.gcode.addUndo(undoinfo)
            self._on_modified()
            self.select_blocks(list(blocks_seen))

    def toggle_enable(self):
        """Toggle enable/disable for selected blocks."""
        self._set_enable(None)

    def enable(self):
        self._set_enable(True)

    def disable(self):
        self._set_enable(False)

    def _set_enable(self, enable=None):
        sel = self.get_selection()
        if not sel:
            return
        blocks_seen = set()
        undoinfo = []
        for bid, lid in sel:
            if bid in blocks_seen:
                continue
            blocks_seen.add(bid)
            block = self.gcode.blocks[bid]
            if block.name() in ("Header", "Footer"):
                continue
            if enable is None:
                enable = not block.enable
            undoinfo.append(self.gcode.setBlockEnableUndo(bid, enable))
        if undoinfo:
            self.gcode.calculateEnableMargins()
            self.gcode.addUndo(undoinfo)
            self._on_modified()

    def comment_row(self):
        """Toggle comment on selected lines."""
        sel = self.get_selection()
        if not sel:
            return
        mreg = re.compile(r"^\((.*)\)$")
        changed = False
        for bid, lid in sel:
            if lid is not None:
                changed = True
                line = self.gcode.blocks[bid][lid]
                m = mreg.search(line)
                if m is None:
                    self.gcode.blocks[bid][lid] = "(" + line + ")"
                else:
                    self.gcode.blocks[bid][lid] = m.group(1)
        if changed:
            self._on_modified()

    def join_blocks(self):
        """Join selected blocks into one."""
        blocks = self.get_selected_blocks()
        if len(blocks) < 2:
            return
        bl = Block(self.gcode.blocks[blocks[0]].name())
        for bid in blocks:
            for line in self.gcode.blocks[bid]:
                bl.append(line)
            bl.append("( ---------- cut-here ---------- )")
        del bl[-1]
        last = blocks[-1]
        self.gcode.addUndo(self.gcode.addBlockUndo(last + 1, bl))
        # delete original blocks
        undoinfo = []
        for bid in reversed(blocks):
            undoinfo.append(self.gcode.delBlockUndo(bid))
        self.gcode.addUndo(undoinfo)
        self._on_modified()

    def split_blocks(self):
        """Split selected blocks at cut-here markers."""
        blocks = self.get_selected_blocks()
        if not blocks:
            return
        for bid in blocks:
            bl = Block(self.gcode.blocks[bid].name())
            for line in self.gcode.blocks[bid]:
                if line == "( ---------- cut-here ---------- )":
                    self.gcode.addUndo(
                        self.gcode.addBlockUndo(bid + 1, bl))
                    bl = Block(self.gcode.blocks[bid].name())
                else:
                    bl.append(line)
            self.gcode.addUndo(self.gcode.addBlockUndo(bid + 1, bl))
        # delete originals
        undoinfo = []
        for bid in reversed(blocks):
            undoinfo.append(self.gcode.delBlockUndo(bid))
        self.gcode.addUndo(undoinfo)
        self._on_modified()

    def change_color(self, color):
        """Set color on selected blocks."""
        sel = self.get_selection()
        if not sel:
            return
        blocks_seen = set()
        undoinfo = []
        for bid, lid in reversed(sel):
            if bid in blocks_seen:
                continue
            blocks_seen.add(bid)
            undoinfo.append(
                self.gcode.setBlockColorUndo(bid, self.gcode.blocks[bid].color))
        if undoinfo:
            self.gcode.addUndo(undoinfo)
            for bid in blocks_seen:
                self.gcode.blocks[bid].color = color
            self._on_modified()

    def order_up(self):
        """Move selected items up."""
        items = self.get_clean_selection()
        if not items:
            return
        sel = self.gcode.orderUp(items)
        self._on_modified()
        self.select_items(sel)

    def order_down(self):
        """Move selected items down."""
        items = self.get_clean_selection()
        if not items:
            return
        sel = self.gcode.orderDown(items)
        self._on_modified()
        self.select_items(sel)

    def invert_blocks(self):
        """Invert order of selected blocks."""
        blocks = self.get_selected_blocks()
        if not blocks:
            return
        self.gcode.addUndo(self.gcode.invertBlocksUndo(blocks))
        self._on_modified()

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------
    def copy(self):
        """Copy selected items to clipboard as JSON."""
        clipboard_data = []
        for bid, lid in self.get_clean_selection():
            if lid is None:
                clipboard_data.append(self.gcode.blocks[bid].dump())
            else:
                clipboard_data.append(self.gcode.blocks[bid][lid])
        QApplication.clipboard().setText(json.dumps(clipboard_data))

    def cut(self):
        self.copy()
        self.delete_block()

    def paste(self):
        """Paste from clipboard after current selection."""
        text = QApplication.clipboard().text()
        if not text:
            return

        # Determine insert position
        sel = self.get_selection()
        if sel:
            bid, lid = sel[-1]
        else:
            bid = len(self.gcode.blocks) - 1
            lid = None

        undoinfo = []
        sel_items = []

        def add_lines(lines):
            nonlocal bid, lid
            for line in lines.splitlines():
                if lid is None:
                    bid += 1
                    if bid > len(self.gcode.blocks):
                        bid = len(self.gcode.blocks)
                    lid = MAXINT
                    block = Block()
                    undoinfo.append(self.gcode.addBlockUndo(bid, block))
                    sel_items.append((bid, None))
                else:
                    pass  # block already exists

                block = self.gcode.blocks[bid]
                if lid == MAXINT:
                    lid = len(block)
                    sel_items.append((bid, len(block)))
                else:
                    lid += 1
                    sel_items.append((bid, lid))
                undoinfo.append(self.gcode.insLineUndo(bid, lid, line))

        try:
            objs = json.loads(text)
        except Exception:
            objs = [text]

        for obj in objs:
            if isinstance(obj, list):
                obj = tuple(obj)
            if isinstance(obj, tuple):
                block = Block.load(obj)
                bid += 1
                undoinfo.append(self.gcode.addBlockUndo(bid, block))
                sel_items.append((bid, None))
                lid = None
            else:
                add_lines(obj)

        if not undoinfo:
            return
        self.gcode.addUndo(undoinfo)
        self._on_modified()
        self.select_items(sel_items)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------
    def _show_context_menu(self, pos):
        sel = self.get_selection()
        has_sel = bool(sel)
        has_blocks = bool(self.get_selected_blocks())
        has_lines = any(lid is not None for _, lid in sel) if sel else False
        clipboard_has_text = bool(QApplication.clipboard().text())

        menu = QMenu(self._tree)

        # Clipboard group
        menu.addAction("Cut\tCtrl+X", self.cut).setEnabled(has_sel)
        menu.addAction("Copy\tCtrl+C", self.copy).setEnabled(has_sel)
        menu.addAction("Paste\tCtrl+V", self.paste).setEnabled(
            clipboard_has_text)
        menu.addSeparator()

        # Add / Clone / Delete
        menu.addAction("Add Line", self.insert_line)
        menu.addAction("Add Block", self.insert_block)
        menu.addAction("Clone\tCtrl+D", self.clone).setEnabled(has_sel)
        menu.addAction("Delete\tDel", self.delete_block).setEnabled(has_sel)
        menu.addSeparator()

        # Block toggles
        menu.addAction(
            "Enable/Disable\tCtrl+L", self.toggle_enable
        ).setEnabled(has_blocks)
        menu.addAction(
            "Expand/Collapse\tCtrl+E", self.toggle_expand
        ).setEnabled(has_blocks)
        menu.addAction("Comment", self.comment_row).setEnabled(has_lines)
        menu.addSeparator()

        # Ordering
        menu.addAction("Move Up\tCtrl+Up", self.order_up).setEnabled(has_sel)
        menu.addAction(
            "Move Down\tCtrl+Down", self.order_down
        ).setEnabled(has_sel)
        menu.addSeparator()

        # Join / Split
        menu.addAction("Join Blocks", self.join_blocks).setEnabled(
            len(self.get_selected_blocks()) >= 2 if has_blocks else False)
        menu.addAction("Split Blocks", self.split_blocks).setEnabled(
            has_blocks)
        menu.addSeparator()

        # Selection
        menu.addAction("Select All\tCtrl+A", self.select_all)
        menu.addAction("Select None", self.select_clear)
        menu.addAction("Select Invert", self.select_invert)
        menu.addAction("Select Layer", self.select_layer).setEnabled(
            has_blocks)
        menu.addSeparator()

        # Color submenu
        color_menu = menu.addMenu("Color")
        color_menu.setEnabled(has_blocks)
        colors = [
            ("Black", "black"), ("Red", "red"), ("Green", "green"),
            ("Blue", "blue"), ("Yellow", "yellow"), ("Magenta", "magenta"),
            ("Cyan", "cyan"), ("Orange", "orange"),
        ]
        for label, value in colors:
            color_menu.addAction(
                label, lambda v=value: self.change_color(v))
        color_menu.addSeparator()
        color_menu.addAction("Custom...", self._pick_custom_color)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _pick_custom_color(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.change_color(color.name())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _on_modified(self):
        self._model.refresh()
        self._sync_expand_state()
        self.signals.modified.emit()
        self.signals.draw_requested.emit()

    def _on_selection_changed(self):
        self.signals.selection_changed.emit()

    def _on_clicked(self, proxy_idx):
        """Toggle expand/collapse when a block row is clicked."""
        if proxy_idx.parent().isValid():
            return  # line row, not a block
        expanded = self._tree.isExpanded(proxy_idx)
        self._tree.setExpanded(proxy_idx, not expanded)
        src_idx = self._proxy.mapToSource(proxy_idx)
        if src_idx.isValid():
            bid = src_idx.row()
            if 0 <= bid < len(self.gcode.blocks):
                self.gcode.blocks[bid].expand = not expanded

    def _on_tree_expanded(self, proxy_idx):
        """Sync block.expand when tree node is expanded via arrow."""
        src_idx = self._proxy.mapToSource(proxy_idx)
        if src_idx.isValid():
            bid = src_idx.row()
            if 0 <= bid < len(self.gcode.blocks):
                self.gcode.blocks[bid].expand = True

    def _on_tree_collapsed(self, proxy_idx):
        """Sync block.expand when tree node is collapsed via arrow."""
        src_idx = self._proxy.mapToSource(proxy_idx)
        if src_idx.isValid():
            bid = src_idx.row()
            if 0 <= bid < len(self.gcode.blocks):
                self.gcode.blocks[bid].expand = False

    def _sync_expand_state(self):
        """Sync tree expanded/collapsed state with block.expand flags."""
        for bid, block in enumerate(self.gcode.blocks):
            proxy_idx = self._proxy.mapFromSource(
                self._model.block_index(bid))
            if proxy_idx.isValid():
                self._tree.setExpanded(proxy_idx, block.expand)

    def _on_filter_changed(self, text):
        self._proxy.setFilterFixedString(text)
