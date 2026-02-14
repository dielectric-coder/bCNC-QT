# FileManager - Toolkit-independent file operations
#
# Wraps GCode file I/O with EventBus notifications.
# The UI layer subscribes to events and handles dialogs,
# editor refresh, and title bar updates.

import os

import utils_core as Utils
from CNC import GCode
from EventBus import bus as event_bus


class FileManager:
    """Manages file operations for GCode, probe, and orientation files.

    Emits events via EventBus so the UI can react without
    being directly coupled.

    Events emitted:
        "file_loaded"       (filename, file_type)
        "file_saved"        (filename)
        "file_new"          ()
        "file_imported"     (filename, blocks)
        "status_message"    (message)
    """

    def __init__(self, sender):
        """
        Args:
            sender: The Sender instance that owns gcode and
                    handles backend file I/O.
        """
        self._sender = sender

    @property
    def gcode(self):
        return self._sender.gcode

    def new_file(self):
        """Initialize a new empty GCode file.

        Returns:
            True on success.
        """
        self.gcode.init()
        self.gcode.headerFooter()
        event_bus.emit("file_new")
        return True

    def load(self, filename):
        """Load a file (g-code, probe, orient, DXF, SVG).

        Delegates to Sender.load() for the actual I/O.
        Emits "file_loaded" with the filename and detected type.

        Args:
            filename: Path to the file.

        Returns:
            str: The file type ("probe", "orient", "mesh_info", "gcode").
        """
        fn, ext = os.path.splitext(filename)
        ext = ext.lower()

        event_bus.emit("status_message",
                       _("Loading: {} ...").format(filename))
        self._sender.load(filename)

        if ext == ".probe":
            file_type = "probe"
        elif ext == ".orient":
            file_type = "orient"
        elif ext in (".stl", ".ply"):
            file_type = "mesh_info"
        else:
            file_type = "gcode"

        Utils.addRecent(filename)
        event_bus.emit("file_loaded", filename, file_type)
        event_bus.emit("status_message",
                       _("'{}' loaded").format(filename))
        return file_type

    def save(self, filename):
        """Save to filename.

        Args:
            filename: Path to save to.
        """
        self._sender.save(filename)
        event_bus.emit("file_saved", filename)
        event_bus.emit("status_message",
                       _("'{}' saved").format(filename))

    def save_all(self):
        """Save all (gcode + probe if exists).

        Returns:
            True if saved, False if no filename set.
        """
        if self.gcode.filename:
            self._sender.saveAll()
            event_bus.emit("file_saved", self.gcode.filename)
            return True
        return False

    def import_file(self, filename):
        """Import a G-code or DXF file, returning new blocks.

        The imported blocks are NOT inserted into the main gcode.
        The caller is responsible for insertion (since that requires
        knowing the editor selection position).

        Args:
            filename: Path to import.

        Returns:
            list: The imported GCode blocks, or None on failure.
        """
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
        event_bus.emit("file_imported", filename, blocks)
        return blocks

    def is_modified(self):
        """Check if gcode or probe data has unsaved changes.

        Returns:
            tuple: (gcode_modified: bool, probe_modified: bool)
        """
        gcode_mod = self.gcode.isModified()
        probe_mod = (not self.gcode.probe.isEmpty()
                     and not self.gcode.probe.saved)
        return gcode_mod, probe_mod
