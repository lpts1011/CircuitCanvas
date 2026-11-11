"""Where terminals sit on the canvas (no Qt dependency).

The canvas draws the battery at a fixed place and every component as a card
whose two terminals are ``COMPONENT_HALF_LENGTH`` either side of its centre.
Edits that reshape wires (closing a gap, making room) need the same numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .wiring import EndpointRef, JunctionRef, Point, TerminalRef

if TYPE_CHECKING:
    from .circuit import Circuit

BATTERY_POSITION: Point = (110.0, 360.0)
BATTERY_HALF_LENGTH = 70.0
COMPONENT_HALF_LENGTH = 84.0

#: Unit vector from a component's centre to its "b" terminal, by rotation.
_B_DIRECTION: dict[int, Point] = {
    0: (1.0, 0.0),
    90: (0.0, 1.0),
    180: (-1.0, 0.0),
    270: (0.0, -1.0),
}


def component_rotation(circuit: Circuit, component_id: str) -> int:
    component = circuit.components[component_id]
    return circuit.rotations.get(component_id, component.rotation) % 360


def terminal_offset(rotation: int, terminal: str) -> Point:
    """Offset of terminal "a" or "b" from the centre of a component."""
    dx, dy = _B_DIRECTION.get(rotation % 360, _B_DIRECTION[0])
    sign = 1.0 if terminal == "b" else -1.0
    return (sign * dx * COMPONENT_HALF_LENGTH, sign * dy * COMPONENT_HALF_LENGTH)


def terminal_position(circuit: Circuit, ref: TerminalRef) -> Point:
    if ref.owner_id == circuit.source.id:
        sign = 1.0 if ref.terminal == "b" else -1.0
        return (BATTERY_POSITION[0], BATTERY_POSITION[1] + sign * BATTERY_HALF_LENGTH)
    x, y = circuit.positions.get(ref.owner_id, (0.0, 0.0))
    dx, dy = terminal_offset(component_rotation(circuit, ref.owner_id), ref.terminal)
    return (x + dx, y + dy)


def endpoint_position(circuit: Circuit, ref: EndpointRef) -> Point:
    if isinstance(ref, JunctionRef):
        return circuit.junctions[ref.junction_id].position
    return terminal_position(circuit, ref)


def simplify_polyline(points: tuple[Point, ...], tolerance: float = 1e-6) -> tuple[Point, ...]:
    """Drop repeated points and points that lie on a straight run between their neighbours."""
    distinct: list[Point] = []
    for point in points:
        if not distinct or abs(point[0] - distinct[-1][0]) + abs(point[1] - distinct[-1][1]) > (
            tolerance
        ):
            distinct.append(point)
    if len(distinct) < 3:
        return tuple(distinct)
    kept = [distinct[0]]
    for index in range(1, len(distinct) - 1):
        before, here, after = kept[-1], distinct[index], distinct[index + 1]
        ax, ay = here[0] - before[0], here[1] - before[1]
        bx, by = after[0] - here[0], after[1] - here[1]
        straight_on = abs(ax * by - ay * bx) <= tolerance and (ax * bx + ay * by) > 0
        if not straight_on:
            kept.append(here)
    kept.append(distinct[-1])
    return tuple(kept)
