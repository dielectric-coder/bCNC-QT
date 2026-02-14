# Qt Application Entry Point
#
# Launches the Qt-based bCNC interface.  This is the Qt equivalent
# of running bCNC through __main__.py with the Tkinter UI.
#
# Usage:
#     python -m bCNC.qt.app
#   or from the bCNC directory:
#     python qt/app.py

import os
import sys

# Determine base directory — PyInstaller extracts to sys._MEIPASS
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _bCNC_dir = sys._MEIPASS
else:
    _bCNC_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure bCNC package is on the path
if _bCNC_dir not in sys.path:
    sys.path.insert(0, _bCNC_dir)
# Also add lib/ for tkExtra, rexx, etc.
_lib_dir = os.path.join(_bCNC_dir, "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
# Also add controllers/ and plugins/
_ctrl_dir = os.path.join(_bCNC_dir, "controllers")
if _ctrl_dir not in sys.path:
    sys.path.insert(0, _ctrl_dir)
_plug_dir = os.path.join(_bCNC_dir, "plugins")
if _plug_dir not in sys.path:
    sys.path.insert(0, _plug_dir)

# Install _() translation builtin before any other bCNC imports
# (Helpers.py does gettext.install() which puts _() in builtins)
import Helpers  # noqa: F401

import utils_core as Utils
Utils.loadConfiguration()

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from CNC import CNC
from Sender import Sender

from .main_window import MainWindow


def main():
    """Create the QApplication, Sender, and MainWindow, then run."""

    app = QApplication(sys.argv)
    app.setApplicationName("bCNC")
    app.setApplicationVersion(Utils.__version__)

    # Create the Sender (backend — no UI dependency)
    sender = Sender()
    sender.loadConfig()

    # Create and show the main window
    window = MainWindow(sender)
    window.show()

    # Load file from command line if provided
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and os.path.isfile(args[0]):
        sender.load(args[0])
        Utils.addRecent(args[0])
        window.signals.file_loaded.emit(args[0])

    # Initial draw and select all blocks (highlights paths like Tkinter)
    window._on_draw()
    if args and os.path.isfile(args[0]):
        window.editor_panel.select_all()
    window._update_title()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
