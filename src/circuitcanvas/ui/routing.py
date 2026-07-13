"""Qt-independent geometry for horizontal, vertical, and 45-degree wires."""

from __future__ import annotations

import math

type Point = tuple[float, float]

TOLERANCE = 1e-6


def is_octilinear(start: Point, end: Point, tolerance: float = TOLERANCE) -> bool:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return abs(dx) <= tolerance or abs(dy) <= tolerance or abs(abs(dx) - abs(dy)) <= tolerance


def project_to_octilinear(origin: Point, point: Point) -> Point:
    """Project a point onto the closest permitted infinite axis through origin."""
    dx = point[0] - origin[0]
    dy = point[1] - origin[1]
    rising = (dx + dy) / 2.0
    falling = (dx - dy) / 2.0
    candidates = (
        (point[0], origin[1]),
        (origin[0], point[1]),
        (origin[0] + rising, origin[1] + rising),
        (origin[0] + falling, origin[1] - falling),
    )
    return min(
        candidates,
        key=lambda candidate: (candidate[0] - point[0]) ** 2 + (candidate[1] - point[1]) ** 2,
    )


def octilinear_route(start: Point, end: Point) -> tuple[Point, ...]:
    """Return a deterministic zero- or one-bend permitted route."""
    if is_octilinear(start, end):
        return ()
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    diagonal = min(abs(dx), abs(dy))
    bend = (
        start[0] + math.copysign(diagonal, dx),
        start[1] + math.copysign(diagonal, dy),
    )
    return (bend,)


def _project_to_segment(point: Point, start: Point, end: Point) -> Point:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= TOLERANCE**2:
        return start
    fraction = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    fraction = max(0.0, min(1.0, fraction))
    return (start[0] + fraction * dx, start[1] + fraction * dy)


def project_to_polyline(point: Point, polyline: tuple[Point, ...]) -> Point:
    """Return the closest clamped projection onto any segment of a polyline."""
    if not polyline:
        raise ValueError("Polyline must contain at least one point")
    if len(polyline) == 1:
        return polyline[0]
    candidates = [
        _project_to_segment(point, start, end)
        for start, end in zip(polyline, polyline[1:], strict=False)
    ]
    return min(
        candidates,
        key=lambda candidate: (candidate[0] - point[0]) ** 2 + (candidate[1] - point[1]) ** 2,
    )


def split_polyline(
    polyline: tuple[Point, ...], point: Point
) -> tuple[tuple[Point, ...], tuple[Point, ...]]:
    """Project point onto a polyline and return both ordered sides of the split."""
    if len(polyline) < 2:
        raise ValueError("Polyline must contain at least two points")
    candidates = [
        (index, _project_to_segment(point, start, end))
        for index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False))
    ]
    segment_index, projected = min(
        candidates,
        key=lambda candidate: (candidate[1][0] - point[0]) ** 2 + (candidate[1][1] - point[1]) ** 2,
    )
    left = list(polyline[: segment_index + 1])
    right = list(polyline[segment_index + 1 :])
    if math.dist(left[-1], projected) <= TOLERANCE:
        projected = left[-1]
    elif math.dist(projected, right[0]) <= TOLERANCE:
        projected = right[0]
    if left[-1] != projected:
        left.append(projected)
    if right[0] != projected:
        right.insert(0, projected)
    return tuple(left), tuple(right)


def normalized_octilinear_polyline(points: tuple[Point, ...]) -> tuple[Point, ...]:
    """Remove zero-length segments and repair every forbidden-angle segment."""
    if not points:
        return ()
    normalized = [points[0]]
    for target in points[1:]:
        current = normalized[-1]
        if math.dist(current, target) <= TOLERANCE:
            continue
        for bend in octilinear_route(current, target):
            if math.dist(normalized[-1], bend) > TOLERANCE:
                normalized.append(bend)
        if math.dist(normalized[-1], target) > TOLERANCE:
            normalized.append(target)
    return tuple(normalized)
