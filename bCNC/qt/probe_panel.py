# Qt Probe Panel — tabbed container for Probe, Autolevel, Camera, Tool
#
# Ports ProbePage.py ProbeCommonFrame, ProbeFrame, and ToolFrame to Qt,
# wrapping them with AutolevelTab in a QTabWidget.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QComboBox, QCheckBox, QLineEdit, QTabWidget,
    QMessageBox,
)

import utils_core as Utils
from CNC import CNC

from .autolevel_panel import AutolevelTab


PROBE_CMD = [
    "G38.2 stop on contact else error",
    "G38.3 stop on contact",
    "G38.4 stop on loss contact else error",
    "G38.5 stop on loss contact",
]

TOOL_POLICY = [
    "Send M6 commands",
    "Ignore M6 commands",
    "Manual Tool Change (WCS)",
    "Manual Tool Change (TLO)",
    "Manual Tool Change (NoProbe)",
]

TOOL_WAIT = [
    "ONLY before probing",
    "BEFORE & AFTER probing",
]


# ======================================================================
# ProbeCommonWidget — shared probe settings (feed, TLO, command)
# ======================================================================
class ProbeCommonWidget(QWidget):
    """Probe settings shared across Probe, Autolevel, and Tool tabs."""

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender

        group = QGroupBox("Probe Settings")
        gl = QGridLayout(group)

        gl.addWidget(QLabel("Fast Probe Feed:"), 0, 0)
        self.fast_probe_feed = QDoubleSpinBox()
        self.fast_probe_feed.setRange(0.1, 10000)
        self.fast_probe_feed.setDecimals(1)
        gl.addWidget(self.fast_probe_feed, 0, 1)

        gl.addWidget(QLabel("Probe Feed:"), 1, 0)
        self.probe_feed = QDoubleSpinBox()
        self.probe_feed.setRange(0.1, 10000)
        self.probe_feed.setDecimals(1)
        gl.addWidget(self.probe_feed, 1, 1)

        gl.addWidget(QLabel("TLO:"), 2, 0)
        tlo_row = QHBoxLayout()
        self.tlo = QDoubleSpinBox()
        self.tlo.setRange(-1000, 1000)
        self.tlo.setDecimals(3)
        tlo_row.addWidget(self.tlo)
        self.tlo_set_btn = QPushButton("Set")
        self.tlo_set_btn.clicked.connect(self._on_tlo_set)
        tlo_row.addWidget(self.tlo_set_btn)
        gl.addLayout(tlo_row, 2, 1)

        gl.addWidget(QLabel("Probe Command:"), 3, 0)
        self.probe_cmd = QComboBox()
        self.probe_cmd.addItems(PROBE_CMD)
        gl.addWidget(self.probe_cmd, 3, 1)

        gl.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

    def apply_to_cnc(self):
        """Push feed/cmd values into CNC.vars. Returns True on error."""
        try:
            CNC.vars["fastprbfeed"] = self.fast_probe_feed.value()
            CNC.vars["prbfeed"] = self.probe_feed.value()
            CNC.vars["prbcmd"] = self.probe_cmd.currentText().split()[0]
            return False
        except Exception:
            return True

    def update_tlo_display(self):
        """Refresh TLO spinbox from CNC.vars (called on %update TLO)."""
        self.tlo.setValue(CNC.vars.get("TLO", 0.0))

    def _on_tlo_set(self):
        try:
            CNC.vars["TLO"] = self.tlo.value()
            cmd = f"G43.1Z{self.tlo.value()}"
            self.sender.sendGCode(cmd)
        except Exception:
            pass

    def loadConfig(self):
        self.fast_probe_feed.setValue(
            Utils.getFloat("Probe", "fastfeed", 100.0))
        self.probe_feed.setValue(
            Utils.getFloat("Probe", "feed", 10.0))
        self.tlo.setValue(
            Utils.getFloat("Probe", "tlo", 0.0))
        cmd = Utils.getStr("Probe", "cmd")
        for i, p in enumerate(PROBE_CMD):
            if p.split()[0] == cmd:
                self.probe_cmd.setCurrentIndex(i)
                break

    def saveConfig(self):
        Utils.setFloat("Probe", "fastfeed", self.fast_probe_feed.value())
        Utils.setFloat("Probe", "feed", self.probe_feed.value())
        Utils.setFloat("Probe", "tlo", self.tlo.value())
        Utils.setFloat("Probe", "cmd",
                        self.probe_cmd.currentText().split()[0])


# ======================================================================
# ProbeTab — single-direction probing, center probing, recording
# ======================================================================
class ProbeTab(QWidget):
    """Single-direction probing, center-find, and coordinate recording."""

    def __init__(self, sender, signals, probe_common, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals
        self._probe_common = probe_common
        self._autogoto_next = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Probe group ---
        probe_group = QGroupBox("Probe")
        pg = QGridLayout(probe_group)

        pg.addWidget(QLabel("Probe:"), 0, 0)
        self._probe_x = QLabel("")
        self._probe_x.setStyleSheet(
            "color: darkblue; background: #e8e8e8; padding: 2px;")
        pg.addWidget(self._probe_x, 0, 1)
        self._probe_y = QLabel("")
        self._probe_y.setStyleSheet(
            "color: darkblue; background: #e8e8e8; padding: 2px;")
        pg.addWidget(self._probe_y, 0, 2)
        self._probe_z = QLabel("")
        self._probe_z.setStyleSheet(
            "color: darkblue; background: #e8e8e8; padding: 2px;")
        pg.addWidget(self._probe_z, 0, 3)

        self.autogoto = QCheckBox("Auto goto")
        pg.addWidget(self.autogoto, 0, 4)
        self.goto_btn = QPushButton("Goto")
        self.goto_btn.clicked.connect(self._on_goto_probe)
        pg.addWidget(self.goto_btn, 0, 5)

        pg.addWidget(QLabel("Pos:"), 1, 0)
        self.probe_x_dir = QLineEdit()
        self.probe_x_dir.setPlaceholderText("X")
        self.probe_x_dir.setToolTip("X probe distance (empty=skip)")
        pg.addWidget(self.probe_x_dir, 1, 1)
        self.probe_y_dir = QLineEdit()
        self.probe_y_dir.setPlaceholderText("Y")
        self.probe_y_dir.setToolTip("Y probe distance (empty=skip)")
        pg.addWidget(self.probe_y_dir, 1, 2)
        self.probe_z_dir = QLineEdit()
        self.probe_z_dir.setPlaceholderText("Z")
        self.probe_z_dir.setToolTip("Z probe distance (empty=skip)")
        pg.addWidget(self.probe_z_dir, 1, 3)

        self.probe_btn = QPushButton("Probe")
        self.probe_btn.clicked.connect(self._on_probe)
        pg.addWidget(self.probe_btn, 1, 5)

        pg.setColumnStretch(1, 1)
        pg.setColumnStretch(2, 1)
        pg.setColumnStretch(3, 1)
        layout.addWidget(probe_group)

        # --- Center group ---
        center_group = QGroupBox("Center")
        cg = QHBoxLayout(center_group)
        cg.addWidget(QLabel("Diameter:"))
        self.diameter = QDoubleSpinBox()
        self.diameter.setRange(0.001, 10000)
        self.diameter.setDecimals(3)
        self.diameter.setValue(10.0)
        cg.addWidget(self.diameter, 1)
        self.center_btn = QPushButton("Center")
        self.center_btn.clicked.connect(self._on_probe_center)
        cg.addWidget(self.center_btn)
        layout.addWidget(center_group)

        # --- Record group ---
        record_group = QGroupBox("Record")
        rl = QVBoxLayout(record_group)

        rg = QHBoxLayout()
        self.rec_z = QCheckBox("Z")
        self.rec_z.setToolTip("Include Z coordinate in recorded moves")
        rg.addWidget(self.rec_z)

        for label, slot in [
            ("RAPID", self._on_record_rapid),
            ("FEED", self._on_record_feed),
            ("POINT", self._on_record_point),
            ("CIRCLE", self._on_record_circle),
            ("FINISH", self._on_record_finish),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            rg.addWidget(btn)
        rl.addLayout(rg)

        rg2 = QHBoxLayout()
        rg2.addWidget(QLabel("Radius:"))
        self.rec_radius = QDoubleSpinBox()
        self.rec_radius.setRange(0.001, 10000)
        self.rec_radius.setDecimals(3)
        self.rec_radius.setValue(10.0)
        rg2.addWidget(self.rec_radius, 1)
        rl.addLayout(rg2)

        layout.addWidget(record_group)

        layout.addStretch()

        # Wire probe update signal
        self.signals.probe_updated.connect(self._on_probe_updated)

        self.loadConfig()

    # ------------------------------------------------------------------
    # Probe
    # ------------------------------------------------------------------
    def _on_probe(self):
        if self.autogoto.isChecked():
            self._autogoto_next = True

        if self._probe_common.apply_to_cnc():
            QMessageBox.critical(self, "Probe Error",
                                 "Invalid probe feed rate")
            return

        cmd = str(CNC.vars["prbcmd"])
        ok = False

        v = self.probe_x_dir.text().strip()
        if v:
            cmd += f"X{v}"
            ok = True

        v = self.probe_y_dir.text().strip()
        if v:
            cmd += f"Y{v}"
            ok = True

        v = self.probe_z_dir.text().strip()
        if v:
            cmd += f"Z{v}"
            ok = True

        feed = self._probe_common.probe_feed.value()
        if feed:
            cmd += f"F{feed}"

        if ok:
            self.sender.sendGCode(cmd)
        else:
            QMessageBox.critical(self, "Probe Error",
                                 "At least one probe direction must be specified")

    def _on_goto_probe(self):
        try:
            cmd = "G53 G0 X{:g} Y{:g} Z{:g}\n".format(
                CNC.vars["prbx"],
                CNC.vars["prby"],
                CNC.vars["prbz"],
            )
        except Exception:
            return
        self.sender.sendGCode(cmd)

    def _on_probe_center(self):
        if self._probe_common.apply_to_cnc():
            QMessageBox.critical(self, "Probe Error",
                                 "Invalid probe feed rate")
            return

        diameter = self.diameter.value()
        if diameter < 0.001:
            QMessageBox.critical(self, "Probe Center Error",
                                 "Invalid diameter entered")
            return

        cmd = f"G91 {CNC.vars['prbcmd']} F{CNC.vars['prbfeed']}"
        lines = []
        lines.append(f"{cmd} x-{diameter}")
        lines.append("%wait")
        lines.append("tmp=prbx")
        lines.append(f"g53 g0 x[prbx+{diameter / 10.0:g}]")
        lines.append("%wait")
        lines.append(f"{cmd} x{diameter}")
        lines.append("%wait")
        lines.append("g53 g0 x[0.5*(tmp+prbx)]")
        lines.append("%wait")
        lines.append(f"{cmd} y-{diameter}")
        lines.append("%wait")
        lines.append("tmp=prby")
        lines.append(f"g53 g0 y[prby+{diameter / 10.0:g}]")
        lines.append("%wait")
        lines.append(f"{cmd} y{diameter}")
        lines.append("%wait")
        lines.append("g53 g0 y[0.5*(tmp+prby)]")
        lines.append("%wait")
        lines.append("g90")
        if not self.sender.runLines(lines):
            QMessageBox.warning(self, "Cannot Run",
                                "Not connected or already running.")

    def _on_probe_updated(self):
        """Refresh probe coordinate labels when probe data arrives."""
        self._probe_x.setText(f"{CNC.vars.get('prbx', 0.0):.4f}")
        self._probe_y.setText(f"{CNC.vars.get('prby', 0.0):.4f}")
        self._probe_z.setText(f"{CNC.vars.get('prbz', 0.0):.4f}")

        if self._autogoto_next:
            self._autogoto_next = False
            self._on_goto_probe()

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------
    def _record_coords(self, gcode="G0", point=False):
        x = CNC.vars["wx"]
        y = CNC.vars["wy"]
        z = CNC.vars["wz"]
        coords = f"X{x} Y{y}"
        if self.rec_z.isChecked():
            coords += f" Z{z}"

        lines = []
        if point:
            lines.append(f"G0 Z{CNC.vars.get('safe', 3.0)}")
        lines.append(f"{gcode} {coords}")
        if point:
            lines.append("G1 Z0")
        return lines

    def _on_record_rapid(self):
        lines = self._record_coords("G0")
        self.sender.runLines(lines)

    def _on_record_feed(self):
        lines = self._record_coords("G1")
        self.sender.runLines(lines)

    def _on_record_point(self):
        lines = self._record_coords("G0", point=True)
        self.sender.runLines(lines)

    def _on_record_circle(self):
        r = self.rec_radius.value()
        x = CNC.vars["wx"] - r
        y = CNC.vars["wy"]
        coords = f"X{x} Y{y}"
        if self.rec_z.isChecked():
            coords += f" Z{CNC.vars['wz']}"
        lines = [
            f"G0 {coords}",
            f"G02 {coords} I{r}",
        ]
        self.sender.runLines(lines)

    def _on_record_finish(self):
        self.sender.runLines(["M5", "G0 Z[safe]", "M2"])

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def loadConfig(self):
        self.probe_x_dir.setText(Utils.getStr("Probe", "x", ""))
        self.probe_y_dir.setText(Utils.getStr("Probe", "y", ""))
        self.probe_z_dir.setText(Utils.getStr("Probe", "z", ""))
        self.diameter.setValue(
            Utils.getFloat("Probe", "center", 10.0))
        self.autogoto.setChecked(
            Utils.getBool("Probe", "autogoto", False))

    def saveConfig(self):
        Utils.setStr("Probe", "x", self.probe_x_dir.text())
        Utils.setStr("Probe", "y", self.probe_y_dir.text())
        Utils.setStr("Probe", "z", self.probe_z_dir.text())
        Utils.setFloat("Probe", "center", self.diameter.value())
        Utils.setBool("Probe", "autogoto", self.autogoto.isChecked())


# ======================================================================
# ToolTab — manual tool change management
# ======================================================================
class ToolTab(QWidget):
    """Manual tool change policy, positions, and calibration."""

    def __init__(self, sender, signals, probe_common, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals
        self._probe_common = probe_common

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        group = QGroupBox("Manual Tool Change")
        gl = QGridLayout(group)
        row = 0

        # Policy
        gl.addWidget(QLabel("Policy:"), row, 0)
        self.tool_policy = QComboBox()
        self.tool_policy.addItems(TOOL_POLICY)
        self.tool_policy.currentIndexChanged.connect(self._on_policy_changed)
        gl.addWidget(self.tool_policy, row, 1, 1, 3)
        row += 1

        # Wait / Pause
        gl.addWidget(QLabel("Pause:"), row, 0)
        self.tool_wait = QComboBox()
        self.tool_wait.addItems(TOOL_WAIT)
        self.tool_wait.currentIndexChanged.connect(self._on_wait_changed)
        gl.addWidget(self.tool_wait, row, 1, 1, 3)
        row += 1

        # Headers
        for col, label in enumerate(["MX", "MY", "MZ"], 1):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gl.addWidget(lbl, row, col)
        row += 1

        # Change position
        gl.addWidget(QLabel("Change:"), row, 0)
        self.change_x = QDoubleSpinBox()
        self.change_x.setRange(-10000, 10000)
        self.change_x.setDecimals(3)
        gl.addWidget(self.change_x, row, 1)
        self.change_y = QDoubleSpinBox()
        self.change_y.setRange(-10000, 10000)
        self.change_y.setDecimals(3)
        gl.addWidget(self.change_y, row, 2)
        self.change_z = QDoubleSpinBox()
        self.change_z.setRange(-10000, 10000)
        self.change_z.setDecimals(3)
        gl.addWidget(self.change_z, row, 3)
        get_change_btn = QPushButton("Get")
        get_change_btn.setToolTip("Get current machine position")
        get_change_btn.clicked.connect(self._on_get_change)
        gl.addWidget(get_change_btn, row, 4)
        row += 1

        # Probe position
        gl.addWidget(QLabel("Probe:"), row, 0)
        self.probe_x = QDoubleSpinBox()
        self.probe_x.setRange(-10000, 10000)
        self.probe_x.setDecimals(3)
        gl.addWidget(self.probe_x, row, 1)
        self.probe_y = QDoubleSpinBox()
        self.probe_y.setRange(-10000, 10000)
        self.probe_y.setDecimals(3)
        gl.addWidget(self.probe_y, row, 2)
        self.probe_z = QDoubleSpinBox()
        self.probe_z.setRange(-10000, 10000)
        self.probe_z.setDecimals(3)
        gl.addWidget(self.probe_z, row, 3)
        get_probe_btn = QPushButton("Get")
        get_probe_btn.setToolTip("Get current machine position")
        get_probe_btn.clicked.connect(self._on_get_probe)
        gl.addWidget(get_probe_btn, row, 4)
        row += 1

        # Probe distance
        gl.addWidget(QLabel("Distance:"), row, 0)
        self.probe_distance = QDoubleSpinBox()
        self.probe_distance.setRange(0.001, 10000)
        self.probe_distance.setDecimals(3)
        self.probe_distance.setValue(10.0)
        gl.addWidget(self.probe_distance, row, 1)
        row += 1

        # Tool height + calibrate
        gl.addWidget(QLabel("Height:"), row, 0)
        self.tool_height = QDoubleSpinBox()
        self.tool_height.setRange(-10000, 10000)
        self.tool_height.setDecimals(3)
        self.tool_height.setReadOnly(True)
        self.tool_height.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        gl.addWidget(self.tool_height, row, 1)
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setToolTip("Run tool calibration probe sequence")
        self.calibrate_btn.clicked.connect(self._on_calibrate)
        gl.addWidget(self.calibrate_btn, row, 2)
        self.change_btn = QPushButton("Change")
        self.change_btn.setToolTip("Run tool change sequence")
        self.change_btn.clicked.connect(self._on_change)
        gl.addWidget(self.change_btn, row, 3)
        row += 1

        gl.setColumnStretch(1, 1)
        gl.setColumnStretch(2, 1)
        gl.setColumnStretch(3, 1)
        layout.addWidget(group)
        layout.addStretch()

        self.loadConfig()

    # ------------------------------------------------------------------
    # Push UI values into CNC.vars
    # ------------------------------------------------------------------
    def _push_to_cnc(self):
        CNC.toolPolicy = self.tool_policy.currentIndex()
        CNC.toolWaitAfterProbe = self.tool_wait.currentIndex()
        CNC.vars["toolchangex"] = self.change_x.value()
        CNC.vars["toolchangey"] = self.change_y.value()
        CNC.vars["toolchangez"] = self.change_z.value()
        CNC.vars["toolprobex"] = self.probe_x.value()
        CNC.vars["toolprobey"] = self.probe_y.value()
        CNC.vars["toolprobez"] = self.probe_z.value()
        CNC.vars["tooldistance"] = abs(self.probe_distance.value())
        CNC.vars["toolheight"] = self.tool_height.value()

    def _check_errors(self):
        if CNC.vars.get("tooldistance", 0.0) <= 0.0:
            QMessageBox.critical(
                self, "Probe Tool Change Error",
                "Invalid tool scanning distance entered")
            return True
        return False

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_policy_changed(self):
        CNC.toolPolicy = self.tool_policy.currentIndex()

    def _on_wait_changed(self):
        CNC.toolWaitAfterProbe = self.tool_wait.currentIndex()

    def _on_get_change(self):
        self.change_x.setValue(CNC.vars.get("mx", 0.0))
        self.change_y.setValue(CNC.vars.get("my", 0.0))
        self.change_z.setValue(CNC.vars.get("mz", 0.0))

    def _on_get_probe(self):
        self.probe_x.setValue(CNC.vars.get("mx", 0.0))
        self.probe_y.setValue(CNC.vars.get("my", 0.0))
        self.probe_z.setValue(CNC.vars.get("mz", 0.0))

    def _on_calibrate(self):
        self._push_to_cnc()
        if self._probe_common.apply_to_cnc():
            QMessageBox.critical(self, "Probe Error",
                                 "Invalid probe feed rate")
            return
        if self._check_errors():
            return

        lines = []
        lines.append("g53 g0 z[toolchangez]")
        lines.append("g53 g0 x[toolchangex] y[toolchangey]")
        lines.append("g53 g0 x[toolprobex] y[toolprobey]")
        lines.append("g53 g0 z[toolprobez]")

        if CNC.vars["fastprbfeed"]:
            prb_reverse = {"2": "4", "3": "5", "4": "2", "5": "3"}
            CNC.vars["prbcmdreverse"] = (
                CNC.vars["prbcmd"][:-1]
                + prb_reverse[CNC.vars["prbcmd"][-1]]
            )
            current_feed = CNC.vars["fastprbfeed"]
            while current_feed > CNC.vars["prbfeed"]:
                lines.append("%wait")
                lines.append(
                    f"g91 [prbcmd] {CNC.fmt('f', current_feed)}"
                    " z[toolprobez-mz-tooldistance]"
                )
                lines.append("%wait")
                lines.append(
                    f"[prbcmdreverse] {CNC.fmt('f', current_feed)}"
                    " z[toolprobez-mz]"
                )
                current_feed /= 10

        lines.append("%wait")
        lines.append(
            "g91 [prbcmd] f[prbfeed] z[toolprobez-mz-tooldistance]")
        lines.append("g4 p1")
        lines.append("%wait")
        lines.append("%global toolheight; toolheight=wz")
        lines.append("%global toolmz; toolmz=prbz")
        lines.append("%update toolheight")
        lines.append("g53 g0 z[toolchangez]")
        lines.append("g53 g0 x[toolchangex] y[toolchangey]")
        lines.append("g90")

        if not self.sender.runLines(lines):
            QMessageBox.warning(self, "Cannot Run",
                                "Not connected or already running.")

    def _on_change(self):
        self._push_to_cnc()
        if self._probe_common.apply_to_cnc():
            QMessageBox.critical(self, "Probe Error",
                                 "Invalid probe feed rate")
            return
        if self._check_errors():
            return
        lines = self.sender.cnc.toolChange(0)
        if not self.sender.runLines(lines):
            QMessageBox.warning(self, "Cannot Run",
                                "Not connected or already running.")

    def update_tool_height(self):
        """Refresh tool height display from CNC.vars (on %update toolheight)."""
        self.tool_height.setValue(CNC.vars.get("toolheight", 0.0))

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def loadConfig(self):
        self.tool_policy.setCurrentIndex(
            Utils.getInt("Probe", "toolpolicy", 0))
        self.tool_wait.setCurrentIndex(
            Utils.getInt("Probe", "toolwait", 1))
        self.change_x.setValue(
            Utils.getFloat("Probe", "toolchangex", 0.0))
        self.change_y.setValue(
            Utils.getFloat("Probe", "toolchangey", 0.0))
        self.change_z.setValue(
            Utils.getFloat("Probe", "toolchangez", 0.0))
        self.probe_x.setValue(
            Utils.getFloat("Probe", "toolprobex", 0.0))
        self.probe_y.setValue(
            Utils.getFloat("Probe", "toolprobey", 0.0))
        self.probe_z.setValue(
            Utils.getFloat("Probe", "toolprobez", 0.0))
        self.probe_distance.setValue(
            Utils.getFloat("Probe", "tooldistance", 10.0))
        self.tool_height.setValue(
            Utils.getFloat("Probe", "toolheight", 0.0))

        # Push loaded values into CNC module
        self._push_to_cnc()
        CNC.vars["toolmz"] = Utils.getFloat("Probe", "toolmz", 0.0)

    def saveConfig(self):
        Utils.setInt("Probe", "toolpolicy",
                     self.tool_policy.currentIndex())
        Utils.setInt("Probe", "toolwait",
                     self.tool_wait.currentIndex())
        Utils.setFloat("Probe", "toolchangex", self.change_x.value())
        Utils.setFloat("Probe", "toolchangey", self.change_y.value())
        Utils.setFloat("Probe", "toolchangez", self.change_z.value())
        Utils.setFloat("Probe", "toolprobex", self.probe_x.value())
        Utils.setFloat("Probe", "toolprobey", self.probe_y.value())
        Utils.setFloat("Probe", "toolprobez", self.probe_z.value())
        Utils.setFloat("Probe", "tooldistance",
                       self.probe_distance.value())
        Utils.setFloat("Probe", "toolheight", self.tool_height.value())
        Utils.setFloat("Probe", "toolmz",
                       CNC.vars.get("toolmz", 0.0))


# ======================================================================
# ProbePanel — top-level tabbed container
# ======================================================================
class ProbePanel(QWidget):
    """Top-level probe panel with shared settings and tabbed sub-panels."""

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Shared probe settings (always visible above tabs)
        self.probe_common = ProbeCommonWidget(sender)
        layout.addWidget(self.probe_common)

        # Tabbed sub-panels
        self.tabs = QTabWidget()

        self.probe_tab = ProbeTab(sender, signals, self.probe_common)
        self.tabs.addTab(self.probe_tab, "Probe")

        self.autolevel_tab = AutolevelTab(sender, signals)
        self.autolevel_tab.set_probe_common(self.probe_common)
        self.tabs.addTab(self.autolevel_tab, "Autolevel")

        from .camera_tab import CameraTab
        self.camera_tab = CameraTab(sender, signals)
        self.tabs.addTab(self.camera_tab, "Camera")

        from .orient_tab import OrientTab
        self.orient_tab = OrientTab(sender, signals)
        self.tabs.addTab(self.orient_tab, "Orient")

        self.tool_tab = ToolTab(sender, signals, self.probe_common)
        self.tabs.addTab(self.tool_tab, "Tool")

        layout.addWidget(self.tabs)

        # Wire generic update signal
        self.signals.generic_update.connect(self._on_generic_update)

        self.probe_common.loadConfig()

    def _on_generic_update(self, var):
        if var == "toolheight":
            self.tool_tab.update_tool_height()
        elif var == "TLO":
            self.probe_common.update_tlo_display()

    def saveConfig(self):
        self.probe_common.saveConfig()
        self.probe_tab.saveConfig()
        self.autolevel_tab.saveConfig()
        self.camera_tab.saveConfig()
        self.orient_tab.saveConfig()
        self.tool_tab.saveConfig()

    def loadConfig(self):
        self.probe_common.loadConfig()
        self.probe_tab.loadConfig()
        self.autolevel_tab.loadConfig()
        self.camera_tab.loadConfig()
        self.orient_tab.loadConfig()
        self.tool_tab.loadConfig()
