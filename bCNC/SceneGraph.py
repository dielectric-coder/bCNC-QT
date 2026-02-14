# SceneGraph - Toolkit-independent drawing primitive representation
#
# Defines an intermediate representation of visual elements that
# CNCCanvas builds during draw(). A renderer then consumes these
# primitives to produce actual screen output.
#
# This allows the same drawing logic to target Tkinter Canvas,
# Qt QGraphicsScene, or any other rendering backend.
#
# Usage flow:
#   1. CNCCanvas builds a Scene by adding primitives
#   2. A Renderer takes the Scene and creates toolkit-specific items
#   3. On redraw, the scene is rebuilt and re-rendered


class LinePrimitive:
    """A polyline or line segment."""

    __slots__ = ("coords", "fill", "width", "dash", "arrow",
                 "cap", "tag", "item_id", "metadata")

    def __init__(self, coords, fill="black", width=1, dash=None,
                 arrow=None, cap=None, tag=None, metadata=None):
        """
        Args:
            coords: List of (x, y) canvas-space coordinate pairs.
            fill: Line color string.
            width: Line width in pixels.
            dash: Dash pattern tuple, e.g. (3, 1) or None for solid.
            arrow: Arrow style ("last", "first", "both", or None).
            cap: Line cap style ("projecting", "round", etc.).
            tag: String tag for grouping (e.g. "Axes", "Grid").
            metadata: Optional dict for renderer-specific data.
        """
        self.coords = coords
        self.fill = fill
        self.width = width
        self.dash = dash
        self.arrow = arrow
        self.cap = cap
        self.tag = tag
        self.item_id = None
        self.metadata = metadata


class OvalPrimitive:
    """An oval/ellipse/circle."""

    __slots__ = ("x1", "y1", "x2", "y2", "outline", "fill",
                 "width", "tag", "item_id")

    def __init__(self, x1, y1, x2, y2, outline="black", fill="",
                 width=1, tag=None):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.outline = outline
        self.fill = fill
        self.width = width
        self.tag = tag
        self.item_id = None


class PolygonPrimitive:
    """A filled polygon."""

    __slots__ = ("coords", "fill", "outline", "width", "tag", "item_id")

    def __init__(self, coords, fill="", outline="black", width=1, tag=None):
        self.coords = coords
        self.fill = fill
        self.outline = outline
        self.width = width
        self.tag = tag
        self.item_id = None


class TextPrimitive:
    """A text label at a position."""

    __slots__ = ("x", "y", "text", "fill", "anchor", "font",
                 "tag", "item_id")

    def __init__(self, x, y, text, fill="black", anchor="center",
                 font=None, tag=None):
        self.x = x
        self.y = y
        self.text = text
        self.fill = fill
        self.anchor = anchor
        self.font = font
        self.tag = tag
        self.item_id = None


class ImagePrimitive:
    """An image placed at a position."""

    __slots__ = ("x", "y", "image_data", "anchor", "tag", "item_id")

    def __init__(self, x, y, image_data, anchor="center", tag=None):
        self.x = x
        self.y = y
        self.image_data = image_data
        self.anchor = anchor
        self.tag = tag
        self.item_id = None


class SceneLayer:
    """A named layer of drawing primitives with z-ordering.

    Layers are drawn back-to-front by z_order value.
    """

    __slots__ = ("name", "z_order", "visible", "primitives")

    def __init__(self, name, z_order=0, visible=True):
        self.name = name
        self.z_order = z_order
        self.visible = visible
        self.primitives = []

    def add(self, primitive):
        self.primitives.append(primitive)
        return primitive

    def clear(self):
        self.primitives.clear()


class Scene:
    """Collection of layers forming a complete drawing.

    The Scene acts as a builder. Drawing code adds primitives
    to named layers, and a renderer later walks all layers
    (sorted by z_order) to produce output.
    """

    def __init__(self):
        self._layers = {}
        self._order = []

    def layer(self, name, z_order=0):
        """Get or create a named layer.

        Args:
            name: Layer identifier (e.g. "grid", "paths", "axes").
            z_order: Draw order (lower = further back).

        Returns:
            SceneLayer instance.
        """
        if name not in self._layers:
            lyr = SceneLayer(name, z_order)
            self._layers[name] = lyr
            self._order = sorted(
                self._layers.values(), key=lambda l: l.z_order)
        return self._layers[name]

    def clear(self, layer_name=None):
        """Clear all primitives, or just one layer.

        Args:
            layer_name: If given, clear only that layer.
                        If None, clear everything.
        """
        if layer_name is None:
            for lyr in self._layers.values():
                lyr.clear()
        elif layer_name in self._layers:
            self._layers[layer_name].clear()

    def layers_ordered(self):
        """Return layers sorted by z_order (back to front).

        Returns:
            List of SceneLayer instances.
        """
        return self._order

    def all_primitives(self):
        """Iterate over all primitives across all visible layers.

        Yields:
            Drawing primitives in z_order.
        """
        for lyr in self._order:
            if lyr.visible:
                yield from lyr.primitives


