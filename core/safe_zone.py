"""
safe_zone.py
Safe-zone comparison logic for the Pavlik-harness monitoring prototype.

Purpose:
Given a hip's current flexion/abduction angles and a patient-specific
safe-zone definition, determine whether the hip is inside the allowed
region, and if not, how far outside it is.

Two zone models are provided:
    1. Rectangular zone - simple min/max box (flexion_min/max, abduction_min/max)
    2. Polygon zone - a 2D permitted region (X = flexion, Y = abduction)

Both models return the same output shape so callers (alert_engine.py) don't
need to know which zone type was used.

This function runs independently for each hip - callers should invoke it
once for the left hip and once for the right hip using that hip's own
angles and that hip's own profile limits.

LIMITATION:
Zone boundaries are simulated demonstration values from the patient profile,
not real clinical safe-zone data. This is a software prototype only.
"""

import math


def is_inside_rectangular_zone(flexion, abduction,
                                flexion_min, flexion_max,
                                abduction_min, abduction_max):
    """
    Check whether a (flexion, abduction) point falls inside a simple
    rectangular safe zone.

    Parameters
    ----------
    flexion : float
        Current flexion angle in degrees.
    abduction : float
        Current abduction angle in degrees.
    flexion_min, flexion_max : float
        Allowed flexion range in degrees.
    abduction_min, abduction_max : float
        Allowed abduction range in degrees.

    Returns
    -------
    dict
        {
            "inside": bool,
            "deviation_deg": float,     # 0 if inside; otherwise how far
                                         # outside on the worst axis
            "boundary_distance": float  # straight-line distance in degrees
                                         # to the nearest edge of the box
                                         # (negative if outside, positive if
                                         # inside - i.e. "room to spare")
        }
    """
    inside = (flexion_min <= flexion <= flexion_max and
              abduction_min <= abduction <= abduction_max)

    # How far outside on each axis (0 if within range on that axis)
    flexion_excess = max(flexion_min - flexion, flexion - flexion_max, 0.0)
    abduction_excess = max(abduction_min - abduction, abduction - abduction_max, 0.0)

    if inside:
        deviation_deg = 0.0
        # Distance to nearest edge (how much room to spare), smallest margin wins
        margin_flexion = min(flexion - flexion_min, flexion_max - flexion)
        margin_abduction = min(abduction - abduction_min, abduction_max - abduction)
        boundary_distance = min(margin_flexion, margin_abduction)
    else:
        # Deviation = straight-line distance outside the box, in degrees
        deviation_deg = math.sqrt(flexion_excess ** 2 + abduction_excess ** 2)
        boundary_distance = -deviation_deg

    return {
        "inside": inside,
        "deviation_deg": float(deviation_deg),
        "boundary_distance": float(boundary_distance),
    }


def is_inside_polygon_zone(flexion, abduction, polygon_points):
    """
    Check whether a (flexion, abduction) point falls inside a 2D polygon
    safe zone, where X = flexion and Y = abduction.

    Parameters
    ----------
    flexion : float
        Current flexion angle in degrees (X axis).
    abduction : float
        Current abduction angle in degrees (Y axis).
    polygon_points : list[tuple[float, float]]
        Ordered list of (flexion, abduction) vertices defining the
        permitted region. Must have at least 3 points.

    Returns
    -------
    dict
        {
            "inside": bool,
            "deviation_deg": float,     # 0 if inside; otherwise distance
                                         # to the nearest polygon edge
            "boundary_distance": float  # signed distance to nearest edge
                                         # (negative outside, positive inside)
        }
    """
    if len(polygon_points) < 3:
        raise ValueError("Polygon zone requires at least 3 points.")

    point = (flexion, abduction)
    inside = _point_in_polygon(point, polygon_points)
    distance_to_edge = _distance_to_polygon_boundary(point, polygon_points)

    if inside:
        deviation_deg = 0.0
        boundary_distance = distance_to_edge
    else:
        deviation_deg = distance_to_edge
        boundary_distance = -distance_to_edge

    return {
        "inside": inside,
        "deviation_deg": float(deviation_deg),
        "boundary_distance": float(boundary_distance),
    }


def _point_in_polygon(point, polygon_points):
    """
    Ray-casting algorithm to determine if a point lies inside a polygon.
    """
    x, y = point
    n = len(polygon_points)
    inside = False

    x1, y1 = polygon_points[0]
    for i in range(1, n + 1):
        x2, y2 = polygon_points[i % n]
        if y > min(y1, y2):
            if y <= max(y1, y2):
                if x <= max(x1, x2):
                    if y1 != y2:
                        x_intersect = (y - y1) * (x2 - x1) / (y2 - y1) + x1
                    if x1 == x2 or x <= x_intersect:
                        inside = not inside
        x1, y1 = x2, y2

    return inside


def _distance_point_to_segment(point, seg_start, seg_end):
    """Shortest distance from a point to a line segment."""
    px, py = point
    ax, ay = seg_start
    bx, by = seg_end

    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def _distance_to_polygon_boundary(point, polygon_points):
    """Shortest distance from a point to any edge of the polygon."""
    n = len(polygon_points)
    min_distance = float("inf")
    for i in range(n):
        seg_start = polygon_points[i]
        seg_end = polygon_points[(i + 1) % n]
        distance = _distance_point_to_segment(point, seg_start, seg_end)
        min_distance = min(min_distance, distance)
    return min_distance


def check_hip_safe_zone(flexion, abduction, hip_profile, zone_type="rectangular"):
    """
    Convenience wrapper: checks a single hip's angles against its profile
    limits, choosing rectangular or polygon zone logic.

    Parameters
    ----------
    flexion : float
    abduction : float
    hip_profile : dict
        Either:
        - Rectangular: {"flexion_min", "flexion_max", "abduction_min", "abduction_max"}
        - Polygon:     {"polygon_points": [(flexion, abduction), ...]}
    zone_type : str
        "rectangular" or "polygon"

    Returns
    -------
    dict
        Same shape as is_inside_rectangular_zone / is_inside_polygon_zone.
    """
    if zone_type == "rectangular":
        return is_inside_rectangular_zone(
            flexion, abduction,
            hip_profile["flexion_min"], hip_profile["flexion_max"],
            hip_profile["abduction_min"], hip_profile["abduction_max"],
        )
    elif zone_type == "polygon":
        return is_inside_polygon_zone(
            flexion, abduction, hip_profile["polygon_points"]
        )
    else:
        raise ValueError(f"Unknown zone_type: {zone_type}")
