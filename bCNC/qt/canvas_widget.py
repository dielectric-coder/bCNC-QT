# Qt Canvas Widget - QGraphicsView-based CNC visualization
#
# Replaces CNCCanvas(tkinter.Canvas) with QGraphicsView.
# Uses ViewTransform for coordinate math and SceneGraph
# primitives for rendering.

import math

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPen, QColor, QBrush, QPainter, QFont,
    QWheelEvent, QMouseEvent, QKeyEvent,
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsLineItem,
    QGraphicsEllipseItem, QGraphicsSimpleTextItem,
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QComboBox, QCheckBox, QLabel,
)

import ViewTransform
import PathGeometry
from CNC import CNC


# Colors matching the Tkinter version
COLORS = {
    "gantry": QColor("red"),
    "margin": QColor("magenta"),
    "grid": QColor(128, 128, 128),         # Gray
    "workarea": QColor("orange"),
    "enable": QColor("black"),
    "disable": QColor(211, 211, 211),       # LightGray
    "select": QColor("blue"),
    "process": QColor("green"),
    "rapid": QColor("black"),
    "axis_x": QColor("red"),
    "axis_y": QColor("green"),
    "axis_z": QColor("blue"),
    "background": QColor("white"),
    "box_select": QColor("cyan"),
}

ZOOM_FACTOR = 1.25


class CNCGraphicsView(QGraphicsView):
    """Custom QGraphicsView with zoom/pan and coordinate display.

    Handles mouse interaction for zooming (wheel), panning
    (middle-button drag), and coordinate display on hover.
    """

    coords_changed = Signal(float, float, float)
    canvas_block_clicked = Signal(int, bool)  # (block_id, ctrl_held)
    orient_click = Signal(float, float)       # scene coords click in orient mode

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setMouseTracking(True)
        self.setBackgroundBrush(COLORS["background"])

        self._panning = False
        self._pan_start = QPointF()
        self._action_mode = None

    def wheelEvent(self, event: QWheelEvent):
        """Zoom in/out with mouse wheel."""
        if event.angleDelta().y() > 0:
            factor = ZOOM_FACTOR
        else:
            factor = 1.0 / ZOOM_FACTOR
        self.scale(factor, factor)

    def set_action_mode(self, mode):
        """Set an action mode (e.g. 'add_orient') or None to clear."""
        self._action_mode = mode
        if mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._action_mode == "add_orient"):
            scene_pos = self.mapToScene(event.position().toPoint())
            self.orient_click.emit(scene_pos.x(), scene_pos.y())
            self.set_action_mode(None)
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene().itemAt(scene_pos, self.transform())
            path_id = self.scene().path_id_at(item) if item else None
            if path_id is not None:
                bid, lid = path_id
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                self.canvas_block_clicked.emit(bid, ctrl)
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
        else:
            # Update coordinate display
            scene_pos = self.mapToScene(event.position().toPoint())
            self.coords_changed.emit(scene_pos.x(), scene_pos.y(), 0.0)
            super().mouseMoveEvent(event)

    def fit_to_content(self):
        """Zoom to fit path content in view (excludes workarea/grid/axes)."""
        scene = self.scene()
        # Prefer fitting to path items only so the workarea rect
        # (which can be 300x300mm) doesn't dominate the viewport.
        if hasattr(scene, '_path_items') and scene._path_items:
            rect = QRectF()
            for item in scene._path_items:
                rect = rect.united(item.sceneBoundingRect())
        else:
            rect = scene.itemsBoundingRect()
        if rect.isNull():
            return
        margin = max(rect.width(), rect.height()) * 0.05
        rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


class CNCScene(QGraphicsScene):
    """Scene that renders CNC toolpaths.

    Holds all visual elements: grid, axes, margins, toolpaths,
    gantry position marker. Uses ViewTransform for projections
    and PathGeometry for geometry generation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view_mode = ViewTransform.VIEW_XY
        self.zoom = 1.0

        # Drawing flags
        self.draw_axes = True
        self.draw_grid = True
        self.draw_margin = True
        self.draw_workarea = True
        self.draw_paths = True
        self.draw_rapid = True
        self.draw_probe = True

        # Gantry marker items
        self._gantry_items = []

        # Probe overlay items
        self._probe_items = []

        # Work offset (for workarea rectangle)
        self._dx = 0.0
        self._dy = 0.0

        # Track path items for selection highlighting
        self._path_items = {}
        self._selection_state = {}  # {item: original_pen} for rollback

    def rebuild(self, gcode, cnc):
        """Full redraw: clear scene and rebuild everything.

        Args:
            gcode: The GCode object.
            cnc: The CNC interpreter instance.
        """
        self.clear()
        self._gantry_items = []
        self._probe_items = []
        self._path_items = {}
        self._selection_state = {}

        # Draw paths first so margins are computed before grid/workarea
        self._draw_paths(gcode, cnc)
        self._draw_grid()
        self._draw_margin()
        self._draw_workarea()
        self._draw_axes()
        self._draw_gantry(0, 0)

    def update_gantry(self, wx, wy, wz, mx, my, mz):
        """Update gantry position marker.

        Args:
            wx, wy, wz: Work position.
            mx, my, mz: Machine position.
        """
        coords = ViewTransform.project_3d_to_2d(
            [(wx, wy, wz)], self.view_mode, self.zoom)
        if coords:
            cx, cy = coords[0]
            self._draw_gantry(cx, cy)

        # Update work offset for workarea
        dx = wx - mx
        dy = wy - my
        if abs(dx - self._dx) > 0.0001 or abs(dy - self._dy) > 0.0001:
            self._dx = dx
            self._dy = dy

    def _project(self, xyz):
        """Project 3D coords to scene coords."""
        return ViewTransform.project_3d_to_2d(
            xyz, self.view_mode, self.zoom)

    def _make_pen(self, color, width=1, dash=None):
        """Create a cosmetic QPen (constant pixel width regardless of zoom)."""
        if isinstance(color, str):
            color = QColor(color)
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCosmetic(True)
        if dash:
            pen.setStyle(Qt.PenStyle.DashLine)
        return pen

    def _draw_grid(self):
        if not self.draw_grid:
            return
        if self.view_mode not in (
            ViewTransform.VIEW_XY, ViewTransform.VIEW_ISO1,
            ViewTransform.VIEW_ISO2, ViewTransform.VIEW_ISO3,
        ):
            return

        grid_lines = PathGeometry.generate_grid_lines(
            CNC.vars.get("axmin", -100), CNC.vars.get("axmax", 100),
            CNC.vars.get("aymin", -100), CNC.vars.get("aymax", 100),
        )
        pen = self._make_pen(COLORS["grid"], 0.5, dash=True)
        for xyz in grid_lines:
            coords = self._project(xyz)
            if len(coords) >= 2:
                self.addLine(
                    coords[0][0], coords[0][1],
                    coords[1][0], coords[1][1], pen)

    def _draw_margin(self):
        if not self.draw_margin:
            return

        if CNC.isMarginValid():
            xyz = PathGeometry.generate_margin_rect(
                CNC.vars["xmin"], CNC.vars["ymin"],
                CNC.vars["xmax"], CNC.vars["ymax"],
            )
            self._draw_polyline(xyz, COLORS["margin"], width=1)

        if CNC.isAllMarginValid():
            xyz = PathGeometry.generate_margin_rect(
                CNC.vars["axmin"], CNC.vars["aymin"],
                CNC.vars["axmax"], CNC.vars["aymax"],
            )
            self._draw_polyline(xyz, COLORS["margin"], width=1, dash=True)

    def _draw_workarea(self):
        if not self.draw_workarea:
            return
        xyz = PathGeometry.generate_workarea_rect(
            self._dx, self._dy, CNC.travel_x, CNC.travel_y)
        self._draw_polyline(xyz, COLORS["workarea"], width=1, dash=True)

    def _draw_axes(self):
        if not self.draw_axes:
            return
        s = ViewTransform.compute_axis_scale(
            CNC.vars.get("axmin", -100),
            CNC.vars.get("axmax", 100),
            CNC.inch)
        axes = PathGeometry.generate_axes(s)
        axis_colors = {
            "x": COLORS["axis_x"],
            "y": COLORS["axis_y"],
            "z": COLORS["axis_z"],
        }
        for name, xyz in axes.items():
            coords = self._project(xyz)
            if len(coords) >= 2:
                pen = self._make_pen(axis_colors[name], 1.5, dash=True)
                self.addLine(
                    coords[0][0], coords[0][1],
                    coords[1][0], coords[1][1], pen)

    def _draw_gantry(self, cx, cy):
        """Draw/update the gantry position marker."""
        for item in self._gantry_items:
            self.removeItem(item)
        self._gantry_items.clear()

        diameter = CNC.vars.get("diameter", 3.175)
        r = max(3, diameter / 2.0 * self.zoom)
        pen = self._make_pen(COLORS["gantry"], 2)

        if self.view_mode == ViewTransform.VIEW_XY:
            ellipse = self.addEllipse(
                cx - r, cy - r, 2 * r, 2 * r, pen)
            self._gantry_items.append(ellipse)
        else:
            # Side/ISO view: triangle + oval
            gx = r
            gh = 3 * r
            from PySide6.QtGui import QPolygonF
            triangle = QPolygonF([
                QPointF(cx - gx, cy - gh),
                QPointF(cx, cy),
                QPointF(cx + gx, cy - gh),
                QPointF(cx - gx, cy - gh),
            ])
            item = self.addPolygon(triangle, pen)
            self._gantry_items.append(item)

    def _draw_paths(self, gcode, cnc):
        """Draw all GCode toolpaths."""
        if not self.draw_paths:
            return

        cnc.initPath()
        cnc.resetAllMargins()
        last = (0.0, 0.0, 0.0)

        for i, block in enumerate(gcode.blocks):
            block.resetPath()

            for j, line in enumerate(block):
                try:
                    cmd = gcode.evaluate(CNC.compileLine(line))
                    if isinstance(cmd, tuple):
                        cmd = None
                    else:
                        cmd = CNC.breakLine(cmd)
                except Exception:
                    cmd = None

                if cmd is None:
                    block.addPath(None)
                    continue

                cnc.motionStart(cmd)
                xyz = cnc.motionPath()
                cnc.motionEnd()

                if not xyz:
                    block.addPath(None)
                    continue

                cnc.pathLength(block, xyz)
                if cnc.gcode in (1, 2, 3):
                    block.pathMargins(xyz)
                    cnc.pathMargins(block)

                if block.enable:
                    if cnc.gcode == 0 and self.draw_rapid:
                        xyz[0] = last
                    last = xyz[-1]
                else:
                    if cnc.gcode == 0:
                        block.addPath(None)
                        continue

                coords = self._project(xyz)
                if not coords or len(coords) < 2:
                    block.addPath(None)
                    continue

                if block.enable:
                    color = QColor(block.color) if block.color else COLORS["enable"]
                else:
                    color = COLORS["disable"]

                if cnc.gcode == 0:
                    if self.draw_rapid:
                        pen = self._make_pen(color, 0.5, dash=True)
                    else:
                        block.addPath(None)
                        continue
                else:
                    pen = self._make_pen(color, 1)

                item = self._add_polyline_item(coords, pen)
                self._path_items[item] = (i, j)
                block.addPath(id(item))

            block.endPath(cnc.x, cnc.y, cnc.z)

    def path_id_at(self, item):
        """Return (block_id, line_id) for a path item, or None."""
        return self._path_items.get(item)

    def highlight_selection(self, block_ids):
        """Highlight paths belonging to the given block ids."""
        self.clear_selection()
        if not block_ids:
            return
        bid_set = set(block_ids)
        highlight_pen = self._make_pen(COLORS["select"], 2)
        for item, (bid, lid) in self._path_items.items():
            if bid in bid_set:
                self._selection_state[item] = QPen(item.pen())
                item.setPen(highlight_pen)

    def clear_selection(self):
        """Restore original pens on previously highlighted items."""
        for item, pen in self._selection_state.items():
            try:
                item.setPen(pen)
            except RuntimeError:
                pass  # item already deleted by scene.clear()
        self._selection_state.clear()

    def _draw_polyline(self, xyz, color, width=1, dash=False):
        """Draw a polyline from 3D xyz coordinates."""
        coords = self._project(xyz)
        if len(coords) < 2:
            return None
        pen = self._make_pen(color, width, dash)
        return self._add_polyline_item(coords, pen)

    # ------------------------------------------------------------------
    # Probe overlay
    # ------------------------------------------------------------------
    def clear_probe_overlay(self):
        """Remove all probe overlay items from the scene."""
        for item in self._probe_items:
            try:
                self.removeItem(item)
            except RuntimeError:
                pass  # item already deleted by scene.clear()
        self._probe_items.clear()

    def draw_probe_overlay(self, probe):
        """Draw probe grid, points, and optional heatmap.

        Args:
            probe: A CNC.Probe instance.
        """
        self.clear_probe_overlay()
        if not self.draw_probe:
            return
        if probe is None:
            return

        self._draw_probe_grid(probe)
        self._draw_probe_points(probe)
        self._draw_probe_heatmap(probe)

    def _draw_probe_grid(self, probe):
        """Draw yellow grid lines at probe step intervals."""
        pen = QPen(QColor("yellow"))
        pen.setWidthF(0.5)
        pen.setStyle(Qt.PenStyle.DashLine)

        xstep = probe._xstep
        ystep = probe._ystep
        if xstep <= 0 or ystep <= 0:
            return

        # Vertical lines
        for i in range(probe.xn):
            x = probe.xmin + xstep * i
            pts = [(x, probe.ymin, 0), (x, probe.ymax, 0)]
            coords = self._project(pts)
            if len(coords) >= 2:
                item = self.addLine(
                    coords[0][0], coords[0][1],
                    coords[1][0], coords[1][1], pen)
                self._probe_items.append(item)

        # Horizontal lines
        for j in range(probe.yn):
            y = probe.ymin + ystep * j
            pts = [(probe.xmin, y, 0), (probe.xmax, y, 0)]
            coords = self._project(pts)
            if len(coords) >= 2:
                item = self.addLine(
                    coords[0][0], coords[0][1],
                    coords[1][0], coords[1][1], pen)
                self._probe_items.append(item)

    def _draw_probe_points(self, probe):
        """Draw green Z-height text labels at each probed point."""
        if not probe.points:
            return

        font = QFont("monospace", 7)
        for x, y, z in probe.points:
            coords = self._project([(x, y, z)])
            if not coords:
                continue
            cx, cy = coords[0]
            text = QGraphicsSimpleTextItem(f"{z:.3f}")
            text.setFont(font)
            text.setBrush(QBrush(QColor("green")))
            text.setPos(cx + 2, cy - 10)
            self.addItem(text)
            self._probe_items.append(text)

    def _draw_probe_heatmap(self, probe):
        """Draw a heatmap from probe Z data (blue-white-red).

        Requires probe.matrix to be populated. Uses QImage for pixel
        rendering without numpy/PIL dependency.
        """
        if probe.isEmpty():
            return

        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtWidgets import QGraphicsPixmapItem

        # Find Z range for color mapping
        zmin = float("inf")
        zmax = float("-inf")
        for row in probe.matrix:
            for val in row:
                if val < zmin:
                    zmin = val
                if val > zmax:
                    zmax = val

        zrange = zmax - zmin
        if zrange < 1e-10:
            return

        # Create image: 1 pixel per probe point
        w = probe.xn
        h = probe.yn
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)

        for j in range(h):
            for i in range(w):
                t = (probe.matrix[j][i] - zmin) / zrange  # 0..1
                # Blue (low) → White (mid) → Red (high)
                if t < 0.5:
                    s = t * 2  # 0..1
                    r = int(s * 255)
                    g = int(s * 255)
                    b = 255
                else:
                    s = (t - 0.5) * 2  # 0..1
                    r = 255
                    g = int((1 - s) * 255)
                    b = int((1 - s) * 255)
                img.setPixelColor(i, j, QColor(r, g, b, 120))

        # Project the probe area corners to get placement
        corners = [
            (probe.xmin, probe.ymin, 0),
            (probe.xmax, probe.ymax, 0),
        ]
        coords = self._project(corners)
        if len(coords) < 2:
            return

        sx = abs(coords[1][0] - coords[0][0])
        sy = abs(coords[1][1] - coords[0][1])
        if sx < 1 or sy < 1:
            return

        pixmap = QPixmap.fromImage(img).scaled(
            int(sx), int(sy),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

        item = QGraphicsPixmapItem(pixmap)
        # Position at top-left corner in scene coords
        left = min(coords[0][0], coords[1][0])
        top = min(coords[0][1], coords[1][1])
        item.setPos(left, top)
        item.setZValue(-1)  # Behind paths
        self.addItem(item)
        self._probe_items.append(item)

    def _add_polyline_item(self, coords, pen):
        """Add a polyline as connected line segments to the scene."""
        from PySide6.QtGui import QPainterPath
        from PySide6.QtWidgets import QGraphicsPathItem

        path = QPainterPath()
        path.moveTo(coords[0][0], coords[0][1])
        for x, y in coords[1:]:
            path.lineTo(x, y)
        item = QGraphicsPathItem(path)
        item.setPen(pen)
        self.addItem(item)
        return item


class CanvasPanel(QWidget):
    """Canvas panel with toolbar for view controls.

    Contains the QGraphicsView and a toolbar with view mode
    selector and drawing toggle checkboxes.
    """

    def __init__(self, signals, parent=None):
        super().__init__(parent)
        self.signals = signals

        self.scene = CNCScene()
        self.view = CNCGraphicsView(self.scene)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        toolbar.addWidget(QLabel(" View: "))
        self.view_combo = QComboBox()
        self.view_combo.addItems(ViewTransform.VIEWS)
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        toolbar.addWidget(self.view_combo)

        toolbar.addSeparator()

        for attr, label in [
            ("draw_grid", "Grid"),
            ("draw_axes", "Axes"),
            ("draw_margin", "Margin"),
            ("draw_workarea", "Workarea"),
            ("draw_paths", "Paths"),
            ("draw_rapid", "Rapid"),
            ("draw_probe", "Probe"),
        ]:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.toggled.connect(self._make_toggle(attr))
            toolbar.addWidget(cb)
            setattr(self, "cb_" + attr.replace("draw_", ""), cb)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(self.view)

        # Camera overlay
        from .camera_overlay import CameraOverlay
        self.camera_overlay = CameraOverlay(self.scene, self.view)

        # Orient overlay
        from .orient_overlay import OrientOverlay
        self.orient_overlay = OrientOverlay(self.scene)
        self.view.orient_click.connect(self._on_orient_click)

        # Wire coordinate display
        self.view.coords_changed.connect(self._on_coords)

        # Wire canvas click → central signal
        self.view.canvas_block_clicked.connect(
            self.signals.canvas_block_clicked.emit)

    def _on_view_changed(self, index):
        self.scene.view_mode = index
        self.signals.view_changed.emit(index)

    def _on_coords(self, sx, sy, sz):
        """Convert scene coords back to machine coords."""
        x, y, z = ViewTransform.unproject_2d_to_3d(
            sx, sy, self.scene.view_mode, max(self.scene.zoom, 0.001))
        self.signals.canvas_coords.emit(x, y, z)

    def rebuild(self, gcode, cnc):
        """Full redraw."""
        self.scene.rebuild(gcode, cnc)
        self.view.fit_to_content()

    def update_gantry(self, wx, wy, wz, mx, my, mz):
        """Update gantry position marker."""
        self.scene.update_gantry(wx, wy, wz, mx, my, mz)
        self.camera_overlay.update_gantry(wx, wy, wz)

    def draw_probe(self, probe):
        """Draw probe overlay on the canvas."""
        self.scene.draw_probe_overlay(probe)

    def highlight_selection(self, block_ids):
        """Highlight paths for the given block ids on the canvas."""
        self.scene.highlight_selection(block_ids)

    def _make_toggle(self, attr):
        """Return a slot that sets a scene draw flag and triggers redraw."""
        def _toggle(checked):
            setattr(self.scene, attr, checked)
            self.signals.draw_requested.emit()
        return _toggle

    # ------------------------------------------------------------------
    # Orient overlay
    # ------------------------------------------------------------------
    def _on_orient_click(self, sx, sy):
        """Canvas clicked in add-orient mode — unproject and emit marker."""
        x, y, z = ViewTransform.unproject_2d_to_3d(
            sx, sy, self.scene.view_mode, max(self.scene.zoom, 0.001))
        xm = CNC.vars.get("wx", 0.0)
        ym = CNC.vars.get("wy", 0.0)
        self.signals.orient_marker_added.emit(xm, ym, x, y)

    def enter_add_orient_mode(self):
        """Put the canvas view into add-orient-marker mode."""
        self.view.set_action_mode("add_orient")

    def draw_orient(self, orient):
        """Draw orient markers on the canvas."""
        self.orient_overlay.draw(
            orient, self.scene.view_mode, self.scene.zoom)
