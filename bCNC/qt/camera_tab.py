# Qt Camera Tab — settings and controls for camera overlay
#
# Provides camera configuration (location, rotation, offsets, scale),
# on/off controls, edge detection, freeze, save, and camera/spindle
# coordinate switching.

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QComboBox, QCheckBox, QMessageBox,
)

import utils_core as Utils
import Camera
from CNC import CNC

from .camera_overlay import CAMERA_LOCATION_ORDER


class CameraTab(QWidget):
    """Camera settings and controls tab for the Probe panel."""

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals
        self._overlay = None

        # Registration state for spindle↔camera offset
        self._spindle_x = 0.0
        self._spindle_y = 0.0

        # Save counter for filenames
        self._save_counter = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Camera Settings group ---
        settings_group = QGroupBox("Camera Settings")
        sg = QGridLayout(settings_group)
        row = 0

        # Location
        sg.addWidget(QLabel("Location:"), row, 0)
        self.location = QComboBox()
        self.location.addItems(CAMERA_LOCATION_ORDER)
        self.location.currentIndexChanged.connect(self._on_settings_changed)
        sg.addWidget(self.location, row, 1, 1, 2)
        row += 1

        # Rotation
        sg.addWidget(QLabel("Rotation:"), row, 0)
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-360, 360)
        self.rotation.setDecimals(1)
        self.rotation.setSuffix("\u00b0")
        self.rotation.valueChanged.connect(self._on_settings_changed)
        sg.addWidget(self.rotation, row, 1, 1, 2)
        row += 1

        # Haircross Offset
        sg.addWidget(QLabel("Haircross:"), row, 0)
        self.xcenter = QDoubleSpinBox()
        self.xcenter.setRange(-10000, 10000)
        self.xcenter.setDecimals(1)
        self.xcenter.setPrefix("X ")
        self.xcenter.valueChanged.connect(self._on_settings_changed)
        sg.addWidget(self.xcenter, row, 1)
        self.ycenter = QDoubleSpinBox()
        self.ycenter.setRange(-10000, 10000)
        self.ycenter.setDecimals(1)
        self.ycenter.setPrefix("Y ")
        self.ycenter.valueChanged.connect(self._on_settings_changed)
        sg.addWidget(self.ycenter, row, 2)
        row += 1

        # Scale
        sg.addWidget(QLabel("Scale:"), row, 0)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.001, 10000)
        self.scale.setDecimals(3)
        self.scale.valueChanged.connect(self._on_settings_changed)
        sg.addWidget(self.scale, row, 1, 1, 2)
        row += 1

        # Crosshair (diameter + Get button)
        sg.addWidget(QLabel("Crosshair:"), row, 0)
        self.diameter = QDoubleSpinBox()
        self.diameter.setRange(0.001, 10000)
        self.diameter.setDecimals(3)
        self.diameter.valueChanged.connect(self._on_settings_changed)
        sg.addWidget(self.diameter, row, 1)
        self.get_diameter_btn = QPushButton("Get")
        self.get_diameter_btn.setToolTip(
            "Get diameter from active endmill")
        self.get_diameter_btn.clicked.connect(self._on_get_diameter)
        sg.addWidget(self.get_diameter_btn, row, 2)
        row += 1

        # Offset (DX, DY, Z)
        sg.addWidget(QLabel("Offset:"), row, 0)
        offset_row = QHBoxLayout()
        self.dx = QDoubleSpinBox()
        self.dx.setRange(-10000, 10000)
        self.dx.setDecimals(3)
        self.dx.setPrefix("DX ")
        self.dx.valueChanged.connect(self._on_settings_changed)
        offset_row.addWidget(self.dx)
        self.dy = QDoubleSpinBox()
        self.dy.setRange(-10000, 10000)
        self.dy.setDecimals(3)
        self.dy.setPrefix("DY ")
        self.dy.valueChanged.connect(self._on_settings_changed)
        offset_row.addWidget(self.dy)
        self.z_offset = QDoubleSpinBox()
        self.z_offset.setRange(-10000, 10000)
        self.z_offset.setDecimals(3)
        self.z_offset.setPrefix("Z ")
        self.z_offset.valueChanged.connect(self._on_settings_changed)
        offset_row.addWidget(self.z_offset)
        sg.addLayout(offset_row, row, 1, 1, 2)
        row += 1

        # Register buttons
        sg.addWidget(QLabel("Register:"), row, 0)
        reg_row = QHBoxLayout()
        self.reg_spindle_btn = QPushButton("1. Spindle")
        self.reg_spindle_btn.setToolTip(
            "Move spindle to target, then click to record position")
        self.reg_spindle_btn.clicked.connect(self._on_register_spindle)
        reg_row.addWidget(self.reg_spindle_btn)
        self.reg_camera_btn = QPushButton("2. Camera")
        self.reg_camera_btn.setToolTip(
            "Move camera to same target, then click to compute offset")
        self.reg_camera_btn.clicked.connect(self._on_register_camera)
        reg_row.addWidget(self.reg_camera_btn)
        sg.addLayout(reg_row, row, 1, 1, 2)
        row += 1

        sg.setColumnStretch(1, 1)
        sg.setColumnStretch(2, 1)
        layout.addWidget(settings_group)

        # --- Controls group ---
        controls_group = QGroupBox("Controls")
        cl = QHBoxLayout(controls_group)

        self.switch_btn = QPushButton("Switch To Camera")
        self.switch_btn.setCheckable(True)
        self.switch_btn.clicked.connect(self._on_switch)
        cl.addWidget(self.switch_btn)

        self.edge_cb = QCheckBox("Edge")
        self.edge_cb.setToolTip("Enable edge detection overlay")
        self.edge_cb.toggled.connect(self._on_edge_toggled)
        cl.addWidget(self.edge_cb)

        self.freeze_cb = QCheckBox("Freeze")
        self.freeze_cb.setToolTip("Freeze current frame as overlay")
        self.freeze_cb.toggled.connect(self._on_freeze_toggled)
        cl.addWidget(self.freeze_cb)

        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save current camera frame to PNG")
        self.save_btn.clicked.connect(self._on_save)
        cl.addWidget(self.save_btn)

        layout.addWidget(controls_group)

        # --- On/Off row ---
        onoff_row = QHBoxLayout()
        self.on_btn = QPushButton("Camera ON")
        self.on_btn.clicked.connect(self._on_camera_on)
        onoff_row.addWidget(self.on_btn)
        self.off_btn = QPushButton("Camera OFF")
        self.off_btn.clicked.connect(self._on_camera_off)
        onoff_row.addWidget(self.off_btn)
        layout.addLayout(onoff_row)

        layout.addStretch()

        self.loadConfig()

    # ------------------------------------------------------------------
    # Overlay injection (called by MainWindow after construction)
    # ------------------------------------------------------------------
    def set_camera_overlay(self, overlay):
        """Inject the CameraOverlay instance from CanvasPanel."""
        self._overlay = overlay
        self._push_settings()

    # ------------------------------------------------------------------
    # Settings → overlay
    # ------------------------------------------------------------------
    def _on_settings_changed(self):
        self._push_settings()

    def _push_settings(self):
        """Push all UI values to the overlay."""
        if self._overlay is None:
            return

        from .camera_overlay import CAMERA_LOCATION
        loc_name = self.location.currentText()
        self._overlay.anchor = CAMERA_LOCATION.get(loc_name, "center")
        self._overlay.rotation = self.rotation.value()
        self._overlay.x_center = self.xcenter.value()
        self._overlay.y_center = self.ycenter.value()
        self._overlay.scale = self.scale.value()
        self._overlay.radius = self.diameter.value() / 2.0
        self._overlay.camera_dx = self.dx.value()
        self._overlay.camera_dy = self.dy.value()
        self._overlay.camera_z = self.z_offset.value()
        self._overlay.update_settings()

    # ------------------------------------------------------------------
    # Camera on/off
    # ------------------------------------------------------------------
    def _on_camera_on(self):
        if self._overlay is None:
            return
        if self._overlay.is_on():
            return
        if not Camera.hasOpenCV():
            QMessageBox.warning(
                self, "Camera Error",
                "OpenCV (cv2) is not available.\n"
                "Install it with: pip install opencv-python")
            return
        result = self._overlay.start()
        if result is False:
            QMessageBox.warning(
                self, "Camera Error",
                "Failed to open camera.\n"
                "Check camera index in Tools → Camera settings.")

    def _on_camera_off(self):
        if self._overlay is None:
            return
        self._overlay.stop()
        self.switch_btn.setChecked(False)
        self.freeze_cb.setChecked(False)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _on_switch(self, checked):
        """Toggle between spindle and camera coordinate systems."""
        if self._overlay is None:
            return

        wx = CNC.vars.get("wx", 0.0)
        wy = CNC.vars.get("wy", 0.0)
        dx_val = self.dx.value()
        dy_val = self.dy.value()
        z_val = self.z_offset.value()

        if checked:
            self.switch_btn.setText("Switch To Spindle")
            self.sender.sendGCode(
                f"G92X{dx_val + wx:g}Y{dy_val + wy:g}")
            self._overlay.camera_switch = True
        else:
            self.switch_btn.setText("Switch To Camera")
            self.sender.sendGCode("G92.1")
            self._overlay.camera_switch = False

        if z_val:
            self.sender.sendGCode(f"G0X{wx:g}Y{wy:g}Z{z_val:g}")
        else:
            self.sender.sendGCode(f"G0X{wx:g}Y{wy:g}")

    def _on_edge_toggled(self, checked):
        if self._overlay is not None:
            self._overlay.edge_detect = checked

    def _on_freeze_toggled(self, checked):
        if self._overlay is not None:
            self._overlay.freeze(checked)

    def _on_save(self):
        if self._overlay is None or not self._overlay.is_on():
            return
        self._save_counter += 1
        filename = f"camera{self._save_counter:02d}.png"
        self._overlay.save(filename)
        QMessageBox.information(
            self, "Camera Save", f"Saved frame as {filename}")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def _on_register_spindle(self):
        """Record current spindle position for offset calculation."""
        self._spindle_x = CNC.vars.get("wx", 0.0)
        self._spindle_y = CNC.vars.get("wy", 0.0)

    def _on_register_camera(self):
        """Compute camera offset from spindle position."""
        cx = CNC.vars.get("wx", 0.0)
        cy = CNC.vars.get("wy", 0.0)
        dx_val = self._spindle_x - cx
        dy_val = self._spindle_y - cy
        self.dx.setValue(dx_val)
        self.dy.setValue(dy_val)

    def _on_get_diameter(self):
        """Get tool diameter from CNC.vars."""
        d = CNC.vars.get("diameter", 3.175)
        self.diameter.setValue(d)

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------
    def loadConfig(self):
        anchor = Utils.getStr("Camera", "aligncam_anchor", "Center")
        idx = 0
        for i, name in enumerate(CAMERA_LOCATION_ORDER):
            if name == anchor:
                idx = i
                break
        self.location.setCurrentIndex(idx)

        self.rotation.setValue(
            Utils.getFloat("Camera", "aligncam_rotation", 0.0))
        self.xcenter.setValue(
            Utils.getFloat("Camera", "aligncam_xcenter", 0.0))
        self.ycenter.setValue(
            Utils.getFloat("Camera", "aligncam_ycenter", 0.0))
        self.scale.setValue(
            Utils.getFloat("Camera", "aligncam_scale", 10.0))
        self.diameter.setValue(
            Utils.getFloat("Camera", "aligncam_d", 3.175))
        self.dx.setValue(
            Utils.getFloat("Camera", "aligncam_dx", 0.0))
        self.dy.setValue(
            Utils.getFloat("Camera", "aligncam_dy", 0.0))
        self.z_offset.setValue(
            Utils.getFloat("Camera", "aligncam_z", 0.0))

    def saveConfig(self):
        if not Utils.config.has_section("Camera"):
            Utils.config.add_section("Camera")
        Utils.setStr("Camera", "aligncam_anchor",
                      self.location.currentText())
        Utils.setFloat("Camera", "aligncam_rotation",
                         self.rotation.value())
        Utils.setFloat("Camera", "aligncam_xcenter",
                         self.xcenter.value())
        Utils.setFloat("Camera", "aligncam_ycenter",
                         self.ycenter.value())
        Utils.setFloat("Camera", "aligncam_scale",
                         self.scale.value())
        Utils.setFloat("Camera", "aligncam_d",
                         self.diameter.value())
        Utils.setFloat("Camera", "aligncam_dx",
                         self.dx.value())
        Utils.setFloat("Camera", "aligncam_dy",
                         self.dy.value())
        Utils.setFloat("Camera", "aligncam_z",
                         self.z_offset.value())
