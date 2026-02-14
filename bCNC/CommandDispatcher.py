# CommandDispatcher - Toolkit-independent command routing
#
# Extracts GCode operation dispatch and CAM operations from
# Application.execute(), separating model operations from UI.
# The UI layer (Application) handles selection, dialogs, and
# editor updates; this class handles the GCode transformations.


class GCodeOperations:
    """Routes GCode manipulation commands to the GCode model.

    This class is toolkit-independent. It takes a GCode object
    and returns results (selections, error messages) that the
    UI layer can act on.
    """

    def __init__(self, gcode, tools=None):
        """
        Args:
            gcode: The GCode model object.
            tools: The Tools database (for CAM operations).
        """
        self.gcode = gcode
        self.tools = tools

    def execute_on_items(self, cmd, items, *args):
        """Execute a GCode operation on the given items.

        Args:
            cmd: Operation name (e.g. "CUT", "DRILL", "MOVE").
            items: Selected blocks or lines from the editor.
            *args: Additional arguments for the operation.

        Returns:
            tuple: (selection_result, status_message)
                - selection_result: New selection list, error string,
                  or None if no selection change needed.
                - status_message: Status text to display.
        """
        sel = None

        if cmd == "AUTOLEVEL":
            sel = self.gcode.autolevel(items)
        elif cmd == "CUT":
            sel = self.gcode.cut(items, *args)
        elif cmd == "CLOSE":
            sel = self.gcode.close(items)
        elif cmd == "DIRECTION":
            sel = self.gcode.cutDirection(items, *args)
        elif cmd == "DRILL":
            sel = self.gcode.drill(items, *args)
        elif cmd == "ORDER":
            self.gcode.orderLines(items, *args)
        elif cmd == "INKSCAPE":
            self.gcode.inkscapeLines()
        elif cmd == "ISLAND":
            self.gcode.island(items, *args)
        elif cmd == "MIRRORH":
            self.gcode.mirrorHLines(items)
        elif cmd == "MIRRORV":
            self.gcode.mirrorVLines(items)
        elif cmd == "MOVE":
            self.gcode.moveLines(items, *args)
        elif cmd == "OPTIMIZE":
            self.gcode.optimize(items)
        elif cmd == "ORIENT":
            self.gcode.orientLines(items)
        elif cmd == "REVERSE":
            self.gcode.reverse(items, *args)
        elif cmd == "ROUND":
            self.gcode.roundLines(items, *args)
        elif cmd == "ROTATE":
            self.gcode.rotateLines(items, *args)
        elif cmd == "TABS":
            sel = self.gcode.createTabs(items, *args)

        args_str = " ".join(str(a) for a in args if a is not None)
        status = f"{cmd} {args_str}".strip()

        return sel, status

    def profile(self, blocks, direction=None, offset=0.0,
                overcut=False, name=None, pocket=False):
        """Execute profile operation.

        Args:
            blocks: Selected GCode blocks.
            direction: "INSIDE", "OUTSIDE", or offset value.
            offset: Additional offset.
            overcut: Whether to overcut corners.
            name: Optional name for the new block.
            pocket: Whether this is a pocket profile.

        Returns:
            tuple: (warning_message, computed_offset)
                - warning_message: Warning string or None.
                - computed_offset: The actual offset used.
        """
        import rexx

        tool = self.tools["EndMill"]
        ofs = self.tools.fromMm(tool["diameter"]) / 2.0
        sign = 1.0

        if direction is None:
            pass
        elif rexx.abbrev("INSIDE", direction.upper()):
            sign = -1.0
        elif rexx.abbrev("OUTSIDE", direction.upper()):
            sign = 1.0
        else:
            try:
                ofs = float(direction) / 2.0
            except Exception:
                pass

        try:
            ofs += float(offset)
        except Exception:
            pass

        msg = self.gcode.profile(blocks, ofs * sign, overcut, name, pocket)
        return msg, ofs * sign

    def pocket(self, blocks, name=None):
        """Execute pocket operation.

        Args:
            blocks: Selected GCode blocks.
            name: Optional name for the new block.

        Returns:
            warning_message: Warning string or None.
        """
        tool = self.tools["EndMill"]
        diameter = self.tools.fromMm(tool["diameter"])
        try:
            stepover = tool["stepover"] / 100.0
        except TypeError:
            stepover = 0.0

        msg = self.gcode.pocket(blocks, diameter, stepover, name)
        return msg

    def trochprofile(self, blocks, cutDiam=0.0, direction=None,
                     offset=0.0, overcut=False, adaptative=False,
                     adaptedRadius=0.0, tooldiameter=0.0,
                     targetDepth=0.0, depthIncrement=0.0,
                     tabsnumber=0.0, tabsWidth=0.0, tabsHeight=0.0):
        """Execute trochoidal profile operation.

        Returns:
            tuple: (warning_message, adaptative_flag, computed_offset)
        """
        import rexx

        adaptedRadius = float(adaptedRadius)
        ofs = float(cutDiam) / 2.0
        sign = 1.0

        if direction is None:
            pass
        elif rexx.abbrev("INSIDE", direction.upper()):
            sign = -1.0
        elif rexx.abbrev("OUTSIDE", direction.upper()):
            sign = 1.0
        elif rexx.abbrev("ON", direction.upper()):
            ofs = 0
        else:
            try:
                ofs = float(direction) / 2.0
            except Exception:
                pass

        try:
            ofs += float(offset)
        except Exception:
            pass

        msg = self.gcode.trochprofile_cnc(
            blocks, ofs * sign, overcut, adaptative,
            adaptedRadius, cutDiam, tooldiameter,
            targetDepth, depthIncrement,
            tabsnumber, tabsWidth, tabsHeight,
        )
        return msg, adaptative, ofs * sign
