# Qt Orient Overlay — marker drawing on QGraphicsScene
#
# Draws orient marker pairs (machine pos + gcode pos) with
# connecting lines and error circles. Static scene items,
# no timer — redrawn on demand via draw().

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem

import ViewTransform

# Drawing constants
CROSS_ARM = 3.0  # half-length of cross arms in scene units
COLOR_MACHINE = QColor("green")    # machine position cross
COLOR_GCODE = QColor("red")        # gcode position cross
COLOR_LINK = QColor("blue")        # connecting line
COLOR_ERROR = QColor(255, 0, 0, 80)  # error circle fill


class OrientOverlay:
    """Draws orient markers on a QGraphicsScene.

    Each marker is a pair of crosses (machine + gcode position)
    connected by a dashed blue line. Error circles are drawn
    when orient.errors is populated.
    """

    def __init__(self, scene):
        self._scene = scene
        self._items = []           # flat list of all scene items
        self._marker_items = []    # list of lists, grouped per marker
        self._selected = -1

    def draw(self, orient, view_mode, zoom):
        """Draw all orient markers on the scene.

        Args:
            orient: CNC.Orient instance.
            view_mode: ViewTransform view constant (VIEW_XY, etc.).
            zoom: Current scene zoom factor.
        """
        self.clear()

        # Only draw in XY view
        if view_mode not in (ViewTransform.VIEW_XY,):
            return

        for i, (xm, ym, x, y) in enumerate(orient.markers):
            group = []

            # Project machine position and gcode position
            m_coords = ViewTransform.project_3d_to_2d(
                [(xm, ym, 0)], view_mode, zoom)
            g_coords = ViewTransform.project_3d_to_2d(
                [(x, y, 0)], view_mode, zoom)

            if not m_coords or not g_coords:
                self._marker_items.append(group)
                continue

            mcx, mcy = m_coords[0]
            gcx, gcy = g_coords[0]

            # Green cross at machine position
            items = self._draw_cross(mcx, mcy, CROSS_ARM, COLOR_MACHINE, 1)
            group.extend(items)

            # Red cross at gcode position
            items = self._draw_cross(gcx, gcy, CROSS_ARM, COLOR_GCODE, 1)
            group.extend(items)

            # Blue dashed line connecting pair
            pen = QPen(COLOR_LINK)
            pen.setWidthF(1)
            pen.setStyle(Qt.PenStyle.DashLine)
            line = QGraphicsLineItem(mcx, mcy, gcx, gcy)
            line.setPen(pen)
            line.setZValue(3)
            self._scene.addItem(line)
            group.append(line)

            # Error circle at gcode position
            if orient.errors and i < len(orient.errors):
                err = orient.errors[i]
                if err > 0.001:
                    r = err * zoom
                    pen_err = QPen(COLOR_GCODE)
                    pen_err.setWidthF(0.5)
                    circle = QGraphicsEllipseItem(
                        gcx - r, gcy - r, 2 * r, 2 * r)
                    circle.setPen(pen_err)
                    circle.setZValue(3)
                    self._scene.addItem(circle)
                    group.append(circle)

            self._marker_items.append(group)
            self._items.extend(group)

        # Re-highlight if a marker was selected
        if self._selected >= 0:
            self.highlight(self._selected)

    def clear(self):
        """Remove all orient overlay items from the scene."""
        for item in self._items:
            try:
                self._scene.removeItem(item)
            except RuntimeError:
                pass  # item already deleted by scene.clear()
        self._items.clear()
        self._marker_items.clear()

    def highlight(self, index):
        """Highlight a specific marker (thicker pen), dim others.

        Args:
            index: Marker index to highlight, or -1 to clear.
        """
        self._selected = index
        for i, group in enumerate(self._marker_items):
            width = 2.0 if i == index else 1.0
            for item in group:
                pen = QPen(item.pen())
                pen.setWidthF(width)
                item.setPen(pen)

    def _draw_cross(self, cx, cy, arm, color, width):
        """Draw a cross (+ shape) at the given scene coordinates.

        Returns:
            List of 2 QGraphicsLineItem.
        """
        pen = QPen(color)
        pen.setWidthF(width)

        h_line = QGraphicsLineItem(cx - arm, cy, cx + arm, cy)
        h_line.setPen(pen)
        h_line.setZValue(3)
        self._scene.addItem(h_line)

        v_line = QGraphicsLineItem(cx, cy - arm, cx, cy + arm)
        v_line.setPen(pen)
        v_line.setZValue(3)
        self._scene.addItem(v_line)

        return [h_line, v_line]
