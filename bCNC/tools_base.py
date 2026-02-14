# Toolkit-independent tool base classes extracted from ToolsPage.py
#
# This module contains _Base, DataBase, Plugin, and all 15 built-in tool
# classes.  It imports only utils_core (no tkinter), so it can be used by
# both the Qt app and plugins without pulling in the Tkinter stack.
#
# The original ToolsPage.py re-exports everything here via
# ``from tools_base import *`` and lazily loads Tkinter UI classes only
# when they are accessed.
#
# Author: Vasilis Vlachoudis
#  Email: Vasilis.Vlachoudis@cern.ch
#   Date: 24-Aug-2014

import time

import utils_core as Utils
from CNC import CNC
from Helpers import N_

__author__ = "Vasilis Vlachoudis"
__email__ = "Vasilis.Vlachoudis@cern.ch"


# =============================================================================
# Tools Base class
# =============================================================================
class _Base:
    def __init__(self, master, name=None):
        self.master = master
        self.name = name
        self.icon = None
        self.plugin = False
        self.variables = []  # name, type, default, label
        self.values = {}  # database of values
        self.listdb = {}  # lists database
        self.current = None  # currently editing index
        self.n = 0
        self.buttons = []

    # ----------------------------------------------------------------------
    def __setitem__(self, name, value):
        if self.current is None:
            self.values[name] = value
        else:
            self.values["%s.%d" % (name, self.current)] = value

    # ----------------------------------------------------------------------
    def __getitem__(self, name):
        if self.current is None:
            return self.values.get(name, "")
        else:
            return self.values.get("%s.%d" % (name, self.current), "")

    # ----------------------------------------------------------------------
    def gcode(self):
        return self.master.gcode

    # ----------------------------------------------------------------------
    # Return a sorted list of all names
    # ----------------------------------------------------------------------
    def names(self):
        lst = []
        for i in range(1000):
            key = "name.%d" % (i)
            value = self.values.get(key)
            if value is None:
                break
            lst.append(value)
        lst.sort()
        return lst

    # ----------------------------------------------------------------------
    def _get(self, key, t, default):
        if t in ("float", "mm"):
            return Utils.getFloat(self.name, key, default)
        elif t == "int":
            return Utils.getInt(self.name, key, default)
        elif t == "bool":
            return Utils.getInt(self.name, key, default)
        else:
            return Utils.getStr(self.name, key, default)

    # ----------------------------------------------------------------------
    # Override with execute command
    # ----------------------------------------------------------------------
    def execute(self, app):
        pass

    # ----------------------------------------------------------------------
    # Update variables after edit command
    # ----------------------------------------------------------------------
    def update(self):
        return False

    # ----------------------------------------------------------------------
    def event_generate(self, msg, **kwargs):
        self.master.listbox.event_generate(msg, **kwargs)

    # ----------------------------------------------------------------------
    def beforeChange(self, app):
        pass

    # ----------------------------------------------------------------------
    # Tkinter-only: overridden by ToolsPage when tkinter is loaded
    # ----------------------------------------------------------------------
    def populate(self):
        pass

    # ----------------------------------------------------------------------
    # Tkinter-only: overridden by ToolsPage when tkinter is loaded
    # ----------------------------------------------------------------------
    def _sendReturn(self, active):
        pass

    # ----------------------------------------------------------------------
    # Tkinter-only: overridden by ToolsPage when tkinter is loaded
    # ----------------------------------------------------------------------
    def _editPrev(self):
        pass

    # ----------------------------------------------------------------------
    # Tkinter-only: overridden by ToolsPage when tkinter is loaded
    # ----------------------------------------------------------------------
    def _editNext(self):
        pass

    # ----------------------------------------------------------------------
    # Make current "name" from the database
    # ----------------------------------------------------------------------
    def makeCurrent(self, name):
        if not name:
            return
        # special handling
        for i in range(1000):
            if name == self.values.get("name.%d" % (i)):
                self.current = i
                self.update()
                return True
        return False

    # ----------------------------------------------------------------------
    # Tkinter-only: overridden by ToolsPage when tkinter is loaded
    # ----------------------------------------------------------------------
    def edit(self, event=None, rename=False):
        pass

    # =========================================================================
    # Persistence
    # =========================================================================
    # ----------------------------------------------------------------------
    # Load from a configuration file
    # ----------------------------------------------------------------------
    def load(self):
        # Load lists
        lists = []
        for var in self.variables:
            n, t, d, lp = var[:4]
            if t == "list":
                lists.append(n)
        if lists:
            for p in lists:
                self.listdb[p] = []
                for i in range(1000):
                    key = "_%s.%d" % (p, i)
                    value = Utils.getStr(self.name, key).strip()
                    if value:
                        self.listdb[p].append(value)
                    else:
                        break

        # Check if there is a current
        try:
            self.current = int(Utils.config.get(self.name, "current"))
        except Exception:
            self.current = None

        # Load values
        if self.current is not None:
            self.n = self._get("n", "int", 0)
            for i in range(self.n):
                key = "name.%d" % (i)
                self.values[key] = Utils.getStr(self.name, key)
                for var in self.variables:
                    n, t, d, lp = var[:4]
                    key = "%s.%d" % (n, i)
                    self.values[key] = self._get(key, t, d)
        else:
            for var in self.variables:
                n, t, d, lp = var[:4]
                self.values[n] = self._get(n, t, d)
        self.update()

    # ----------------------------------------------------------------------
    # Save to a configuration file
    # ----------------------------------------------------------------------
    def save(self):
        # if section do not exist add it
        Utils.addSection(self.name)

        if self.listdb:
            for name, lst in self.listdb.items():
                for i, value in enumerate(lst):
                    Utils.setStr(self.name, "_%s.%d" % (name, i), value)

        # Save values
        if self.current is not None:
            Utils.setStr(self.name, "current", str(self.current))
            Utils.setStr(self.name, "n", str(self.n))

            for i in range(self.n):
                key = "name.%d" % (i)
                value = self.values.get(key)
                if value is None:
                    break
                Utils.setStr(self.name, key, value)

                for var in self.variables:
                    n, t, d, lp = var[:4]
                    key = "%s.%d" % (n, i)
                    Utils.setStr(self.name, key, str(self.values.get(key, d)))
        else:
            for var in self.variables:
                n, t, d, lp = var[:4]
                val = self.values.get(n, d)
                Utils.setStr(self.name, n, str(val))

    # ----------------------------------------------------------------------
    def fromMm(self, name, default=0.0):
        try:
            return self.master.fromMm(float(self[name]))
        except ValueError:
            return default


# =============================================================================
# Base class of all databases
# =============================================================================
class DataBase(_Base):
    def __init__(self, master, name):
        _Base.__init__(self, master, name)
        self.buttons = ["add", "delete", "clone", "rename"]

    # ----------------------------------------------------------------------
    # Add a new item
    # ----------------------------------------------------------------------
    def add(self, rename=True):
        self.current = self.n
        self.values["name.%d" % (self.n)] = "%s %02d" % (self.name, self.n + 1)
        self.n += 1
        self.populate()
        if rename:
            self.rename()

    # ----------------------------------------------------------------------
    # Delete selected item
    # ----------------------------------------------------------------------
    def delete(self):
        if self.n == 0:
            return
        for var in self.variables:
            n, t, d, lp = var[:4]
            for i in range(self.current, self.n):
                try:
                    self.values["%s.%d" % (n, i)] = self.values[
                        "%s.%d" % (n, i + 1)]
                except KeyError:
                    try:
                        del self.values["%s.%d" % (n, i)]
                    except KeyError:
                        pass

        self.n -= 1
        if self.current >= self.n:
            self.current = self.n - 1
        self.populate()

    # ----------------------------------------------------------------------
    # Clone selected item
    # ----------------------------------------------------------------------
    def clone(self):
        if self.n == 0:
            return
        for var in self.variables:
            n, t, d, lp = var[:4]
            try:
                if n == "name":
                    self.values["%s.%d" % (n, self.n)] = (
                        self.values["%s.%d" % (n, self.current)] + " clone"
                    )
                else:
                    self.values["%s.%d" % (n, self.n)] = self.values[
                        "%s.%d" % (n, self.current)
                    ]
            except KeyError:
                pass
        self.n += 1
        self.current = self.n - 1
        self.populate()

    # ----------------------------------------------------------------------
    # Tkinter-only: overridden by ToolsPage when tkinter is loaded
    # ----------------------------------------------------------------------
    def rename(self):
        pass


# =============================================================================
class Plugin(DataBase):
    def __init__(self, master, name):
        DataBase.__init__(self, master, name)
        self.plugin = True
        self.group = "Macros"
        self.oneshot = False
        self.help = None


# =============================================================================
# Generic ini configuration
# =============================================================================
class Ini(_Base):
    def __init__(self, master, name, vartype, include=(), ignore=()):
        _Base.__init__(self, master)
        self.name = name

        # detect variables from ini file
        for name, value in Utils.config.items(self.name):
            if name in ignore:
                continue
            self.variables.append((name, vartype, value, name))


# -----------------------------------------------------------------------------
class Font(Ini):
    def __init__(self, master):
        Ini.__init__(self, master, "Font", "str")


# -----------------------------------------------------------------------------
class Color(Ini):
    def __init__(self, master):
        Ini.__init__(self, master, "Color", "color")


# -----------------------------------------------------------------------------
class Events(Ini):
    def __init__(self, master):
        Ini.__init__(self, master, "Events", "str")


# -----------------------------------------------------------------------------
class Shortcut(_Base):
    def __init__(self, master):
        _Base.__init__(self, master, "Shortcut")
        self.variables = [
            ("F1", "str", "help", _("F1")),
            ("F2", "str", "edit", _("F2")),
            ("F3", "str", "XY", _("F3")),
            ("F4", "str", "ISO1", _("F4")),
            ("F5", "str", "ISO2", _("F5")),
            ("F6", "str", "ISO3", _("F6")),
            ("F7", "str", "", _("F7")),
            ("F8", "str", "", _("F8")),
            ("F9", "str", "", _("F9")),
            ("F10", "str", "", _("F10")),
            ("F11", "str", "", _("F11")),
            ("F12", "str", "", _("F12")),
            ("Shift-F1", "str", "", _("Shift-") + _("F1")),
            ("Shift-F2", "str", "", _("Shift-") + _("F2")),
            ("Shift-F3", "str", "", _("Shift-") + _("F3")),
            ("Shift-F4", "str", "", _("Shift-") + _("F4")),
            ("Shift-F5", "str", "", _("Shift-") + _("F5")),
            ("Shift-F6", "str", "", _("Shift-") + _("F6")),
            ("Shift-F7", "str", "", _("Shift-") + _("F7")),
            ("Shift-F8", "str", "", _("Shift-") + _("F8")),
            ("Shift-F9", "str", "", _("Shift-") + _("F9")),
            ("Shift-F10", "str", "", _("Shift-") + _("F10")),
            ("Shift-F11", "str", "", _("Shift-") + _("F11")),
            ("Shift-F12", "str", "", _("Shift-") + _("F12")),
            ("Control-F1", "str", "", _("Control-") + _("F1")),
            ("Control-F2", "str", "", _("Control-") + _("F2")),
            ("Control-F3", "str", "", _("Control-") + _("F3")),
            ("Control-F4", "str", "", _("Control-") + _("F4")),
            ("Control-F5", "str", "", _("Control-") + _("F5")),
            ("Control-F6", "str", "", _("Control-") + _("F6")),
            ("Control-F7", "str", "", _("Control-") + _("F7")),
            ("Control-F8", "str", "", _("Control-") + _("F8")),
            ("Control-F9", "str", "", _("Control-") + _("F9")),
            ("Control-F10", "str", "", _("Control-") + _("F10")),
            ("Control-F11", "str", "", _("Control-") + _("F11")),
            ("Control-F12", "str", "", _("Control-") + _("F12")),
        ]
        self.buttons.append("exe")

    # ----------------------------------------------------------------------
    def execute(self, app):
        self.save()
        app.loadShortcuts()


# -----------------------------------------------------------------------------
class Camera(_Base):
    def __init__(self, master):
        _Base.__init__(self, master, "Camera")
        self.variables = [
            ("aligncam", "int", 0, _("Align Camera")),
            ("aligncam_width", "int", 0, _("Align Camera Width")),
            ("aligncam_height", "int", 0, _("Align Camera Height")),
            ("aligncam_angle", "0,90,180,270", 0, _("Align Camera Angle")),
            ("webcam", "int", 0, _("Web Camera")),
            ("webcam_width", "int", 0, _("Web Camera Width")),
            ("webcam_height", "int", 0, _("Web Camera Height")),
            ("webcam_angle", "0,90,180,270", 0, _("Web Camera Angle")),
        ]


# =============================================================================
# CNC machine configuration
# =============================================================================
class Config(_Base):
    def __init__(self, master):
        _Base.__init__(self, master)
        self.name = "CNC"
        self.variables = [
            ("units", "bool", 0, _("Units (inches)")),
            ("lasercutter", "bool", 0, _("Laser Cutter")),
            ("laseradaptive", "bool", 0, _("Laser Adaptive Power")),
            ("doublesizeicon", "bool", 0, _("Double Size Icon")),
            ("enable6axisopt", "bool", 0, _("Enable 6 Axis Displays")),
            ("acceleration_x", "mm", 25.0, _("Acceleration x")),
            ("acceleration_y", "mm", 25.0, _("Acceleration y")),
            ("acceleration_z", "mm", 5.0, _("Acceleration z")),
            ("feedmax_x", "mm", 3000.0, _("Feed max x")),
            ("feedmax_y", "mm", 3000.0, _("Feed max y")),
            ("feedmax_z", "mm", 2000.0, _("Feed max z")),
            ("travel_x", "mm", 200, _("Travel x")),
            ("travel_y", "mm", 200, _("Travel y")),
            ("travel_z", "mm", 100, _("Travel z")),
            ("round", "int", 4, _("Decimal digits")),
            ("accuracy", "mm", 0.1, _("Plotting Arc accuracy")),
            ("startup", "str", "G90", _("Start up")),
            ("spindlemin", "int", 0, _("Spindle min (RPM)")),
            ("spindlemax", "int", 12000, _("Spindle max (RPM)")),
            ("drozeropad", "int", 0, _("DRO Zero padding")),
            ("header", "text", "", _("Header gcode")),
            ("footer", "text", "", _("Footer gcode")),
            ("init", "text", "", _("Connection init string")),
        ]

    # ----------------------------------------------------------------------
    # Update variables after edit command
    # ----------------------------------------------------------------------
    def update(self):
        self.master.inches = self["units"]
        self.master.digits = int(self["round"])
        self.master.cnc().decimal = self.master.digits
        self.master.cnc().startup = self["startup"]
        self.master.gcode.header = self["header"]
        self.master.gcode.footer = self["footer"]
        return False


# =============================================================================
# Material database
# =============================================================================
class Material(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Material")
        self.variables = [
            ("name", "db", "", _("Name")),
            ("comment", "str", "", _("Comment")),
            ("feed", "mm", 10.0, _("Feed")),
            ("feedz", "mm", 1.0, _("Plunge Feed")),
            ("stepz", "mm", 1.0, _("Depth Increment")),
        ]

    # ----------------------------------------------------------------------
    # Update variables after edit command
    # ----------------------------------------------------------------------
    def update(self):
        # update ONLY if stock material is empty:
        stockmat = self.master["stock"]["material"]
        if stockmat == "" or stockmat == self["name"]:
            self.master.cnc()["cutfeed"] = self.fromMm("feed")
            self.master.cnc()["cutfeedz"] = self.fromMm("feedz")
            self.master.cnc()["stepz"] = self.fromMm("stepz")
        return False


# =============================================================================
# EndMill Bit database
# =============================================================================
class EndMill(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "EndMill")
        self.variables = [
            ("name", "db", "", _("Name")),
            ("comment", "str", "", _("Comment")),
            ("type", "list", "", _("Type")),
            ("shape", "list", "", _("Shape")),
            ("material", "list", "", _("Material")),
            ("coating", "list", "", _("Coating")),
            ("diameter", "mm", 3.175, _("Diameter")),
            ("axis", "mm", 3.175, _("Mount Axis")),
            ("flutes", "int", 2, _("Flutes")),
            ("length", "mm", 20.0, _("Length")),
            ("angle", "float", "", _("Angle")),
            ("stepover", "float", 40.0, _("Stepover %")),
        ]

    # ----------------------------------------------------------------------
    # Update variables after edit command
    # ----------------------------------------------------------------------
    def update(self):
        self.master.cnc()["diameter"] = self.fromMm("diameter")
        self.master.cnc()["stepover"] = self["stepover"]
        return False


# =============================================================================
# Stock material on worksurface
# =============================================================================
class Stock(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Stock")
        self.variables = [
            ("name", "db", "", _("Name")),
            ("comment", "str", "", _("Comment")),
            ("material", "db", "", _("Material")),
            ("safe", "mm", 3.0, _("Safe Z")),
            ("surface", "mm", 0.0, _("Surface Z")),
            ("thickness", "mm", 5.0, _("Thickness")),
        ]

    # ----------------------------------------------------------------------
    # Update variables after edit command
    # ----------------------------------------------------------------------
    def update(self):
        self.master.cnc()["safe"] = self.fromMm("safe")
        self.master.cnc()["surface"] = self.fromMm("surface")
        self.master.cnc()["thickness"] = self.fromMm("thickness")
        if self["material"]:
            self.master["material"].makeCurrent(self["material"])
        return False


# =============================================================================
# Cut material
# =============================================================================
class Cut(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Cut")
        self.icon = "cut"
        self.variables = [
            ("name", "db", "", _("Name")),
            ("surface", "mm", "", _("Surface Z")),
            ("depth", "mm", "", _("Target Depth")),
            ("stepz", "mm", "", _("Depth Increment")),
            ("feed", "mm", "", _("Feed")),
            ("feedz", "mm", "", _("Plunge Feed")),
            (
                "strategy",
                "flat,helical+bottom,helical,ramp",
                "helical+bottom",
                _("Cutting strategy"),
            ),
            (
                "ramp",
                "int",
                10,
                _("Ramp length"),
                _(
                    "positive value = relative to tool diameter (5 to 10 "
                    + "probably makes sense), negative = absolute ramp "
                    + "distance (you probably don't need this). Also note "
                    + "that ramp can't currently be shorter than affected "
                    + "g-code segment."
                ),
            ),
            ("cutFromTop", "bool", False, _("First cut at surface height")),
            (
                "spring",
                "bool",
                False,
                _("Spring pass"),
                _(
                    "Do the last cut once more in opposite direction. "
                    + "Helix bottom is disabled in such case."
                ),
            ),
            (
                "exitpoint",
                "on path,inside,outside",
                "on path",
                _("Exit strategy (useful for threads)"),
                _(
                    "You should probably always use 'on path', unless "
                    + "you are threadmilling!"
                ),
            ),
            ("islandsLeave", "bool", True, _("Leave islands uncut")),
            (
                "islandsSelectedOnly",
                "bool",
                True,
                _("Only leave selected islands uncut"),
            ),
            (
                "islandsCompensate",
                "bool",
                False,
                _("Compensate islands for cutter radius"),
                _(
                    "Add additional margin/offset around islands to "
                    + "compensate for endmill radius. This is automatically "
                    + "done for all islands if they are marked as tabs."
                ),
            ),
            ("islandsCut", "bool", True, _("Cut contours of selected islands")),
        ]
        self.buttons.append("exe")
        self.help = "\n".join([
            "Cut selected toolpath into Z depth of stock material.",
            "",
            "For short paths, you should probably use helical cut with "
            + "bottom.",
            "For long toolpaths and pocketing you should use ramp cut "
            + "(length around 10).",
            "Also there's classic flat cuting strategy, but that will lead to "
            + "plunging straight down to material, which is not really "
            + "desirable (especially when milling harder materials).",
            "",
            "If you have generated tabs and want them to be left uncut, you "
            + "should check \"leave islands\" and uncheck "
            + "\"cut contours of islands\"",
            "If you want islands to get finishing pass, cou can use "
            + "\"cut contours of selected islands\" or cut them "
            + "individually afterwards.",
        ])

    # ----------------------------------------------------------------------
    def execute(self, app):
        # Cuting dimensions
        surface = self.fromMm("surface", None)
        depth = self.fromMm("depth", None)
        step = self.fromMm("stepz", None)

        # Cuting speed
        try:
            feed = self.fromMm("feed", None)
        except Exception:
            feed = None
        try:
            feedz = self.fromMm("feedz", None)
        except Exception:
            feedz = None

        # Cuting strategy
        strategy = self["strategy"]
        cutFromTop = self["cutFromTop"]
        springPass = self["spring"]

        # Islands
        islandsLeave = self["islandsLeave"]
        islandsCut = self["islandsCut"]
        islandsSelectedOnly = self["islandsSelectedOnly"]
        islandsCompensate = self["islandsCompensate"]

        # Decide if helix or ramp
        helix = False
        if strategy in ["helical+bottom", "helical", "ramp+bottom", "ramp"]:
            helix = True

        # Decide if ramp
        ramp = 0
        if strategy in ["ramp+bottom", "ramp"]:
            helixBottom = True
            ramp = self["ramp"]
            if ramp < 0:
                ramp = self.master.fromMm(float(ramp))

        # Decide if bottom
        helixBottom = False
        if strategy in ["helical+bottom", "ramp+bottom", "ramp"]:
            helixBottom = True

        # Decide exit point
        exitpoint = self["exitpoint"]
        if exitpoint == "inside":
            exitpoint = 1
        elif exitpoint == "outside":
            exitpoint = -1
        else:
            exitpoint = None

        # Execute cut
        app.executeOnSelection(
            "CUT",
            True,
            depth,
            step,
            surface,
            feed,
            feedz,
            cutFromTop,
            helix,
            helixBottom,
            ramp,
            islandsLeave,
            islandsCut,
            islandsSelectedOnly,
            exitpoint,
            springPass,
            islandsCompensate,
        )
        app.setStatus(_("CUT selected paths"))


# =============================================================================
# Drill material
# =============================================================================
class Drill(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Drill")
        self.icon = "drill"
        self.variables = [
            ("name", "db", "", _("Name")),
            ("center", "bool", True, _("Drill in center only")),
            ("depth", "mm", "", _("Target Depth")),
            ("peck", "mm", "", _("Peck depth")),
            ("dwell", "float", "", _("Dwell (s)")),
            ("distance", "mm", "", _("Distance (mm)")),
            ("number", "int", "", _("Number")),
        ]
        self.help = "\n".join([
            "Drill a hole in the center of the selected path or drill many "
            + "holes along the selected path.",
            "",
            "MODULE PARAMETERS:",
            "",
            "* center : if checked, there is only one drill in the center of "
            + "the selected path. (Otherwise drill along path)",
            "",
            "* depth : Depth of the drill. If not provided, stock material "
            + "thickness is used. (usually negative value)",
            "",
            "* peck: Peck step depth. If provided, drill with peck depth "
            + "step, raising the drill to z travel value. If not provided, "
            + "one pass drill is generated.",
            "",
            "* dwell: Dwell time at the bottom. If pecking is defined, dwell "
            + "also at lifted height.",
            "",
            "* distance: Distance between drills if drilling along path. "
            + "(Number of drills will superceed this parameter))",
            "",
            "* number: Number of drills if drilling along path. If nonzero, "
            + "Parameter 'distance' has no effect.",
        ])
        self.buttons.append("exe")

    # ----------------------------------------------------------------------
    def execute(self, app):
        h = self.fromMm("depth", None)
        p = self.fromMm("peck", None)
        e = self.fromMm("distance", None)
        c = self["center"]
        try:
            d = self["dwell"]
        except Exception:
            d = None
        try:
            n = int(self["number"])
        except Exception:
            n = 0
        app.executeOnSelection("DRILL", True, h, p, d, e, n, c)
        app.setStatus(_("DRILL selected points"))


# =============================================================================
# Profile
# =============================================================================
class Profile(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Profile")
        self.icon = "profile"
        self.variables = [
            ("name", "db", "", _("Name")),
            (
                "endmill",
                "db",
                "",
                _("End Mill"),
                _("Size of this endmill will be used as offset distance"),
            ),
            (
                "direction",
                "inside,outside",
                "outside",
                _("Direction"),
                _("Should we machine on inside or outside of the shape?"),
            ),
            ("offset", "float", 0.0, _("Additional offset distance")),
            (
                "overcut",
                "bool",
                1,
                _("Overcut"),
                _("Sets if we want to overcut or not."),
            ),
            (
                "pocket",
                "bool",
                0,
                _("Pocket"),
                _(
                    "Generate pocket after profiling? Useful for making "
                    + "pockets with overcuts."
                ),
            ),
        ]
        self.buttons.append("exe")
        self.help = "\n".join([
            "This plugin offsets shapes to create toolpaths for profiling "
            + "operation.",
            "Shape needs to be offset by the radius of endmill to get cut "
            + "correctly.",
            "",
            "Currently we have two modes.",
            "",
            "Without overcut:",
            "#overcut-without",
            "",
            "And with overcut:",
            "#overcut-with",
            "",
            "Blue is the original shape from CAD",
            "Turquoise is the generated toolpath",
            "Grey is simulation of how part will look after machining",
        ])

    # ----------------------------------------------------------------------
    def execute(self, app):
        if self["endmill"]:
            self.master["endmill"].makeCurrent(self["endmill"])
        direction = self["direction"]
        name = self["name"]
        pocket = self["pocket"]
        if name == "default" or name == "":
            name = None
        app.profile(direction, self["offset"], self["overcut"], name, pocket)
        app.setStatus(_("Generate profile path"))


# =============================================================================
# Pocket
# =============================================================================
class Pocket(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Pocket")
        self.icon = "pocket"
        self.variables = [
            ("name", "db", "", _("Name")),
            ("endmill", "db", "", _("End Mill")),
        ]
        self.buttons.append("exe")
        self.help = """Remove all material inside selected shape
"""

    # ----------------------------------------------------------------------
    def execute(self, app):
        if self["endmill"]:
            self.master["endmill"].makeCurrent(self["endmill"])
        name = self["name"]
        if name == "default" or name == "":
            name = None
        app.pocket(name)
        app.setStatus(_("Generate pocket path"))


# =============================================================================
# Tabs
# =============================================================================
class Tabs(DataBase):
    def __init__(self, master):
        DataBase.__init__(self, master, "Tabs")
        self.icon = "tab"
        self.variables = [
            ("name", "db", "", _("Name")),
            ("ntabs", "int", 5, _("Number of tabs")),
            ("dtabs", "mm", 0.0, _("Min. Distance of tabs")),
            ("dx", "mm", 5.0, "Width"),
            ("z", "mm", -3.0, _("Height")),
        ]
        self.buttons.append("exe")
        self.help = "\n".join([
            "Create tabs, which will be left uncut to hold the part in place "
            + "after cutting.",
            "",
            "Tabs after creation:",
            "#tabs-created",
            "",
            "Tabs after cutting the path they're attached to:",
            "#tabs-cut",
            "",
            "Tab shows the size of material, which will be left in place "
            + "after cutting. It's compensated for endmill diameter during "
            + "cut operation.",
            "",
            "Note that tabs used to be square, but if there was a diagonal "
            + "segment crossing such tab, it resulted in larger tab without "
            + "any reason. If we use circular tabs, the tab size is always "
            + "the same, no matter the angle of segment.",
            "",
            "You can move selected tabs using \"Move\" feature in \"Editor\". "
            + "If you want to modify individual tabs, you have to first use "
            + "\"Split\" feature to break the block into individual tabs. "
            + "After moving them, you can \"Join\" them back together.",
        ])

    # ----------------------------------------------------------------------
    def execute(self, app):
        try:
            ntabs = int(self["ntabs"])
        except Exception:
            ntabs = 0

        dtabs = self.fromMm("dtabs", 0.0)
        dx = self.fromMm("dx", self.master.fromMm(5.0))
        dy = dx
        z = self.fromMm("z", -self.master.fromMm(3.0))

        if ntabs < 0:
            ntabs = 0
        if dtabs < 0.0:
            dtabs = 0

        if ntabs == 0 and dtabs == 0:
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    _("Tabs error"),
                    _("You cannot have both the number of tabs or distance "
                      "equal to zero"),
                )
            except ImportError:
                pass

        circ = True

        app.executeOnSelection("TABS", True, ntabs, dtabs, dx, dy, z, circ)
        app.setStatus(_("Create tabs on blocks"))


# =============================================================================
# Controller setup
# =============================================================================
class Controller(_Base):
    def __init__(self, master):
        _Base.__init__(self, master)
        self.name = "Controller"
        self.variables = [
            ("grbl_0", "float", 10, _("$0 Step pulse time [us]")),
            ("grbl_1", "int", 25, _("$1 Step idle delay [ms]")),
            ("grbl_2", "int", 0, _("$2 Step port invert [mask]")),
            ("grbl_3", "int", 0, _("$3 Direction port invert [mask]")),
            ("grbl_4", "bool", 0, _("$4 Step enable invert")),
            ("grbl_5", "bool", 0, _("$5 Limit pins invert")),
            ("grbl_6", "bool", 0, _("$6 Probe pin invert")),
            ("grbl_10", "int", 1, _("$10 Status report [mask]")),
            ("grbl_11", "float", 0.010, _("$11 Junction deviation [mm]")),
            ("grbl_12", "float", 0.002, _("$12 Arc tolerance [mm]")),
            ("grbl_13", "bool", 0, _("$13 Report inches")),
            ("grbl_20", "bool", 0, _("$20 Soft limits")),
            ("grbl_21", "bool", 0, _("$21 Hard limits")),
            ("grbl_22", "bool", 0, _("$22 Homing cycle")),
            ("grbl_23", "int", 0, _("$23 Homing direction invert [mask]")),
            ("grbl_24", "float", 25.0, _("$24 Homing feed [mm/min]")),
            ("grbl_25", "float", 500.0, _("$25 Homing seek [mm/min]")),
            ("grbl_26", "int", 250, _("$26 Homing debounce [ms]")),
            ("grbl_27", "float", 1.0, _("$27 Homing pull-off [mm]")),
            ("grbl_30", "float", 1000.0, _("$30 Max spindle speed [RPM]")),
            ("grbl_31", "float", 0.0, _("$31 Min spindle speed [RPM]")),
            ("grbl_32", "bool", 0, _("$32 Laser mode enable")),
            ("grbl_100", "float", 250.0, _("$100 X steps/mm")),
            ("grbl_101", "float", 250.0, _("$101 Y steps/mm")),
            ("grbl_102", "float", 250.0, _("$102 Z steps/mm")),
            ("grbl_110", "float", 500.0, _("$110 X max rate [mm/min]")),
            ("grbl_111", "float", 500.0, _("$111 Y max rate [mm/min]")),
            ("grbl_112", "float", 500.0, _("$112 Z max rate [mm/min]")),
            ("grbl_120", "float", 10.0, _("$120 X acceleration [mm/sec^2]")),
            ("grbl_121", "float", 10.0, _("$121 Y acceleration [mm/sec^2]")),
            ("grbl_122", "float", 10.0, _("$122 Z acceleration [mm/sec^2]")),
            ("grbl_130", "float", 200.0, _("$130 X max travel [mm]")),
            ("grbl_131", "float", 200.0, _("$131 Y max travel [mm]")),
            ("grbl_132", "float", 200.0, _("$132 Z max travel [mm]")),
            ("grbl_140", "float", 200.0, _("$140 X homing pull-off [mm]")),
            ("grbl_141", "float", 200.0, _("$141 Y homing pull-off [mm]")),
            ("grbl_142", "float", 200.0, _("$142 Z homing pull-off [mm]")),
        ]
        self.buttons.append("exe")

    # ----------------------------------------------------------------------
    def execute(self, app):
        lines = []
        for n, t, d, _c in self.variables:
            v = self[n]
            try:
                if t == "float":
                    if v == float(CNC.vars[n]):
                        continue
                else:
                    if v == int(CNC.vars[n]):
                        continue
            except Exception:
                continue
            lines.append(f"${n[5:]}={str(v)}")
            lines.append("%wait")
        lines.append("$$")
        app.run(lines=lines)

    # ----------------------------------------------------------------------
    def beforeChange(self, app):
        app.sendGCode("$$")
        time.sleep(1)

    # ----------------------------------------------------------------------
    def populate(self):
        for var in self.variables:
            n, t, d, lp = var[:4]
            try:
                if t == "float":
                    self.values[n] = float(CNC.vars[n])
                else:
                    self.values[n] = int(CNC.vars[n])
            except KeyError:
                pass
        _Base.populate(self)
