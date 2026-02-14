""" This file is a collection of simple helper functions. It was necessary to
remove them from other files, since there were circular imports.
XXX: This file might be removed, once the circular imports are cleared.
"""

import os
import gettext
import sys

_localedir = os.path.join(
    sys._MEIPASS if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
    else os.path.abspath(os.path.dirname(__file__)),
    "locales",
)
gettext.install("bCNC", localedir=_localedir if os.path.isdir(_localedir) else None)

__all__ = (
    "to_zip",
)

__prg__ = "bCNC"
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    prgpath = sys._MEIPASS
else:
    prgpath = os.path.abspath(os.path.dirname(__file__))


def to_zip(*args, **kwargs):
    return list(zip(*args, **kwargs))


def N_(message):
    return message
