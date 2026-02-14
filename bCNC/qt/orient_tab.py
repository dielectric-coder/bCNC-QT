# Qt Orient Tab — marker alignment management
#
# Ports the Tkinter Orient functionality to Qt. Users place
# marker pairs mapping machine positions to G-code design
# positions, solve for rotation+translation via least-squares,
# and transform G-code to align with the workpiece.

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QMessageBox,
)

from CommandDispatcher import GCodeOperations


class OrientTab(QWidget):
    """Orient marker management and alignment controls.

    Manages marker pairs (machine pos → gcode pos), solves
    rotation+translation, and applies orientation transform
    to selected G-code blocks.
    """

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals
        self._overlay = None
        self._editor_panel = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Markers group ---
        markers_group = QGroupBox("Markers")
        mg = QGridLayout(markers_group)

        # Row 0: Marker spinner + Add button
        mg.addWidget(QLabel("Marker:"), 0, 0)
        self._marker_spin = QSpinBox()
        self._marker_spin.setMinimum(1)
        self._marker_spin.setMaximum(1)
        self._marker_spin.setEnabled(False)
        self._marker_spin.valueChanged.connect(self._on_marker_changed)
        mg.addWidget(self._marker_spin, 0, 1, 1, 2)

        self._add_btn = QPushButton("Add")
        self._add_btn.setToolTip("Click on canvas to add a marker at current position")
        self._add_btn.clicked.connect(self._on_add)
        mg.addWidget(self._add_btn, 0, 3)

        # Row 1: GCode coordinates
        mg.addWidget(QLabel("GCode:"), 1, 0)
        self._gcode_x = QDoubleSpinBox()
        self._gcode_x.setRange(-10000, 10000)
        self._gcode_x.setDecimals(4)
        self._gcode_x.setPrefix("X ")
        self._gcode_x.editingFinished.connect(self._on_coords_edited)
        mg.addWidget(self._gcode_x, 1, 1)

        self._gcode_y = QDoubleSpinBox()
        self._gcode_y.setRange(-10000, 10000)
        self._gcode_y.setDecimals(4)
        self._gcode_y.setPrefix("Y ")
        self._gcode_y.editingFinished.connect(self._on_coords_edited)
        mg.addWidget(self._gcode_y, 1, 2)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setToolTip("Delete current marker")
        self._delete_btn.clicked.connect(self._on_delete)
        mg.addWidget(self._delete_btn, 1, 3)

        # Row 2: WPos (machine) coordinates
        mg.addWidget(QLabel("WPos:"), 2, 0)
        self._wpos_x = QDoubleSpinBox()
        self._wpos_x.setRange(-10000, 10000)
        self._wpos_x.setDecimals(4)
        self._wpos_x.setPrefix("X ")
        self._wpos_x.editingFinished.connect(self._on_coords_edited)
        mg.addWidget(self._wpos_x, 2, 1)

        self._wpos_y = QDoubleSpinBox()
        self._wpos_y.setRange(-10000, 10000)
        self._wpos_y.setDecimals(4)
        self._wpos_y.setPrefix("Y ")
        self._wpos_y.editingFinished.connect(self._on_coords_edited)
        mg.addWidget(self._wpos_y, 2, 2)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear all markers")
        self._clear_btn.clicked.connect(self._on_clear)
        mg.addWidget(self._clear_btn, 2, 3)

        mg.setColumnStretch(1, 1)
        mg.setColumnStretch(2, 1)
        layout.addWidget(markers_group)

        # --- Results group ---
        results_group = QGroupBox("Results")
        rg = QGridLayout(results_group)

        rg.addWidget(QLabel("Angle:"), 0, 0)
        self._angle_label = QLabel("—")
        self._angle_label.setStyleSheet(
            "color: darkblue; background: #e8e8e8; padding: 2px;")
        rg.addWidget(self._angle_label, 0, 1, 1, 2)

        self._orient_btn = QPushButton("Orient")
        self._orient_btn.setToolTip(
            "Apply orientation transform to selected blocks")
        self._orient_btn.clicked.connect(self._on_orient)
        rg.addWidget(self._orient_btn, 0, 3, 3, 1)

        rg.addWidget(QLabel("Offset:"), 1, 0)
        self._offset_label = QLabel("—")
        self._offset_label.setStyleSheet(
            "color: darkblue; background: #e8e8e8; padding: 2px;")
        rg.addWidget(self._offset_label, 1, 1, 1, 2)

        rg.addWidget(QLabel("Error:"), 2, 0)
        self._error_label = QLabel("—")
        self._error_label.setStyleSheet(
            "color: darkblue; background: #e8e8e8; padding: 2px;")
        rg.addWidget(self._error_label, 2, 1, 1, 2)

        rg.setColumnStretch(1, 1)
        rg.setColumnStretch(2, 1)
        layout.addWidget(results_group)

        layout.addStretch()

        # Wire signals
        self.signals.orient_marker_added.connect(self._on_marker_added)

    # ------------------------------------------------------------------
    # Injection setters (called from MainWindow after construction)
    # ------------------------------------------------------------------
    def set_orient_overlay(self, overlay):
        """Inject the OrientOverlay instance from CanvasPanel."""
        self._overlay = overlay

    def set_editor_panel(self, editor_panel):
        """Inject the EditorPanel for selection access."""
        self._editor_panel = editor_panel

    # ------------------------------------------------------------------
    # Add marker flow
    # ------------------------------------------------------------------
    def _on_add(self):
        """Request canvas to enter add-marker mode."""
        self.signals.orient_add_marker_mode.emit()

    def _on_marker_added(self, xm, ym, x, y):
        """A marker was placed on the canvas."""
        orient = self.sender.gcode.orient
        orient.add(xm, ym, x, y)
        self._update_spinner()
        self._marker_spin.setValue(len(orient))
        self._solve()
        self.signals.draw_orient.emit()

    # ------------------------------------------------------------------
    # Marker navigation
    # ------------------------------------------------------------------
    def _on_marker_changed(self, value):
        """Marker spinner changed — populate fields and highlight."""
        orient = self.sender.gcode.orient
        idx = value - 1
        if idx < 0 or idx >= len(orient):
            return
        xm, ym, x, y = orient[idx]
        self._wpos_x.setValue(xm)
        self._wpos_y.setValue(ym)
        self._gcode_x.setValue(x)
        self._gcode_y.setValue(y)
        if self._overlay:
            self._overlay.highlight(idx)

    # ------------------------------------------------------------------
    # Coordinate editing
    # ------------------------------------------------------------------
    def _on_coords_edited(self):
        """User edited coordinate spinboxes — update marker in model."""
        orient = self.sender.gcode.orient
        idx = self._marker_spin.value() - 1
        if idx < 0 or idx >= len(orient):
            return
        orient.markers[idx] = (
            self._wpos_x.value(),
            self._wpos_y.value(),
            self._gcode_x.value(),
            self._gcode_y.value(),
        )
        orient.valid = False
        orient.saved = False
        self._solve()
        self.signals.draw_orient.emit()

    # ------------------------------------------------------------------
    # Delete / Clear
    # ------------------------------------------------------------------
    def _on_delete(self):
        """Delete the currently selected marker."""
        orient = self.sender.gcode.orient
        idx = self._marker_spin.value() - 1
        if idx < 0 or idx >= len(orient):
            return
        orient.clear(idx)
        self._update_spinner()
        if len(orient) > 0:
            new_idx = min(idx, len(orient) - 1)
            self._marker_spin.setValue(new_idx + 1)
            self._on_marker_changed(new_idx + 1)
        else:
            self._clear_fields()
        self._solve()
        self.signals.draw_orient.emit()

    def _on_clear(self):
        """Clear all markers after confirmation."""
        orient = self.sender.gcode.orient
        if len(orient) == 0:
            return
        ans = QMessageBox.question(
            self, "Clear Orient Markers",
            f"Delete all {len(orient)} markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        orient.clear()
        self._update_spinner()
        self._clear_fields()
        self.signals.draw_orient.emit()

    # ------------------------------------------------------------------
    # Orient (apply transform)
    # ------------------------------------------------------------------
    def _on_orient(self):
        """Apply orientation transform to selected blocks."""
        orient = self.sender.gcode.orient
        if not orient.valid:
            QMessageBox.warning(
                self, "Orient",
                "No valid orientation solution. Add at least 2 markers.")
            return

        if self._editor_panel is None:
            QMessageBox.warning(
                self, "Orient", "Editor panel not available.")
            return

        items = self._editor_panel.get_clean_selection()
        if not items:
            QMessageBox.warning(
                self, "Orient",
                "Select blocks in the editor to orient.")
            return

        ops = GCodeOperations(self.sender.gcode)
        ops.execute_on_items("ORIENT", items)
        self._editor_panel.fill()
        self.signals.draw_requested.emit()

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    def _solve(self):
        """Solve the orientation system and display results."""
        orient = self.sender.gcode.orient
        if len(orient) < 2:
            self._angle_label.setText("—")
            self._offset_label.setText("—")
            self._error_label.setText("—")
            return

        try:
            phi, xo, yo = orient.solve()
            angle_deg = math.degrees(phi)
            self._angle_label.setText(f"{angle_deg:.4f}\u00b0")
            self._offset_label.setText(f"X {xo:.4f}  Y {yo:.4f}")

            minerr, avgerr, maxerr = orient.error()
            self._error_label.setText(
                f"min {minerr:.4f}  avg {avgerr:.4f}  max {maxerr:.4f}")
        except Exception as e:
            self._angle_label.setText(str(e))
            self._offset_label.setText("—")
            self._error_label.setText("—")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_spinner(self):
        """Update marker spinner range and enabled state."""
        orient = self.sender.gcode.orient
        n = len(orient)
        self._marker_spin.setMaximum(max(1, n))
        self._marker_spin.setEnabled(n > 0)
        self._delete_btn.setEnabled(n > 0)
        self._clear_btn.setEnabled(n > 0)

    def _clear_fields(self):
        """Reset coordinate fields and result labels."""
        self._wpos_x.setValue(0.0)
        self._wpos_y.setValue(0.0)
        self._gcode_x.setValue(0.0)
        self._gcode_y.setValue(0.0)
        self._angle_label.setText("—")
        self._offset_label.setText("—")
        self._error_label.setText("—")

    def refresh(self):
        """Refresh UI after loading an .orient file."""
        orient = self.sender.gcode.orient
        self._update_spinner()
        if len(orient) > 0:
            self._marker_spin.setValue(1)
            self._on_marker_changed(1)
        else:
            self._clear_fields()
        self._solve()

    def loadConfig(self):
        """No-op — orient data lives in .orient files."""
        pass

    def saveConfig(self):
        """No-op — orient data lives in .orient files."""
        pass
