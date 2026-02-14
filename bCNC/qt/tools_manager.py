# Qt Tools Manager - Tkinter-free replacement for ToolsPage.Tools
#
# Loads all 15 built-in tool classes and 43+ external plugins from
# ToolsPage without requiring a Tk root or StringVar.

import glob
import os
import sys
import traceback
from operator import attrgetter

from PySide6.QtCore import QObject, Signal

import utils_core as Utils


class _NoOpListbox:
    """Stub that absorbs Tkinter listbox calls from _Base.populate()."""

    def event_generate(self, *args, **kwargs):
        pass

    def delete(self, *args):
        pass

    def insert(self, *args):
        pass

    def selection_clear(self, *args):
        pass

    def selection_set(self, *args):
        pass

    def activate(self, *args):
        pass

    def see(self, *args):
        pass

    def index(self, *args):
        return 0

    def get(self, *args):
        return ""

    def size(self):
        return 0

    def yview(self):
        return (0.0, 1.0)

    def listbox(self, *args):
        return self


class ToolsManager(QObject):
    """Tkinter-free replacement for ToolsPage.Tools.

    Loads built-in tool classes and plugins, manages active tool,
    provides config load/save.  Uses _NoOpListbox to absorb any
    calls tools make to the old Tkinter listbox.
    """

    active_changed = Signal(str)

    def __init__(self, gcode, parent=None):
        super().__init__(parent)
        self.gcode = gcode
        self.inches = False
        self.digits = 4
        self._active = "CNC"

        self.tools = {}
        self.buttons = {}
        self.listbox = _NoOpListbox()
        self.widget = {}

        # Import tool classes from tools_base (no tkinter dependency)
        from tools_base import (
            Camera, Config, Font, Color, Controller,
            Cut, Drill, EndMill, Events, Material,
            Pocket, Profile, Shortcut, Stock, Tabs,
        )

        for cls in [
            Camera, Config, Font, Color, Controller,
            Cut, Drill, EndMill, Events, Material,
            Pocket, Profile, Shortcut, Stock, Tabs,
        ]:
            tool = cls(self)
            self.addTool(tool)

        # Discover and load plugins
        for f in glob.glob(f"{Utils.prgpath}/plugins/*.py"):
            name, _ext = os.path.splitext(os.path.basename(f))
            try:
                package = __import__(name, globals(), locals(), [], 0)
                tool = package.Tool(self)
                self.addTool(tool)
            except Exception:
                typ, val, tb = sys.exc_info()
                traceback.print_exception(typ, val, tb)

    def addTool(self, tool):
        self.tools[tool.name.upper()] = tool

    def __getitem__(self, name):
        return self.tools[name.upper()]

    def getActive(self):
        try:
            return self.tools[self._active.upper()]
        except KeyError:
            self._active = "CNC"
            return self.tools["CNC"]

    def setActive(self, value):
        self._active = value
        self.active_changed.emit(value)

    def toMm(self, value):
        if self.inches:
            return value * 25.4
        return value

    def fromMm(self, value):
        if self.inches:
            return value / 25.4
        return value

    def names(self):
        lst = [x.name for x in self.tools.values()]
        lst.sort()
        return lst

    def pluginList(self):
        plugins = [x for x in self.tools.values() if x.plugin]
        return sorted(plugins, key=attrgetter("name"))

    def cnc(self):
        return self.gcode.cnc

    def addButton(self, name, button):
        self.buttons[name] = button

    def loadConfig(self):
        self._active = Utils.getStr(Utils.__prg__, "tool", "CNC")
        for tool in self.tools.values():
            tool.load()

    def saveConfig(self):
        Utils.setStr(Utils.__prg__, "tool", self._active)
        for tool in self.tools.values():
            tool.save()
