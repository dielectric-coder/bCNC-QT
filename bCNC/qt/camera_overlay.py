# Qt Camera Overlay — live video feed on QGraphicsScene
#
# Manages Camera instance, QTimer refresh, scene items (pixmap,
# crosshair lines, circles), and anchor-based positioning.

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem, QGraphicsLineItem, QGraphicsEllipseItem,
)

import Camera
import ViewTransform

# Anchor location mapping: display name → internal key
CAMERA_LOCATION = {
    "Gantry": "gantry",
    "Top-Left": "nw",
    "Top": "n",
    "Top-Right": "ne",
    "Left": "w",
    "Center": "center",
    "Right": "e",
    "Bottom-Left": "sw",
    "Bottom": "s",
    "Bottom-Right": "se",
}

CAMERA_LOCATION_ORDER = [
    "Gantry",
    "Top-Left",
    "Top",
    "Top-Right",
    "Left",
    "Center",
    "Right",
    "Bottom-Left",
    "Bottom",
    "Bottom-Right",
]

CAMERA_COLOR = QColor("cyan")
REFRESH_MS = 100


class CameraOverlay:
    """Camera video overlay on the CNC canvas scene.

    Owns a Camera instance, a QTimer for periodic refresh, and
    QGraphicsScene items for the video feed, crosshair, and circles.
    """

    def __init__(self, scene, view):
        self._scene = scene
        self._view = view
        self._camera = Camera.Camera("aligncam")

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)

        # Scene items (created on first frame)
        self._pixmap_item = None
        self._hori_line = None
        self._vert_line = None
        self._inner_circle = None
        self._outer_circle = None

        # Display properties
        self.anchor = "center"
        self.rotation = 0.0
        self.x_center = 0.0
        self.y_center = 0.0
        self.scale = 10.0
        self.radius = 1.5875    # half of default 3.175mm diameter
        self.edge_detect = False
        self.camera_dx = 0.0
        self.camera_dy = 0.0
        self.camera_z = 0.0
        self.camera_switch = False

        # Cached gantry position (work coords)
        self._gantry_wx = 0.0
        self._gantry_wy = 0.0
        self._gantry_wz = 0.0

    def start(self):
        """Start camera capture and refresh timer.

        Returns False if camera failed to open.
        """
        if not Camera.hasOpenCV():
            return False
        result = self._camera.start()
        if result is False:
            return False
        self._timer.start(REFRESH_MS)
        return True

    def stop(self):
        """Stop refresh timer, remove scene items, stop camera."""
        self._timer.stop()
        self._remove_items()
        self._camera.stop()

    def is_on(self):
        """Return True if camera is currently active."""
        return self._camera.isOn()

    def update_gantry(self, wx, wy, wz):
        """Cache gantry position for Gantry anchor mode."""
        self._gantry_wx = wx
        self._gantry_wy = wy
        self._gantry_wz = wz

    def update_settings(self):
        """Push rotation/xcenter/ycenter to camera and reposition."""
        self._camera.rotation = self.rotation
        self._camera.xcenter = self.x_center
        self._camera.ycenter = self.y_center
        if self._pixmap_item is not None:
            self._reposition()

    def freeze(self, enabled):
        """Toggle frame freeze overlay."""
        self._camera.freeze(enabled)

    def save(self, filename):
        """Save current frame to file."""
        self._camera.save(filename)

    # ------------------------------------------------------------------
    # Timer callback
    # ------------------------------------------------------------------
    def _refresh(self):
        """Read a frame, optionally apply edge detection, and display."""
        if not self._camera.isOn():
            return

        if not self._camera.read():
            return

        if self.edge_detect:
            self._camera.canny(50, 200)

        # Resize based on zoom and scale
        zoom = self._scene.zoom if hasattr(self._scene, 'zoom') else 1.0
        factor = zoom / self.scale if self.scale > 0 else 1.0
        vp = self._view.viewport()
        max_w = vp.width() if vp else 2000
        max_h = vp.height() if vp else 2000
        self._camera.resize(factor, max_w, max_h)

        # Convert to QImage → QPixmap
        qimg = self._camera.toQImage()
        if qimg is None:
            return
        pixmap = QPixmap.fromImage(qimg)

        if self._pixmap_item is None:
            self._create_items(pixmap)
        else:
            self._pixmap_item.setPixmap(pixmap)

        self._reposition()

    # ------------------------------------------------------------------
    # Scene item management
    # ------------------------------------------------------------------
    def _create_items(self, pixmap):
        """Create scene items for camera overlay."""
        # Video feed (Z=5, below crosshair)
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._pixmap_item.setZValue(5)
        self._scene.addItem(self._pixmap_item)

        # Crosshair and circles (Z=6, above video)
        pen_solid = QPen(CAMERA_COLOR)
        pen_solid.setWidthF(1)

        pen_dash = QPen(CAMERA_COLOR)
        pen_dash.setWidthF(1)
        pen_dash.setStyle(Qt.PenStyle.DashLine)

        self._hori_line = QGraphicsLineItem()
        self._hori_line.setPen(pen_solid)
        self._hori_line.setZValue(6)
        self._scene.addItem(self._hori_line)

        self._vert_line = QGraphicsLineItem()
        self._vert_line.setPen(pen_solid)
        self._vert_line.setZValue(6)
        self._scene.addItem(self._vert_line)

        self._inner_circle = QGraphicsEllipseItem()
        self._inner_circle.setPen(pen_solid)
        self._inner_circle.setZValue(6)
        self._scene.addItem(self._inner_circle)

        self._outer_circle = QGraphicsEllipseItem()
        self._outer_circle.setPen(pen_dash)
        self._outer_circle.setZValue(6)
        self._scene.addItem(self._outer_circle)

    def _remove_items(self):
        """Remove all camera items from the scene."""
        for attr in ('_pixmap_item', '_hori_line', '_vert_line',
                      '_inner_circle', '_outer_circle'):
            item = getattr(self, attr, None)
            if item is not None:
                try:
                    self._scene.removeItem(item)
                except RuntimeError:
                    pass
                setattr(self, attr, None)

    # ------------------------------------------------------------------
    # Positioning
    # ------------------------------------------------------------------
    def _reposition(self):
        """Position all camera items based on current anchor mode."""
        if self._pixmap_item is None:
            return

        pixmap = self._pixmap_item.pixmap()
        pw = pixmap.width()
        ph = pixmap.height()
        if pw == 0 or ph == 0:
            return

        zoom = self._scene.zoom if hasattr(self._scene, 'zoom') else 1.0

        x, y = self._compute_anchor_pos(zoom)

        # Center pixmap at (x, y)
        self._pixmap_item.setPos(x - pw / 2, y - ph / 2)

        # Crosshair lines spanning the image
        self._hori_line.setLine(x - pw / 2, y, x + pw / 2, y)
        self._vert_line.setLine(x, y - ph / 2, x, y + ph / 2)

        # Circle radii — scale with zoom in gantry mode, else with scale
        if self.anchor == "gantry":
            r = self.radius * zoom
        else:
            if zoom / self.scale > 1.0:
                r = self.radius * zoom
            else:
                r = self.radius * self.scale

        self._inner_circle.setRect(x - r, y - r, 2 * r, 2 * r)
        r2 = 2 * r
        self._outer_circle.setRect(x - r2, y - r2, 2 * r2, 2 * r2)

    def _compute_anchor_pos(self, zoom):
        """Compute the center position for camera overlay in scene coords."""
        if self.anchor == "gantry":
            # Project gantry position to scene coordinates
            view_mode = self._scene.view_mode
            coords = ViewTransform.project_3d_to_2d(
                [(self._gantry_wx, self._gantry_wy, self._gantry_wz)],
                view_mode, zoom)
            if coords:
                x, y = coords[0]
            else:
                x, y = 0, 0

            # Apply camera offset (unless in camera-switch mode)
            if not self.camera_switch:
                x += self.camera_dx * zoom
                y -= self.camera_dy * zoom

            return x, y

        # Viewport-anchored modes — map viewport edges to scene coords
        vp = self._view.viewport()
        vw = vp.width() if vp else 800
        vh = vp.height() if vp else 600

        pixmap = self._pixmap_item.pixmap()
        pw2 = pixmap.width() / 2
        ph2 = pixmap.height() / 2

        # Default: center of viewport
        vx = vw / 2
        vy = vh / 2

        anchor = self.anchor
        if "n" in anchor:
            vy = ph2
        elif "s" in anchor:
            vy = vh - ph2

        if "w" in anchor:
            vx = pw2
        elif "e" in anchor:
            vx = vw - pw2

        # Map viewport pixel to scene coordinate
        scene_pt = self._view.mapToScene(QPoint(int(vx), int(vy)))
        return scene_pt.x(), scene_pt.y()
