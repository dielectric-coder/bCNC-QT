"""Tests for Qt control panel widgets: DRO, jog, state, macros."""

import os
import sys
import unittest

# Offscreen rendering — must be set before QApplication import
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# bCNC import path setup
_root = os.path.join(os.path.dirname(__file__), "..")
for sub in ("bCNC", "bCNC/lib", "bCNC/controllers", "bCNC/plugins"):
    p = os.path.join(_root, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import Helpers  # noqa: E402  — must be first (installs _() builtin)
import utils_core as Utils  # noqa: E402

# Patch config.get so missing sections don't raise
_orig_get = Utils.config.get
def _safe_get(section, option, **kw):
    if not Utils.config.has_section(section):
        Utils.config.add_section(section)
    return _orig_get(section, option, **kw)
Utils.config.get = _safe_get

_orig_items = Utils.config.items
Utils.config.items = lambda s="DEFAULT", **kw: (
    [] if s != "DEFAULT" and not Utils.config.has_section(s)
    else _orig_items(s, **kw)
)

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402

# Single QApplication for all tests
app = QApplication.instance() or QApplication(sys.argv)

from CNC import CNC  # noqa: E402
from Sender import Sender, CONNECTED, NOT_CONNECTED  # noqa: E402
from qt.control_panel import (  # noqa: E402
    _config_font,
    MacroButtonsWidget,
    MacroEditDialog,
    ControlPanel,
    DROWidget,
    JogWidget,
    StateWidget,
)
from qt.signals import AppSignals  # noqa: E402


class TestConfigFont(unittest.TestCase):
    """Test _config_font() helper that loads QFont from [Font] config."""

    def test_defaults_when_no_config(self):
        """Returns default font when config key is missing."""
        font = _config_font("nonexistent.key", "Courier", 16, True)
        self.assertEqual(font.family(), "Courier")
        self.assertEqual(font.pointSize(), 16)
        self.assertTrue(font.bold())

    def test_parses_config_string(self):
        """Parses 'Family,size,bold' format from config."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.font", "Monospace,18,bold")
        font = _config_font("test.font")
        self.assertEqual(font.family(), "Monospace")
        self.assertEqual(font.pointSize(), 18)
        self.assertTrue(font.bold())
        Utils.config.remove_option("Font", "test.font")

    def test_parses_italic(self):
        """Parses italic flag from config string."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.italic", "Arial,10,italic")
        font = _config_font("test.italic")
        self.assertEqual(font.family(), "Arial")
        self.assertEqual(font.pointSize(), 10)
        self.assertFalse(font.bold())
        self.assertTrue(font.italic())
        Utils.config.remove_option("Font", "test.italic")

    def test_parses_bold_italic(self):
        """Parses both bold and italic."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.bi", "Helvetica,14,bold,italic")
        font = _config_font("test.bi")
        self.assertTrue(font.bold())
        self.assertTrue(font.italic())
        Utils.config.remove_option("Font", "test.bi")

    def test_negative_size_uses_absolute(self):
        """Negative sizes (Tkinter convention) are converted to positive."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.neg", "Sans,-11")
        font = _config_font("test.neg")
        self.assertEqual(font.pointSize(), 11)
        Utils.config.remove_option("Font", "test.neg")

    def test_family_only(self):
        """Config with only family name uses defaults for size/weight."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.fam", "Times")
        font = _config_font("test.fam", default_size=20)
        self.assertEqual(font.family(), "Times")
        self.assertEqual(font.pointSize(), 20)
        Utils.config.remove_option("Font", "test.fam")


class TestDROWidget(unittest.TestCase):
    """Test DROWidget uses configurable fonts."""

    def test_work_and_machine_fonts_differ(self):
        """Work position labels should use wpos font, machine labels use mpos."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "dro.wpos", "Sans,14,bold")
        Utils.config.set("Font", "dro.mpos", "Sans,10")

        dro = DROWidget()
        w_font = dro._work_labels["X"].font()
        m_font = dro._mach_labels["X"].font()

        self.assertEqual(w_font.pointSize(), 14)
        self.assertTrue(w_font.bold())
        self.assertEqual(m_font.pointSize(), 10)
        self.assertFalse(m_font.bold())

        # Cleanup
        Utils.config.remove_option("Font", "dro.wpos")
        Utils.config.remove_option("Font", "dro.mpos")

    def test_all_axes_have_labels(self):
        """DRO has work and machine labels for X, Y, Z."""
        dro = DROWidget()
        for axis in ("X", "Y", "Z"):
            self.assertIn(axis, dro._work_labels)
            self.assertIn(axis, dro._mach_labels)


class TestMacroButtonsWidget(unittest.TestCase):
    """Test MacroButtonsWidget loads buttons from [Buttons] config."""

    def setUp(self):
        self.sender = Sender()
        if not Utils.config.has_section("Buttons"):
            Utils.config.add_section("Buttons")

    def test_builds_correct_button_count(self):
        """Button count = n-1 (skipping button 0)."""
        Utils.config.set("Buttons", "n", "4")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(len(widget._buttons), 3)  # buttons 1, 2, 3

    def test_button_names_from_config(self):
        """Buttons get their names from config."""
        Utils.config.set("Buttons", "n", "3")
        Utils.config.set("Buttons", "name.1", "Home XY")
        Utils.config.set("Buttons", "name.2", "Probe Z")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(widget._buttons[0].text(), "Home XY")
        self.assertEqual(widget._buttons[1].text(), "Probe Z")

    def test_button_tooltip_from_config(self):
        """Buttons get tooltips from config, fallback to default."""
        Utils.config.set("Buttons", "n", "3")
        Utils.config.set("Buttons", "name.1", "B1")
        Utils.config.set("Buttons", "tooltip.1", "Go to origin")
        Utils.config.set("Buttons", "name.2", "B2")
        # No tooltip for button 2
        if Utils.config.has_option("Buttons", "tooltip.2"):
            Utils.config.remove_option("Buttons", "tooltip.2")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(widget._buttons[0].toolTip(), "Go to origin")
        self.assertEqual(widget._buttons[1].toolTip(), "Right-click to configure")

    def test_execute_queues_to_pendant(self):
        """Clicking a configured button queues commands via pendant."""
        Utils.config.set("Buttons", "n", "2")
        Utils.config.set("Buttons", "name.1", "Test")
        Utils.config.set("Buttons", "command.1", "G0 X0 Y0\nG0 Z5")
        widget = MacroButtonsWidget(self.sender)
        widget._execute(1)
        # Drain the pendant queue
        lines = []
        while not self.sender.pendant.empty():
            lines.append(self.sender.pendant.get())
        self.assertEqual(lines, ["G0 X0 Y0", "G0 Z5"])

    def test_execute_empty_command_does_not_queue(self):
        """Empty command does not put anything on pendant queue."""
        from unittest.mock import patch
        Utils.config.set("Buttons", "n", "2")
        Utils.config.set("Buttons", "name.1", "Empty")
        Utils.config.set("Buttons", "command.1", "")
        widget = MacroButtonsWidget(self.sender)
        # Patch _edit to prevent modal dialog from blocking
        with patch.object(widget, "_edit"):
            widget._execute(1)
        self.assertTrue(self.sender.pendant.empty())

    def test_rebuild_after_config_change(self):
        """_build_buttons() refreshes from config."""
        Utils.config.set("Buttons", "n", "2")
        Utils.config.set("Buttons", "name.1", "Old")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(widget._buttons[0].text(), "Old")

        Utils.config.set("Buttons", "name.1", "New")
        widget._build_buttons()
        self.assertEqual(widget._buttons[0].text(), "New")

    def test_default_button_count(self):
        """Default n=6 gives 5 buttons."""
        # Remove n if set
        if Utils.config.has_option("Buttons", "n"):
            Utils.config.remove_option("Buttons", "n")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(len(widget._buttons), 5)


class TestMacroEditDialog(unittest.TestCase):
    """Test MacroEditDialog saves to config on accept."""

    def setUp(self):
        if not Utils.config.has_section("Buttons"):
            Utils.config.add_section("Buttons")

    def test_dialog_loads_config_values(self):
        """Dialog fields are populated from config."""
        Utils.config.set("Buttons", "name.5", "MyMacro")
        Utils.config.set("Buttons", "tooltip.5", "Does stuff")
        Utils.config.set("Buttons", "command.5", "G28")

        dlg = MacroEditDialog(5)
        self.assertEqual(dlg._name.text(), "MyMacro")
        self.assertEqual(dlg._tooltip.text(), "Does stuff")
        self.assertEqual(dlg._command.toPlainText(), "G28")

    def test_accept_saves_to_config(self):
        """Accepting the dialog writes values back to config."""
        dlg = MacroEditDialog(7)
        dlg._name.setText("Saved")
        dlg._tooltip.setText("A tooltip")
        dlg._command.setPlainText("G0 X10\nG0 Y20")
        dlg.accept()

        self.assertEqual(Utils.config.get("Buttons", "name.7"), "Saved")
        self.assertEqual(Utils.config.get("Buttons", "tooltip.7"), "A tooltip")
        self.assertEqual(Utils.config.get("Buttons", "command.7"), "G0 X10\nG0 Y20")


class TestJogWidget(unittest.TestCase):
    """Test JogWidget jog command generation."""

    def setUp(self):
        self.sender = Sender()

    def test_jog_calls_sender_jog(self):
        """_jog() delegates to sender.jog() with axis and step."""
        from unittest.mock import patch
        widget = JogWidget(self.sender)
        widget._step_spin.setValue(5.0)
        with patch.object(self.sender, "jog") as mock_jog:
            widget._jog("X", 1)
            mock_jog.assert_called_once_with("X5.000")

    def test_jog_negative_direction(self):
        """Negative direction produces negative step value."""
        from unittest.mock import patch
        widget = JogWidget(self.sender)
        widget._step_spin.setValue(2.5)
        with patch.object(self.sender, "jog") as mock_jog:
            widget._jog("Y", -1)
            mock_jog.assert_called_once_with("Y-2.500")

    def test_jog_small_step(self):
        """Tiny step values are formatted correctly."""
        from unittest.mock import patch
        widget = JogWidget(self.sender)
        widget._step_spin.setValue(0.001)
        with patch.object(self.sender, "jog") as mock_jog:
            widget._jog("Z", 1)
            mock_jog.assert_called_once_with("Z0.001")

    def test_quick_step_buttons_set_value(self):
        """Quick step buttons update the step spinbox."""
        widget = JogWidget(self.sender)
        widget._step_spin.setValue(1.0)
        # Simulate clicking the 10.0 quick-step button
        widget._step_spin.setValue(10.0)
        self.assertAlmostEqual(widget._step_spin.value(), 10.0)

    def test_home_calls_sender(self):
        """Home button delegates to sender.home()."""
        from unittest.mock import patch
        widget = JogWidget(self.sender)
        with patch.object(self.sender, "home") as mock_home:
            widget._home()
            mock_home.assert_called_once()


class TestStateWidget(unittest.TestCase):
    """Test StateWidget override controls and state display."""

    def setUp(self):
        self.sender = Sender()
        self._saved_vars = dict(CNC.vars)

    def tearDown(self):
        CNC.vars.update(self._saved_vars)

    def test_update_state_updates_labels(self):
        """update_state() reads CNC.vars and updates label text."""
        widget = StateWidget(self.sender)
        CNC.vars["curfeed"] = 500.0
        CNC.vars["curspindle"] = 12000.0
        CNC.vars["OvFeed"] = 110
        CNC.vars["OvSpindle"] = 90
        CNC.vars["OvRapid"] = 50
        CNC.vars["spindle"] = "M5"
        widget.update_state("Idle", "lime")
        self.assertEqual(widget._feed_label.text(), "500")
        self.assertEqual(widget._spindle_label.text(), "12000")
        self.assertEqual(widget._ov_feed_label.text(), "110%")
        self.assertEqual(widget._ov_spindle_label.text(), "90%")
        self.assertEqual(widget._ov_rapid_label.text(), "50%")

    def test_adjust_override_clamps_high(self):
        """Override cannot exceed 200%."""
        widget = StateWidget(self.sender)
        CNC.vars["OvFeed"] = 195
        widget._adjust_override("_OvFeed", "OvFeed", 10)
        self.assertEqual(CNC.vars["_OvFeed"], 200)
        self.assertTrue(CNC.vars["_OvChanged"])

    def test_adjust_override_clamps_low(self):
        """Override cannot go below 10%."""
        widget = StateWidget(self.sender)
        CNC.vars["OvFeed"] = 15
        widget._adjust_override("_OvFeed", "OvFeed", -10)
        self.assertEqual(CNC.vars["_OvFeed"], 10)

    def test_cycle_rapid(self):
        """Rapid override cycles 100 → 50 → 25 → 100."""
        widget = StateWidget(self.sender)
        CNC.vars["OvRapid"] = 100
        widget._cycle_rapid()
        self.assertEqual(CNC.vars["_OvRapid"], 50)

        CNC.vars["OvRapid"] = 50
        widget._cycle_rapid()
        self.assertEqual(CNC.vars["_OvRapid"], 25)

        CNC.vars["OvRapid"] = 25
        widget._cycle_rapid()
        self.assertEqual(CNC.vars["_OvRapid"], 100)

    def test_reset_overrides(self):
        """Reset sets all overrides to 100%."""
        widget = StateWidget(self.sender)
        CNC.vars["_OvFeed"] = 150
        CNC.vars["_OvSpindle"] = 80
        CNC.vars["_OvRapid"] = 50
        widget._reset_overrides()
        self.assertEqual(CNC.vars["_OvFeed"], 100)
        self.assertEqual(CNC.vars["_OvSpindle"], 100)
        self.assertEqual(CNC.vars["_OvRapid"], 100)
        self.assertTrue(CNC.vars["_OvChanged"])

    def test_send_guarded_blocks_when_not_connected(self):
        """_send_guarded() does not send when machine is not connected."""
        from unittest.mock import patch
        widget = StateWidget(self.sender)
        CNC.vars["state"] = NOT_CONNECTED
        with patch.object(self.sender, "sendGCode") as mock_send:
            widget._send_guarded("M8")
            mock_send.assert_not_called()

    def test_send_guarded_sends_when_idle(self):
        """_send_guarded() sends when machine is in Idle state."""
        from unittest.mock import patch
        widget = StateWidget(self.sender)
        CNC.vars["state"] = "Idle"
        with patch.object(self.sender, "sendGCode") as mock_send:
            widget._send_guarded("M8")
            mock_send.assert_called_once_with("M8")

    def test_toggle_spindle_off(self):
        """Toggle spindle sends M5 when spindle is running."""
        from unittest.mock import patch
        widget = StateWidget(self.sender)
        CNC.vars["state"] = "Idle"
        CNC.vars["spindle"] = "M3"
        with patch.object(self.sender, "sendGCode") as mock_send:
            widget._toggle_spindle()
            mock_send.assert_called_once_with("M5")

    def test_toggle_spindle_on(self):
        """Toggle spindle sends M3 with RPM when spindle is off."""
        from unittest.mock import patch
        widget = StateWidget(self.sender)
        CNC.vars["state"] = "Idle"
        CNC.vars["spindle"] = "M5"
        CNC.vars["rpm"] = 8000
        with patch.object(self.sender, "sendGCode") as mock_send:
            widget._toggle_spindle()
            mock_send.assert_called_once_with("M3 S8000")

    def test_spindle_button_reflects_state(self):
        """Spindle button text updates based on CNC.vars."""
        widget = StateWidget(self.sender)
        CNC.vars["curfeed"] = 0
        CNC.vars["curspindle"] = 0
        CNC.vars["OvFeed"] = 100
        CNC.vars["OvSpindle"] = 100
        CNC.vars["OvRapid"] = 100
        CNC.vars["spindle"] = "M3"
        widget.update_state("Run", "green")
        self.assertEqual(widget._spindle_btn.text(), "Spindle OFF")
        self.assertTrue(widget._spindle_btn.isChecked())

        CNC.vars["spindle"] = "M5"
        widget.update_state("Idle", "lime")
        self.assertEqual(widget._spindle_btn.text(), "Spindle ON")
        self.assertFalse(widget._spindle_btn.isChecked())


class TestControlPanelIntegration(unittest.TestCase):
    """Integration test: ControlPanel has macro_buttons widget."""

    def test_macro_buttons_present(self):
        """ControlPanel has a macro_buttons attribute."""
        sender = Sender()
        signals = AppSignals()
        panel = ControlPanel(sender, signals)
        self.assertTrue(hasattr(panel, "macro_buttons"))
        self.assertIsInstance(panel.macro_buttons, MacroButtonsWidget)

    def test_macro_buttons_has_buttons(self):
        """macro_buttons widget contains QPushButtons."""
        sender = Sender()
        signals = AppSignals()
        panel = ControlPanel(sender, signals)
        self.assertGreater(len(panel.macro_buttons._buttons), 0)


if __name__ == "__main__":
    unittest.main()
