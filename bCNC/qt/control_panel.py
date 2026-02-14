# Qt Control Panel - DRO, connection, jog controls
#
# Replaces parts of ControlPage with a compact QWidget providing
# digital readout (DRO), connection controls, and jog buttons.

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QComboBox, QDoubleSpinBox, QDialog, QTextEdit,
)

import utils_core as Utils
from CNC import CNC, WCS
from Sender import CONNECTED, NOT_CONNECTED, STATECOLOR


# Jog step sizes (mm)
JOG_STEPS = [0.001, 0.01, 0.1, 1.0, 5.0, 10.0, 50.0, 100.0]


def _config_font(key, default_family="Sans", default_size=12, default_bold=False):
    """Load a QFont from [Font] config section.

    Config format: "FontFamily,size[,bold][,italic]" (matches Tkinter convention).
    """
    family, size, bold, italic = default_family, default_size, default_bold, False
    try:
        value = Utils.config.get("Font", key)
        if value:
            parts = [p.strip() for p in value.split(",")]
            if parts:
                family = parts[0]
            if len(parts) > 1:
                try:
                    size = abs(int(parts[1]))
                except ValueError:
                    pass
            for p in parts[2:]:
                if p.lower() == "bold":
                    bold = True
                elif p.lower() == "italic":
                    italic = True
    except Exception:
        logging.debug("Failed to load font config for '%s', using defaults", key)
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    return QFont(family, size, weight, italic)


class DROWidget(QWidget):
    """Digital Readout showing work and machine positions."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Load DRO fonts from [Font] config (matches Tkinter keys)
        wpos_font = _config_font("dro.wpos", "Sans", 12, True)
        mpos_font = _config_font("dro.mpos", "Sans", 12, False)

        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        headers = ["", "Work", "Machine"]
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl, 0, col)

        self._work_labels = {}
        self._mach_labels = {}
        colors = {
            "X": "red", "Y": "green", "Z": "blue",
            "A": "#FF8C00", "B": "#00CED1", "C": "#DA70D6",
        }
        axes = list("XYZ")
        if getattr(CNC, "enable6axisopt", False):
            axes += list("ABC")

        for row, axis in enumerate(axes, start=1):
            name_lbl = QLabel(axis)
            name_lbl.setFont(wpos_font)
            name_lbl.setStyleSheet(f"color: {colors[axis]};")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_lbl, row, 0)

            w_lbl = QLabel("0.000")
            w_lbl.setFont(wpos_font)
            w_lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            w_lbl.setMinimumWidth(100)
            layout.addWidget(w_lbl, row, 1)
            self._work_labels[axis] = w_lbl

            m_lbl = QLabel("0.000")
            m_lbl.setFont(mpos_font)
            m_lbl.setStyleSheet("color: gray;")
            m_lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            m_lbl.setMinimumWidth(100)
            layout.addWidget(m_lbl, row, 2)
            self._mach_labels[axis] = m_lbl

    def update_position(self, wx, wy, wz, mx, my, mz):
        """Update displayed coordinates."""
        fmt = "%.3f" if not CNC.inch else "%.4f"
        self._work_labels["X"].setText(fmt % wx)
        self._work_labels["Y"].setText(fmt % wy)
        self._work_labels["Z"].setText(fmt % wz)
        self._mach_labels["X"].setText(fmt % mx)
        self._mach_labels["Y"].setText(fmt % my)
        self._mach_labels["Z"].setText(fmt % mz)
        if getattr(CNC, "enable6axisopt", False):
            for axis, wk, mk in [("A","wa","ma"), ("B","wb","mb"), ("C","wc","mc")]:
                self._work_labels[axis].setText(fmt % CNC.vars[wk])
                self._mach_labels[axis].setText(fmt % CNC.vars[mk])


class ConnectionWidget(QWidget):
    """Serial connection controls."""

    connect_clicked = Signal()

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setMinimumWidth(150)
        self._populate_ports()
        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self._port_combo, 1)

        self._baud_combo = QComboBox()
        for rate in [9600, 19200, 38400, 57600, 115200, 230400]:
            self._baud_combo.addItem(str(rate))
        self._baud_combo.setCurrentText(
            str(Utils.getInt("Connection", "baud", 115200)))
        layout.addWidget(QLabel("Baud:"))
        layout.addWidget(self._baud_combo)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self._connect_btn)

        self._state_label = QLabel(NOT_CONNECTED)
        self._state_label.setMinimumWidth(100)
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setStyleSheet(
            f"background-color: {STATECOLOR[NOT_CONNECTED]}; padding: 2px;")
        layout.addWidget(self._state_label)

    def _populate_ports(self):
        """Scan for available serial ports."""
        self._port_combo.clear()
        try:
            import serial.tools.list_ports
            for port in serial.tools.list_ports.comports():
                self._port_combo.addItem(port.device)
        except ImportError:
            pass
        # Add saved port
        saved = Utils.getStr("Connection", "port", "")
        if saved and self._port_combo.findText(saved) < 0:
            self._port_combo.addItem(saved)
        if saved:
            self._port_combo.setCurrentText(saved)

    def _on_connect(self):
        if self.sender.serial is None:
            device = self._port_combo.currentText()
            baud = int(self._baud_combo.currentText())
            try:
                self.sender.open(device, baud)
            except Exception as e:
                self._state_label.setText(f"Error: {e}")
                return
        else:
            self.sender.close()
        self.connect_clicked.emit()

    def update_state(self, state, color):
        """Update connection state display."""
        self._state_label.setText(state)
        self._state_label.setStyleSheet(
            f"background-color: {color}; padding: 2px;")
        if self.sender.serial is not None:
            self._connect_btn.setText("Disconnect")
        else:
            self._connect_btn.setText("Connect")


class JogWidget(QWidget):
    """Jog control buttons and step size selector."""

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Step size selector
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step:"))
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.001, 1000.0)
        self._step_spin.setDecimals(3)
        self._step_spin.setValue(1.0)
        self._step_spin.setSuffix(" mm")
        step_layout.addWidget(self._step_spin)

        # Quick step buttons
        for step in [0.1, 1.0, 10.0]:
            btn = QPushButton(f"{step}")
            btn.setMaximumWidth(50)
            btn.clicked.connect(
                lambda checked, s=step: self._step_spin.setValue(s))
            step_layout.addWidget(btn)
        layout.addLayout(step_layout)

        # Jog buttons grid
        grid = QGridLayout()
        grid.setSpacing(2)

        buttons = {
            (0, 1): ("Y+", self._jog_yp),
            (2, 1): ("Y-", self._jog_yn),
            (1, 0): ("X-", self._jog_xn),
            (1, 2): ("X+", self._jog_xp),
            (0, 3): ("Z+", self._jog_zp),
            (2, 3): ("Z-", self._jog_zn),
            (1, 1): ("Home", self._home),
        }

        for (r, c), (label, callback) in buttons.items():
            btn = QPushButton(label)
            btn.setMinimumSize(50, 35)
            btn.clicked.connect(callback)
            grid.addWidget(btn, r, c)

        layout.addLayout(grid)

        # ABC jog buttons (conditional on 6-axis config)
        if getattr(CNC, "enable6axisopt", False):
            abc_grid = QGridLayout()
            abc_grid.setSpacing(2)
            for col, axis in enumerate(["A", "B", "C"]):
                btn_plus = QPushButton(f"{axis}+")
                btn_plus.setMinimumSize(50, 35)
                btn_plus.clicked.connect(
                    lambda checked, a=axis: self._jog(a, 1))
                abc_grid.addWidget(btn_plus, 0, col)
                btn_minus = QPushButton(f"{axis}-")
                btn_minus.setMinimumSize(50, 35)
                btn_minus.clicked.connect(
                    lambda checked, a=axis: self._jog(a, -1))
                abc_grid.addWidget(btn_minus, 1, col)
            layout.addLayout(abc_grid)

        # Action buttons
        action_layout = QHBoxLayout()
        for label, callback in [
            ("Unlock", lambda: sender.unlock()),
            ("Reset", lambda: sender.softReset()),
            ("Home All", lambda: sender.home()),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            action_layout.addWidget(btn)
        layout.addLayout(action_layout)

    def _jog(self, axis, direction):
        step = self._step_spin.value() * direction
        self.sender.jog(f"{axis}{step:.3f}")

    def _jog_xp(self): self._jog("X", 1)
    def _jog_xn(self): self._jog("X", -1)
    def _jog_yp(self): self._jog("Y", 1)
    def _jog_yn(self): self._jog("Y", -1)
    def _jog_zp(self): self._jog("Z", 1)
    def _jog_zn(self): self._jog("Z", -1)
    def _home(self): self.sender.home()


class StateWidget(QWidget):
    """Real-time feed/spindle display and override controls."""

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender

        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Row 0-2: Feed / Spindle / Rapid readouts with override %
        row_defs = [
            ("Feed", "_feed_label", "_ov_feed_label"),
            ("Spindle", "_spindle_label", "_ov_spindle_label"),
            ("Rapid", None, "_ov_rapid_label"),
        ]
        for row, (name, val_attr, ov_attr) in enumerate(row_defs):
            layout.addWidget(QLabel(name), row, 0)
            if val_attr:
                lbl = QLabel("0")
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                                 | Qt.AlignmentFlag.AlignVCenter)
                lbl.setMinimumWidth(60)
                layout.addWidget(lbl, row, 1)
                setattr(self, val_attr, lbl)
            layout.addWidget(QLabel("Ov"), row, 2)
            ov_lbl = QLabel("100%")
            ov_lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
            ov_lbl.setMinimumWidth(45)
            layout.addWidget(ov_lbl, row, 3)
            setattr(self, ov_attr, ov_lbl)

        # Row 3: Override adjustment buttons
        ov_btn_layout = QHBoxLayout()
        for label, callback in [
            ("F-10", lambda: self._adjust_override("_OvFeed", "OvFeed", -10)),
            ("F+10", lambda: self._adjust_override("_OvFeed", "OvFeed", 10)),
            ("S-10", lambda: self._adjust_override("_OvSpindle", "OvSpindle", -10)),
            ("S+10", lambda: self._adjust_override("_OvSpindle", "OvSpindle", 10)),
            ("Rapid", self._cycle_rapid),
            ("Reset", self._reset_overrides),
        ]:
            btn = QPushButton(label)
            btn.setMaximumHeight(28)
            btn.clicked.connect(callback)
            ov_btn_layout.addWidget(btn)
        layout.addLayout(ov_btn_layout, 3, 0, 1, 4)

        # Row 4: Spindle + Coolant controls
        sc_layout = QHBoxLayout()
        self._spindle_btn = QPushButton("Spindle ON")
        self._spindle_btn.setCheckable(True)
        self._spindle_btn.clicked.connect(self._toggle_spindle)
        sc_layout.addWidget(self._spindle_btn)

        flood_btn = QPushButton("Flood")
        flood_btn.clicked.connect(lambda: self._send_guarded("M8"))
        sc_layout.addWidget(flood_btn)

        mist_btn = QPushButton("Mist")
        mist_btn.clicked.connect(lambda: self._send_guarded("M7"))
        sc_layout.addWidget(mist_btn)

        cool_off_btn = QPushButton("Cool Off")
        cool_off_btn.clicked.connect(lambda: self._send_guarded("M9"))
        sc_layout.addWidget(cool_off_btn)

        layout.addLayout(sc_layout, 4, 0, 1, 4)

    def update_state(self, state, color):
        """Update all readout labels from CNC.vars."""
        self._feed_label.setText(f"{CNC.vars['curfeed']:.0f}")
        self._spindle_label.setText(f"{CNC.vars['curspindle']:.0f}")
        self._ov_feed_label.setText(f"{CNC.vars['OvFeed']}%")
        self._ov_spindle_label.setText(f"{CNC.vars['OvSpindle']}%")
        self._ov_rapid_label.setText(f"{CNC.vars['OvRapid']}%")
        # Update spindle button state
        is_on = CNC.vars.get("spindle", "M5") in ("M3", "M4")
        self._spindle_btn.setChecked(is_on)
        self._spindle_btn.setText("Spindle OFF" if is_on else "Spindle ON")

    def _adjust_override(self, target_key, current_key, delta):
        """Adjust an override target by delta, clamped 10-200."""
        current = CNC.vars.get(current_key, 100)
        CNC.vars[target_key] = max(10, min(200, current + delta))
        CNC.vars["_OvChanged"] = True

    def _cycle_rapid(self):
        """Cycle rapid override: 100 → 50 → 25 → 100."""
        current = CNC.vars.get("OvRapid", 100)
        if current >= 100:
            CNC.vars["_OvRapid"] = 50
        elif current >= 50:
            CNC.vars["_OvRapid"] = 25
        else:
            CNC.vars["_OvRapid"] = 100
        CNC.vars["_OvChanged"] = True

    def _reset_overrides(self):
        """Reset all overrides to 100%."""
        CNC.vars["_OvFeed"] = 100
        CNC.vars["_OvRapid"] = 100
        CNC.vars["_OvSpindle"] = 100
        CNC.vars["_OvChanged"] = True

    def _is_connected_and_ready(self):
        """Check if machine is connected and past initial state."""
        state = CNC.vars.get("state", NOT_CONNECTED)
        return state not in (NOT_CONNECTED, CONNECTED)

    def _send_guarded(self, gcode):
        """Send G-code only if connected and ready."""
        if self._is_connected_and_ready():
            self.sender.sendGCode(gcode)

    def _toggle_spindle(self):
        """Toggle spindle on/off."""
        if not self._is_connected_and_ready():
            self._spindle_btn.setChecked(False)
            return
        if CNC.vars.get("spindle", "M5") in ("M3", "M4"):
            self.sender.sendGCode("M5")
        else:
            rpm = CNC.vars.get("rpm", 0) or CNC.vars.get("curspindle", 0) or 1000
            self.sender.sendGCode(f"M3 S{rpm}")


class MacroEditDialog(QDialog):
    """Dialog for editing a user macro button's name, tooltip, and command."""

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self._index = index
        self.setWindowTitle(f"Edit Button {index}")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Name:"))
        self._name = QLineEdit(
            Utils.config.get("Buttons", f"name.{index}", fallback=str(index)))
        layout.addWidget(self._name)

        layout.addWidget(QLabel("Tooltip:"))
        self._tooltip = QLineEdit(
            Utils.config.get("Buttons", f"tooltip.{index}", fallback=""))
        layout.addWidget(self._tooltip)

        layout.addWidget(QLabel("Command:"))
        self._command = QTextEdit()
        self._command.setPlainText(
            Utils.config.get("Buttons", f"command.{index}", fallback=""))
        self._command.setMinimumHeight(120)
        layout.addWidget(self._command)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def accept(self):
        i = self._index
        if not Utils.config.has_section("Buttons"):
            Utils.config.add_section("Buttons")
        Utils.config.set("Buttons", f"name.{i}", self._name.text().strip())
        Utils.config.set("Buttons", f"tooltip.{i}", self._tooltip.text().strip())
        Utils.config.set("Buttons", f"command.{i}",
                         self._command.toPlainText().strip())
        super().accept()


class MacroButtonsWidget(QWidget):
    """User-configurable macro buttons loaded from [Buttons] config."""

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender
        self._buttons = []

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(2)
        self._build_buttons()

    def _build_buttons(self):
        for btn in self._buttons:
            btn.deleteLater()
        self._buttons.clear()

        n = Utils.getInt("Buttons", "n", 6)
        for i in range(1, n):  # Skip button 0 (Tkinter jog-pad origin)
            name = Utils.config.get("Buttons", f"name.{i}", fallback=str(i))
            tooltip = Utils.config.get("Buttons", f"tooltip.{i}", fallback="")
            btn = QPushButton(name)
            btn.setToolTip(tooltip or "Right-click to configure")
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.clicked.connect(lambda checked, idx=i: self._execute(idx))
            btn.customContextMenuRequested.connect(
                lambda pos, idx=i: self._edit(idx))
            row, col = divmod(i - 1, 3)  # 3-column grid
            self._layout.addWidget(btn, row, col)
            self._buttons.append(btn)

    def _execute(self, index):
        cmd = Utils.config.get("Buttons", f"command.{index}", fallback="")
        if not cmd:
            self._edit(index)
            return
        for line in cmd.splitlines():
            line = line.strip()
            if line:
                self.sender.executeCommand(line)

    def _edit(self, index):
        dlg = MacroEditDialog(index, self)
        if dlg.exec():
            self._build_buttons()


class ControlPanel(QWidget):
    """Combined control panel with DRO, connection, and jog widgets."""

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setContentsMargins(2, 2, 2, 2)
        self.connection = ConnectionWidget(sender)
        conn_layout.addWidget(self.connection)
        layout.addWidget(conn_group)

        # DRO group
        dro_group = QGroupBox("Position")
        dro_layout = QVBoxLayout(dro_group)
        dro_layout.setContentsMargins(2, 2, 2, 2)
        self.dro = DROWidget()
        dro_layout.addWidget(self.dro)

        # WCS selector (G54-G59)
        wcs_layout = QHBoxLayout()
        self._wcs_buttons = []
        for wcs in WCS:
            btn = QPushButton(wcs)
            btn.setCheckable(True)
            btn.setMaximumWidth(50)
            btn.clicked.connect(
                lambda checked, w=wcs: self._select_wcs(w))
            wcs_layout.addWidget(btn)
            self._wcs_buttons.append(btn)
        self._wcs_buttons[0].setChecked(True)  # G54 default
        dro_layout.addLayout(wcs_layout)

        # Zero-axis buttons
        zero_layout = QHBoxLayout()
        for axis in ["X", "Y", "Z"]:
            btn = QPushButton(f"{axis}=0")
            btn.setMaximumWidth(50)
            btn.clicked.connect(
                lambda checked, a=axis: self._zero_axis(a))
            zero_layout.addWidget(btn)
        if getattr(CNC, "enable6axisopt", False):
            for axis in ["A", "B", "C"]:
                btn = QPushButton(f"{axis}=0")
                btn.setMaximumWidth(50)
                btn.clicked.connect(
                    lambda checked, a=axis: self._zero_axis(a))
                zero_layout.addWidget(btn)
        dro_layout.addLayout(zero_layout)

        layout.addWidget(dro_group)

        # Jog group
        jog_group = QGroupBox("Jog")
        jog_layout = QVBoxLayout(jog_group)
        jog_layout.setContentsMargins(2, 2, 2, 2)
        self.jog = JogWidget(sender)
        jog_layout.addWidget(self.jog)
        layout.addWidget(jog_group)

        # State group (spindle / overrides)
        state_group = QGroupBox("Spindle / Overrides")
        state_layout = QVBoxLayout(state_group)
        state_layout.setContentsMargins(2, 2, 2, 2)
        self.state_widget = StateWidget(sender)
        state_layout.addWidget(self.state_widget)
        layout.addWidget(state_group)

        # Custom macro buttons
        macro_group = QGroupBox("Custom Buttons")
        macro_layout = QVBoxLayout(macro_group)
        macro_layout.setContentsMargins(2, 2, 2, 2)
        self.macro_buttons = MacroButtonsWidget(sender)
        macro_layout.addWidget(self.macro_buttons)
        layout.addWidget(macro_group)

        # Run controls
        run_group = QGroupBox("Execution")
        run_layout = QHBoxLayout(run_group)
        run_layout.setContentsMargins(2, 2, 2, 2)
        for label, signal in [
            ("Run", signals.run_requested),
            ("Pause", signals.pause_requested),
            ("Stop", signals.stop_requested),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(signal.emit)
            run_layout.addWidget(btn)
        layout.addWidget(run_group)

        layout.addStretch()

        # Wire signals
        signals.state_changed.connect(self.connection.update_state)
        signals.state_changed.connect(self.state_widget.update_state)
        signals.position_updated.connect(self.dro.update_position)
        signals.g_state_updated.connect(self._update_wcs)

    def _select_wcs(self, wcs):
        """Switch to the given workspace coordinate system."""
        self.sender.sendGCode(wcs)
        self.sender.viewState()

    def _update_wcs(self):
        """Highlight the active WCS button from CNC.vars."""
        active = CNC.vars.get("WCS", "G54")
        for btn in self._wcs_buttons:
            btn.setChecked(btn.text() == active)

    def _zero_axis(self, axis):
        """Zero a single axis via G10 L20."""
        args = {a: None for a in "xyzabc"}
        args[axis.lower()] = "0"
        self.sender.wcsSet(**args)
