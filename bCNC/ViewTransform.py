# ViewTransform - Toolkit-independent coordinate transformation math
#
# Extracted from CNCCanvas.py. Provides pure-math functions for
# converting between 3D world coordinates and 2D canvas coordinates
# across all supported view projections (XY, XZ, YZ, ISO1-3).
#
# Zero Tkinter dependencies. Can be used by any rendering backend.

import math

# View constants
VIEW_XY = 0
VIEW_XZ = 1
VIEW_YZ = 2
VIEW_ISO1 = 3
VIEW_ISO2 = 4
VIEW_ISO3 = 5
VIEWS = ["X-Y", "X-Z", "Y-Z", "ISO1", "ISO2", "ISO3"]

# Precomputed trigonometric constants for isometric projections
S60 = math.sin(math.radians(60))
C60 = math.cos(math.radians(60))

# Coordinate clipping boundary
MAXDIST = 10000


def project_3d_to_2d(xyz, view, zoom):
    """Project a list of 3D world points to 2D canvas coordinates.

    This is the core transformation: world (x, y, z) -> screen (cx, cy).
    Note: the Y-axis is flipped (negated) for screen coordinates.

    Args:
        xyz: List of (x, y, z) tuples in world space.
        view: View mode (VIEW_XY, VIEW_XZ, etc.).
        zoom: Current zoom factor.

    Returns:
        List of (cx, cy) tuples in canvas space.
    """
    if view == VIEW_XY:
        coords = [(p[0] * zoom, -p[1] * zoom) for p in xyz]
    elif view == VIEW_XZ:
        coords = [(p[0] * zoom, -p[2] * zoom) for p in xyz]
    elif view == VIEW_YZ:
        coords = [(p[1] * zoom, -p[2] * zoom) for p in xyz]
    elif view == VIEW_ISO1:
        coords = [
            (
                (p[0] * S60 + p[1] * S60) * zoom,
                (+p[0] * C60 - p[1] * C60 - p[2]) * zoom,
            )
            for p in xyz
        ]
    elif view == VIEW_ISO2:
        coords = [
            (
                (p[0] * S60 - p[1] * S60) * zoom,
                (-p[0] * C60 - p[1] * C60 - p[2]) * zoom,
            )
            for p in xyz
        ]
    elif view == VIEW_ISO3:
        coords = [
            (
                (-p[0] * S60 - p[1] * S60) * zoom,
                (-p[0] * C60 + p[1] * C60 - p[2]) * zoom,
            )
            for p in xyz
        ]
    else:
        coords = [(p[0] * zoom, -p[1] * zoom) for p in xyz]

    # Clamp to prevent excessively large coordinates
    return _clamp_coords(coords)


def unproject_2d_to_3d(cx, cy, view, zoom):
    """Convert 2D canvas coordinates back to 3D world coordinates.

    Inverse of project_3d_to_2d. For orthogonal views, the
    axis perpendicular to the view plane is set to 0. For
    isometric views, Z is set to 0.

    Args:
        cx: Canvas x coordinate.
        cy: Canvas y coordinate.
        view: View mode.
        zoom: Current zoom factor.

    Returns:
        Tuple (x, y, z) in world space.
    """
    if view == VIEW_XY:
        x = cx / zoom
        y = -cy / zoom
        z = 0.0

    elif view == VIEW_XZ:
        x = cx / zoom
        y = 0.0
        z = -cy / zoom

    elif view == VIEW_YZ:
        x = 0.0
        y = cx / zoom
        z = -cy / zoom

    elif view == VIEW_ISO1:
        x = (cx / S60 + cy / C60) / zoom / 2
        y = (cx / S60 - cy / C60) / zoom / 2
        z = 0.0

    elif view == VIEW_ISO2:
        x = (cx / S60 - cy / C60) / zoom / 2
        y = -(cx / S60 + cy / C60) / zoom / 2
        z = 0.0

    elif view == VIEW_ISO3:
        x = -(cx / S60 + cy / C60) / zoom / 2
        y = -(cx / S60 - cy / C60) / zoom / 2
        z = 0.0

    else:
        x = cx / zoom
        y = -cy / zoom
        z = 0.0

    return x, y, z


def canvas_to_machine(cx, cy, view, zoom):
    """Convert canvas coordinates to machine coordinates.

    Similar to unproject_2d_to_3d but returns None for axes
    not visible in the current view. Used for gantry movement
    and work position setting.

    Args:
        cx: Canvas x coordinate (after canvasx/canvasy offset).
        cy: Canvas y coordinate.
        view: View mode.
        zoom: Current zoom factor.

    Returns:
        Tuple (u, v, w) where None indicates an axis not
        addressable in this view.
    """
    u = cx / zoom
    v = cy / zoom

    if view == VIEW_XY:
        return u, -v, None

    elif view == VIEW_XZ:
        return u, None, -v

    elif view == VIEW_YZ:
        return None, u, -v

    elif view == VIEW_ISO1:
        return (
            0.5 * (u / S60 + v / C60),
            0.5 * (u / S60 - v / C60),
            None,
        )

    elif view == VIEW_ISO2:
        return (
            0.5 * (u / S60 - v / C60),
            -0.5 * (u / S60 + v / C60),
            None,
        )

    elif view == VIEW_ISO3:
        return (
            -0.5 * (u / S60 + v / C60),
            -0.5 * (u / S60 - v / C60),
            None,
        )

    return u, -v, None


def compute_zoom_transform(old_zoom, zoom_factor, pin_x, pin_y,
                           canvas_origin_x, canvas_origin_y):
    """Compute the pan offset needed after zooming to keep a
    screen point stationary (pin zoom).

    Args:
        old_zoom: Previous zoom level.
        zoom_factor: Multiplicative zoom factor (e.g. 1.25 to zoom in).
        pin_x: Screen x coordinate to keep stationary.
        pin_y: Screen y coordinate to keep stationary.
        canvas_origin_x: Current canvas origin x (canvasx(0)).
        canvas_origin_y: Current canvas origin y (canvasy(0)).

    Returns:
        Tuple (new_zoom, dx, dy) where dx, dy are the scan_dragto
        offsets needed to maintain the pin point.
    """
    new_zoom = old_zoom * zoom_factor

    dx = pin_x * (1.0 - zoom_factor)
    dy = pin_y * (1.0 - zoom_factor)

    return new_zoom, int(round(dx)), int(round(dy))


def compute_fit_zoom(bbox_width, bbox_height,
                     viewport_width, viewport_height):
    """Compute the zoom factor to fit a bounding box in the viewport.

    Args:
        bbox_width: Width of the content bounding box.
        bbox_height: Height of the content bounding box.
        viewport_width: Width of the viewport.
        viewport_height: Height of the viewport.

    Returns:
        float: The zoom factor, or None if bbox is degenerate.
    """
    # Add margin for readability
    bbox_width *= 1.05
    bbox_height *= 1.05

    if bbox_width <= 0 or bbox_height <= 0:
        return None

    try:
        zx = round(float(viewport_width / bbox_width), 2)
    except Exception:
        return None

    try:
        zy = round(float(viewport_height / bbox_height), 2)
    except Exception:
        return None

    if zx > 0.98:
        return min(zx, zy)
    else:
        return max(zx, zy)


def compute_axis_scale(axis_min, axis_max, is_inch=False):
    """Compute a nice scale length for drawing axes.

    Args:
        axis_min: Minimum visible coordinate on any axis.
        axis_max: Maximum visible coordinate on any axis.
        is_inch: True if working in inches.

    Returns:
        float: Scale length for axis arrows.
    """
    d = axis_max - axis_min
    try:
        return math.pow(10.0, int(math.log10(d)))
    except Exception:
        return 10.0 if is_inch else 100.0


def _clamp_coords(coords):
    """Clamp coordinates to prevent excessively large values."""
    result = []
    for x, y in coords:
        if abs(x) > MAXDIST or abs(y) > MAXDIST:
            x = max(-MAXDIST, min(MAXDIST, x))
            y = max(-MAXDIST, min(MAXDIST, y))
        result.append((x, y))
    return result
