# PathGeometry - Toolkit-independent geometry generation
#
# Extracted from CNCCanvas.py. Generates geometric primitives
# (coordinate lists) for grid lines, margins, axes, workarea,
# and other visual elements. All functions return raw 3D
# coordinates that can be projected by ViewTransform.
#
# Zero Tkinter dependencies. Zero CNC.vars direct access.

import math


def generate_grid_lines(axis_xmin, axis_xmax, axis_ymin, axis_ymax,
                        spacing=10.0):
    """Generate grid line coordinates.

    Args:
        axis_xmin: Left boundary of the all-blocks margin.
        axis_xmax: Right boundary.
        axis_ymin: Bottom boundary.
        axis_ymax: Top boundary.
        spacing: Grid spacing (default 10 units).

    Returns:
        List of line segments, each as [(x1,y1,z), (x2,y2,z)].
    """
    lines = []
    xmin = (axis_xmin // spacing) * spacing
    xmax = (axis_xmax // spacing + 1) * spacing
    ymin = (axis_ymin // spacing) * spacing
    ymax = (axis_ymax // spacing + 1) * spacing

    # Horizontal lines
    i = int(axis_ymin // spacing)
    end = int(axis_ymax // spacing) + 2
    while i < end:
        y = i * spacing
        lines.append([(xmin, y, 0.0), (xmax, y, 0.0)])
        i += 1

    # Vertical lines
    i = int(axis_xmin // spacing)
    end = int(axis_xmax // spacing) + 2
    while i < end:
        x = i * spacing
        lines.append([(x, ymin, 0.0), (x, ymax, 0.0)])
        i += 1

    return lines


def generate_margin_rect(xmin, ymin, xmax, ymax):
    """Generate a closed rectangle path for a margin boundary.

    Args:
        xmin, ymin, xmax, ymax: Boundary coordinates.

    Returns:
        List of 5 xyz tuples forming a closed rectangle,
        or None if coordinates are invalid.
    """
    return [
        (xmin, ymin, 0.0),
        (xmax, ymin, 0.0),
        (xmax, ymax, 0.0),
        (xmin, ymax, 0.0),
        (xmin, ymin, 0.0),
    ]


def generate_workarea_rect(work_offset_x, work_offset_y,
                           travel_x, travel_y):
    """Generate the workarea rectangle.

    The workarea extends from the work offset back by the
    machine travel distances.

    Args:
        work_offset_x: Work-to-machine X offset (wx - mx).
        work_offset_y: Work-to-machine Y offset (wy - my).
        travel_x: Machine X travel distance.
        travel_y: Machine Y travel distance.

    Returns:
        List of 5 xyz tuples forming a closed rectangle.
    """
    xmin = work_offset_x - travel_x
    ymin = work_offset_y - travel_y
    xmax = work_offset_x
    ymax = work_offset_y
    return generate_margin_rect(xmin, ymin, xmax, ymax)


def generate_axes(scale):
    """Generate coordinate axis arrow endpoints.

    Args:
        scale: Length of each axis arrow.

    Returns:
        Dict with keys "x", "y", "z", each mapping to a list
        of two xyz tuples (origin to arrow tip).
    """
    origin = (0.0, 0.0, 0.0)
    return {
        "x": [origin, (scale, 0.0, 0.0)],
        "y": [origin, (0.0, scale, 0.0)],
        "z": [origin, (0.0, 0.0, scale)],
    }


def generate_orient_crosshair(x, y, size):
    """Generate a crosshair marker at a given position.

    Args:
        x, y: Center position.
        size: Half-size of the crosshair arms.

    Returns:
        List of two line segments:
        [[(x-size,y,0), (x+size,y,0)], [(x,y-size,0), (x,y+size,0)]]
    """
    return [
        [(x - size, y, 0.0), (x + size, y, 0.0)],
        [(x, y - size, 0.0), (x, y + size, 0.0)],
    ]


def path_segments_to_xyz(path, z=0.0):
    """Convert a bpath.Path (list of Segments) to xyz coordinate pairs.

    Each segment produces two xyz points (A and B endpoints).

    Args:
        path: A bpath.Path or list of Segment objects with .A and .B.
        z: Z coordinate for all points.

    Returns:
        List of (x, y, z) tuples.
    """
    xyz = []
    for segment in path:
        xyz.append((segment.A[0], segment.A[1], z))
        xyz.append((segment.B[0], segment.B[1], z))
    return xyz


def rect_to_xyz(xmin, ymin, xmax, ymax, z=0.0):
    """Convert rectangle bounds to a closed xyz path.

    Same as generate_margin_rect but with explicit z.

    Args:
        xmin, ymin, xmax, ymax: Rectangle bounds.
        z: Z coordinate.

    Returns:
        List of 5 (x, y, z) tuples.
    """
    return [
        (xmin, ymin, z),
        (xmax, ymin, z),
        (xmax, ymax, z),
        (xmin, ymax, z),
        (xmin, ymin, z),
    ]


def compute_gantry_geometry(diameter, zoom, view_type):
    """Compute gantry marker dimensions.

    Args:
        diameter: Tool diameter.
        zoom: Current zoom factor.
        view_type: Current view (VIEW_XY, etc.).

    Returns:
        Dict with gantry geometry parameters:
        {
            "radius": int,      # gantry circle radius in pixels
            "gx": int,          # half-width
            "gy": int,          # half-height of oval
            "gh": int,          # height offset for side views
            "is_top_view": bool # True for XY view
        }
    """
    from ViewTransform import VIEW_XY
    gr = max(3, int(diameter / 2.0 * zoom))
    return {
        "radius": gr,
        "gx": gr,
        "gy": gr // 2,
        "gh": 3 * gr,
        "is_top_view": (view_type == VIEW_XY),
    }
