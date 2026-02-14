# Qt tree model for gcode blocks and lines
#
# Two-level hierarchy: blocks are root rows, gcode lines are children.
# References gcode.blocks directly — no parallel arrays to sync.

from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel
from PySide6.QtGui import QColor

from CNC import Block

BLOCK_BG = QColor("LightYellow")
COMMENT_FG = QColor("Blue")
DISABLE_FG = QColor("Gray")

# Sentinel used as internalId for block rows (no parent block)
_BLOCK_ID = 0xFFFFFFFF


class GCodeTreeModel(QAbstractItemModel):
    """Two-level tree model over gcode.blocks.

    Root rows  = blocks (bid).  internalId = _BLOCK_ID
    Child rows = lines (lid).   internalId = parent block index
    """

    def __init__(self, gcode, parent=None):
        super().__init__(parent)
        self.gcode = gcode

    # ---- structure --------------------------------------------------------

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            # Block row
            return self.createIndex(row, column, _BLOCK_ID)
        # Line row — parent is a block
        bid = parent.row()
        return self.createIndex(row, column, bid)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        iid = index.internalId()
        if iid == _BLOCK_ID:
            return QModelIndex()  # block has no parent
        # line's parent is block at row=iid
        return self.createIndex(iid, 0, _BLOCK_ID)

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self.gcode.blocks)
        iid = parent.internalId()
        if iid == _BLOCK_ID:
            # parent is a block — children are its lines
            bid = parent.row()
            if 0 <= bid < len(self.gcode.blocks):
                return len(self.gcode.blocks[bid])
            return 0
        # lines have no children
        return 0

    def columnCount(self, parent=QModelIndex()):
        return 1

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = (Qt.ItemFlag.ItemIsEnabled
                 | Qt.ItemFlag.ItemIsSelectable
                 | Qt.ItemFlag.ItemIsEditable)
        return flags

    # ---- data -------------------------------------------------------------

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        iid = index.internalId()
        is_block = (iid == _BLOCK_ID)

        if is_block:
            bid = index.row()
            if bid >= len(self.gcode.blocks):
                return None
            block = self.gcode.blocks[bid]
            return self._block_data(block, bid, role)
        else:
            bid = iid
            lid = index.row()
            if bid >= len(self.gcode.blocks):
                return None
            block = self.gcode.blocks[bid]
            if lid >= len(block):
                return None
            return self._line_data(block, lid, role)

    def _block_data(self, block, bid, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return block.header()
        if role == Qt.ItemDataRole.EditRole:
            return block.name()
        if role == Qt.ItemDataRole.ForegroundRole:
            if not block.enable:
                return DISABLE_FG
            return None
        if role == Qt.ItemDataRole.BackgroundRole:
            return BLOCK_BG
        return None

    def _line_data(self, block, lid, role):
        line = block[lid]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return line
        if role == Qt.ItemDataRole.ForegroundRole:
            if not block.enable:
                return DISABLE_FG
            if line and line[0] in ("(", "%"):
                return COMMENT_FG
            return None
        return None

    # ---- editing ----------------------------------------------------------

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        iid = index.internalId()
        is_block = (iid == _BLOCK_ID)

        if is_block:
            bid = index.row()
            if bid >= len(self.gcode.blocks):
                return False
            old = self.gcode.blocks[bid].name()
            if value == old:
                return False
            self.gcode.addUndo(self.gcode.setBlockNameUndo(bid, value))
        else:
            bid = iid
            lid = index.row()
            if bid >= len(self.gcode.blocks):
                return False
            block = self.gcode.blocks[bid]
            if lid >= len(block):
                return False
            old = block[lid]
            if value == old:
                return False
            self.gcode.addUndo(self.gcode.setLineUndo(bid, lid, value))

        self.dataChanged.emit(index, index, [role])
        return True

    # ---- refresh ----------------------------------------------------------

    def refresh(self):
        """Full reset after any structural mutation."""
        self.beginResetModel()
        self.endResetModel()

    # ---- helpers ----------------------------------------------------------

    def block_index(self, bid):
        """Return QModelIndex for a block row."""
        if 0 <= bid < len(self.gcode.blocks):
            return self.createIndex(bid, 0, _BLOCK_ID)
        return QModelIndex()

    def line_index(self, bid, lid):
        """Return QModelIndex for a line within a block."""
        if 0 <= bid < len(self.gcode.blocks):
            block = self.gcode.blocks[bid]
            if 0 <= lid < len(block):
                return self.createIndex(lid, 0, bid)
        return QModelIndex()

    def item_id(self, index):
        """Return (bid, lid_or_None) for a given index."""
        if not index.isValid():
            return None
        iid = index.internalId()
        if iid == _BLOCK_ID:
            return (index.row(), None)
        return (iid, index.row())
