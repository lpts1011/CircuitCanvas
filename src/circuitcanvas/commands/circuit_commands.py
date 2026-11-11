"""Repeatable series/parallel edits with snapshot-based undo and redo."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable
from copy import deepcopy
from dataclasses import dataclass, replace

from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import (
    Component,
    ComponentKind,
    VoltageSource,
    make_component,
    replace_value,
)
from circuitcanvas.domain.layout import endpoint_position, simplify_polyline, terminal_position
from circuitcanvas.domain.netlist import derive_connectivity
from circuitcanvas.domain.wiring import EndpointRef, Junction, JunctionRef, Point, TerminalRef, Wire

_PREFIX = {
    ComponentKind.RESISTOR: "R",
    ComponentKind.CAPACITOR: "C",
    ComponentKind.INDUCTOR: "L",
}


def _kind(kind: ComponentKind | str) -> ComponentKind:
    return kind if isinstance(kind, ComponentKind) else ComponentKind(kind)


def insert_series(
    circuit: Circuit,
    target_edge: str | None,
    kind: ComponentKind | str,
    value: float,
) -> str:
    """Insert a new component across the opening or after an existing component."""
    component_kind = _kind(kind)
    component_id = circuit.next_id(_PREFIX[component_kind])
    if target_edge == circuit.open_edge and circuit.open_edge is not None:
        node_a, node_b = circuit.entry_nodes
        circuit.open_edge = None
    elif target_edge is not None and target_edge in circuit.components:
        target = circuit.components[target_edge]
        old_b = target.node_b
        new_node = circuit.next_node_id()
        circuit.replace_component(target.with_endpoints(target.node_a, new_node))
        node_a, node_b = new_node, old_b
    else:
        raise ValueError("Series insertion target is no longer available")

    circuit.add_component(make_component(component_kind, component_id, node_a, node_b, value))
    return component_id


def add_parallel(
    circuit: Circuit,
    target_component_id: str,
    kind: ComponentKind | str,
    value: float,
) -> str:
    """Place a new component between the same endpoint nodes as the target."""
    try:
        target = circuit.components[target_component_id]
    except KeyError:
        raise KeyError(target_component_id) from None
    component_kind = _kind(kind)
    component_id = circuit.next_id(_PREFIX[component_kind])
    circuit.add_component(
        make_component(component_kind, component_id, target.node_a, target.node_b, value)
    )
    return component_id


def update_component_value(circuit: Circuit, component_id: str, value: float) -> None:
    try:
        component = circuit.components[component_id]
    except KeyError:
        raise KeyError(component_id) from None
    circuit.replace_component(replace_value(component, value))


def _wires_at(circuit: Circuit, ref: EndpointRef) -> list[Wire]:
    return [wire for wire in circuit.wires.values() if ref in (wire.start, wire.end)]


def _other_end(wire: Wire, ref: EndpointRef) -> EndpointRef:
    return wire.end if wire.start == ref else wire.start


def _route_from(wire: Wire, ref: EndpointRef) -> tuple[Point, ...]:
    """The wire's bends in order, walking away from ``ref``."""
    return wire.route if wire.start == ref else tuple(reversed(wire.route))


def _is_in_series(circuit: Circuit, component_id: str) -> bool:
    """True when closing the gap left by this component cannot short anything out.

    A component is in series with its neighbour when one of its ends meets exactly
    one other terminal. Joining the wires on either side then keeps the circuit the
    same apart from the missing component. Otherwise (a parallel branch, or a
    component bypassed by a wire) the two ends must stay apart.
    """
    connectivity = derive_connectivity(circuit)
    node_a = connectivity.node_for(TerminalRef(component_id, "a"))
    node_b = connectivity.node_for(TerminalRef(component_id, "b"))
    if node_a == node_b:
        return False
    for other_id in circuit.components:
        if other_id == component_id:
            continue
        ends = {
            connectivity.node_for(TerminalRef(other_id, "a")),
            connectivity.node_for(TerminalRef(other_id, "b")),
        }
        if ends == {node_a, node_b}:
            return False  # A parallel partner: joining the ends would short it.
    terminals_per_node: dict[str, int] = defaultdict(int)
    for node in connectivity.terminal_nodes.values():
        terminals_per_node[node] += 1
    return terminals_per_node[node_a] == 2 or terminals_per_node[node_b] == 2


def _remove_unused_junctions(circuit: Circuit, candidates: Iterable[EndpointRef]) -> None:
    for ref in candidates:
        if isinstance(ref, JunctionRef) and not _wires_at(circuit, ref):
            circuit.junctions.pop(ref.junction_id, None)


def _close_gap(circuit: Circuit, component_id: str) -> None:
    """Join the wires on both sides of a series component that is about to go."""
    ref_a = TerminalRef(component_id, "a")
    ref_b = TerminalRef(component_id, "b")
    position_a = terminal_position(circuit, ref_a)
    position_b = terminal_position(circuit, ref_b)
    wires_a = _wires_at(circuit, ref_a)
    wires_b = _wires_at(circuit, ref_b)

    if len(wires_a) == 1 and len(wires_b) == 1:
        wire_a, wire_b = wires_a[0], wires_b[0]
        far_a = _other_end(wire_a, ref_a)
        far_b = _other_end(wire_b, ref_b)
        del circuit.wires[wire_b.id]
        if far_a == far_b:
            del circuit.wires[wire_a.id]  # It would be a wire from a dot to itself.
            _remove_unused_junctions(circuit, (far_a,))
            return
        path = simplify_polyline(
            (
                endpoint_position(circuit, far_a),
                *reversed(_route_from(wire_a, ref_a)),
                position_a,
                position_b,
                *_route_from(wire_b, ref_b),
                endpoint_position(circuit, far_b),
            )
        )
        circuit.wires[wire_a.id] = Wire(wire_a.id, far_a, far_b, path[1:-1])
        return

    # Several wires meet at one of the ends: they now all meet at a junction there.
    keep_b = len(wires_b) >= len(wires_a)
    junction_id = circuit.next_junction_id()
    junction_position = position_b if keep_b else position_a
    circuit.junctions[junction_id] = Junction(junction_id, junction_position)
    junction = JunctionRef(junction_id)
    kept_ref, moved_ref = (ref_b, ref_a) if keep_b else (ref_a, ref_b)
    moved_position = position_a if keep_b else position_b
    for wire in _wires_at(circuit, kept_ref):
        circuit.wires[wire.id] = replace(
            wire,
            start=junction if wire.start == kept_ref else wire.start,
            end=junction if wire.end == kept_ref else wire.end,
        )
    for wire in _wires_at(circuit, moved_ref):
        far = _other_end(wire, moved_ref)
        path = simplify_polyline(
            (
                endpoint_position(circuit, far),
                *reversed(_route_from(wire, moved_ref)),
                moved_position,
                junction_position,
            )
        )
        circuit.wires[wire.id] = Wire(wire.id, far, junction, path[1:-1])


def _detach(circuit: Circuit, component_id: str) -> None:
    """Take a component out without joining its ends.

    A wire that only led to this component goes with it, so no wire is left ending
    in empty space. Where several wires met at a terminal, they keep meeting at a
    junction dot in the same place.
    """
    orphan_candidates: list[EndpointRef] = []
    for terminal in ("a", "b"):
        ref = TerminalRef(component_id, terminal)
        wires = _wires_at(circuit, ref)
        if len(wires) == 1:
            orphan_candidates.append(_other_end(wires[0], ref))
            del circuit.wires[wires[0].id]
        elif len(wires) > 1:
            junction_id = circuit.next_junction_id()
            circuit.junctions[junction_id] = Junction(junction_id, terminal_position(circuit, ref))
            junction = JunctionRef(junction_id)
            for wire in wires:
                circuit.wires[wire.id] = replace(
                    wire,
                    start=junction if wire.start == ref else wire.start,
                    end=junction if wire.end == ref else wire.end,
                )
    _remove_unused_junctions(circuit, orphan_candidates)


def delete_component(circuit: Circuit, component_id: str) -> Component:
    """Remove a component, leaving the rest of the circuit connected sensibly.

    A component in series is replaced by plain wire, so the loop stays closed. A
    parallel branch disappears together with its leads.
    """
    if component_id not in circuit.components:
        raise KeyError(component_id)
    ref_a = TerminalRef(component_id, "a")
    ref_b = TerminalRef(component_id, "b")
    wired_both_ends = bool(_wires_at(circuit, ref_a)) and bool(_wires_at(circuit, ref_b))
    if wired_both_ends and _is_in_series(circuit, component_id):
        _close_gap(circuit, component_id)
    else:
        _detach(circuit, component_id)
    return circuit.remove_component(component_id)


def dissolve_junction(circuit: Circuit, junction_id: str) -> bool:
    """Turn a dot where exactly two wires meet end to end into one continuous wire."""
    junction = JunctionRef(junction_id)
    wires = _wires_at(circuit, junction)
    if len(wires) != 2:
        return False
    first, second = wires
    far_first = _other_end(first, junction)
    far_second = _other_end(second, junction)
    if far_first == far_second or junction in (far_first, far_second):
        return False
    path = simplify_polyline(
        (
            endpoint_position(circuit, far_first),
            *reversed(_route_from(first, junction)),
            circuit.junctions[junction_id].position,
            *_route_from(second, junction),
            endpoint_position(circuit, far_second),
        )
    )
    del circuit.wires[second.id]
    circuit.wires[first.id] = Wire(first.id, far_first, far_second, path[1:-1])
    del circuit.junctions[junction_id]
    circuit.touch()
    return True


def shift_layout(circuit: Circuit, cut: float, distance: float) -> None:
    """Slide everything to the right of ``x = cut`` sideways to open up space.

    A negative ``distance`` slides everything to the left of the cut further left
    instead. Horizontal wires crossing the cut simply get longer.
    """

    def moved(point: Point) -> Point:
        beyond = point[0] > cut if distance > 0 else point[0] < cut
        return (point[0] + distance, point[1]) if beyond else point

    for component_id, position in tuple(circuit.positions.items()):
        circuit.positions[component_id] = moved(position)
    for junction_id, junction in tuple(circuit.junctions.items()):
        circuit.junctions[junction_id] = replace(junction, position=moved(junction.position))
    for wire_id, wire in tuple(circuit.wires.items()):
        if wire.route:
            circuit.wires[wire_id] = replace(wire, route=tuple(moved(p) for p in wire.route))
    circuit.touch()


def delete_elements(
    circuit: Circuit,
    component_ids: Iterable[str] = (),
    wire_ids: Iterable[str] = (),
    junction_ids: Iterable[str] = (),
    bends: Iterable[tuple[str, int]] = (),
) -> None:
    """Remove a mixed selection of components, wires, junctions, and wire bends.

    Deleting a junction also deletes every wire attached to it. Junctions left
    without any wire afterwards are removed, because they could no longer be
    seen as part of the circuit.
    """
    bends_by_wire: dict[str, set[int]] = defaultdict(set)
    for wire_id, index in bends:
        bends_by_wire[wire_id].add(index)
    for wire_id, indices in bends_by_wire.items():
        wire = circuit.wires.get(wire_id)
        if wire is not None:
            route = tuple(point for index, point in enumerate(wire.route) if index not in indices)
            circuit.wires[wire_id] = replace(wire, route=route)

    for component_id in component_ids:
        if component_id in circuit.components:
            delete_component(circuit, component_id)

    for wire_id in wire_ids:
        circuit.wires.pop(wire_id, None)

    doomed = set(junction_ids)
    for wire_id, wire in tuple(circuit.wires.items()):
        if any(
            isinstance(endpoint, JunctionRef) and endpoint.junction_id in doomed
            for endpoint in (wire.start, wire.end)
        ):
            del circuit.wires[wire_id]

    used = {
        endpoint.junction_id
        for wire in circuit.wires.values()
        for endpoint in (wire.start, wire.end)
        if isinstance(endpoint, JunctionRef)
    }
    for junction_id in tuple(circuit.junctions):
        if junction_id in doomed or junction_id not in used:
            del circuit.junctions[junction_id]
    circuit.touch()


@dataclass(slots=True)
class _CircuitState:
    source: VoltageSource
    settings: SimulationSettings
    components: dict[str, Component]
    nodes: set[str]
    positions: dict[str, tuple[float, float]]
    open_edge: str | None
    counters: dict[str, int]
    rotations: dict[str, int]
    junctions: dict[str, Junction]
    wires: dict[str, Wire]
    wire_counter: int
    junction_counter: int

    @classmethod
    def capture(cls, circuit: Circuit) -> _CircuitState:
        return cls(
            circuit.source,
            circuit.settings,
            deepcopy(circuit.components),
            set(circuit.nodes),
            dict(circuit.positions),
            circuit.open_edge,
            dict(circuit._id_counters),
            dict(circuit.rotations),
            dict(circuit.junctions),
            dict(circuit.wires),
            circuit._wire_counter,
            circuit._junction_counter,
        )

    def restore(self, circuit: Circuit) -> None:
        circuit.source = self.source
        circuit.settings = self.settings
        circuit.components = deepcopy(self.components)
        circuit.nodes = set(self.nodes)
        circuit.positions = dict(self.positions)
        circuit.open_edge = self.open_edge
        circuit._id_counters = dict(self.counters)
        circuit.rotations = dict(self.rotations)
        circuit.junctions = dict(self.junctions)
        circuit.wires = dict(self.wires)
        circuit._wire_counter = self.wire_counter
        circuit._junction_counter = self.junction_counter
        circuit.revision += 1


class CircuitCommandStack:
    """Small domain-level history used by tests and the Qt undo adapter."""

    def __init__(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self._states = [_CircuitState.capture(circuit)]
        self._index = 0
        self._merge_key: Hashable | None = None
        self._clean_state: _CircuitState | None = self._states[0]

    def _execute(
        self,
        operation: Callable[[], object | None],
        merge_key: Hashable | None = None,
    ) -> object | None:
        """Run an edit and record it as one history entry.

        Consecutive edits that pass the same non-None ``merge_key`` (for example,
        every tick of one slider drag) replace the latest entry instead of adding
        new ones, so a single undo reverts the whole gesture.
        """
        merging = (
            merge_key is not None
            and merge_key == self._merge_key
            and self._index > 0
            and self._index == len(self._states) - 1
        )
        result = operation()
        if merging:
            self._states[self._index] = _CircuitState.capture(self.circuit)
            return result
        del self._states[self._index + 1 :]
        self._states.append(_CircuitState.capture(self.circuit))
        self._index += 1
        self._merge_key = merge_key
        return result

    def mark_clean(self) -> None:
        """Remember the current state as saved."""
        self._clean_state = self._states[self._index]

    @property
    def is_clean(self) -> bool:
        """True when the circuit matches the last saved (or initial) state."""
        return self._states[self._index] is self._clean_state

    def insert_series(
        self, target_edge: str | None, kind: ComponentKind | str, value: float
    ) -> str:
        result = self._execute(lambda: insert_series(self.circuit, target_edge, kind, value))
        assert isinstance(result, str)
        return result

    def add_parallel(
        self, target_component_id: str, kind: ComponentKind | str, value: float
    ) -> str:
        result = self._execute(lambda: add_parallel(self.circuit, target_component_id, kind, value))
        assert isinstance(result, str)
        return result

    def update_value(
        self, component_id: str, value: float, *, merge_key: Hashable | None = None
    ) -> None:
        self._execute(lambda: update_component_value(self.circuit, component_id, value), merge_key)

    def set_simulation_settings(self, settings: SimulationSettings) -> None:
        def operation() -> None:
            self.circuit.settings = settings
            self.circuit.touch()

        self._execute(operation)

    def set_source_voltage(self, voltage: float, *, merge_key: Hashable | None = None) -> None:
        def operation() -> None:
            self.circuit.source = replace(self.circuit.source, voltage=voltage)
            self.circuit.touch()

        self._execute(operation, merge_key)

    def delete(self, component_id: str) -> None:
        self._execute(lambda: delete_component(self.circuit, component_id))

    def delete_elements(
        self,
        component_ids: Iterable[str] = (),
        wire_ids: Iterable[str] = (),
        junction_ids: Iterable[str] = (),
        bends: Iterable[tuple[str, int]] = (),
    ) -> None:
        components, wires, junctions = tuple(component_ids), tuple(wire_ids), tuple(junction_ids)
        bend_refs = tuple(bends)
        self._execute(
            lambda: delete_elements(self.circuit, components, wires, junctions, bend_refs)
        )

    def add_loose_component(self, kind: ComponentKind | str, value: float, position: Point) -> str:
        component_kind = _kind(kind)

        def operation() -> str:
            component_id = self.circuit.next_id(_PREFIX[component_kind])
            self.circuit.add_component(
                make_component(
                    component_kind,
                    component_id,
                    f"loose_{component_id}_a",
                    f"loose_{component_id}_b",
                    value,
                )
            )
            self.circuit.positions[component_id] = position
            self.circuit.rotations[component_id] = 0
            return component_id

        result = self._execute(operation)
        assert isinstance(result, str)
        return result

    def connect(
        self,
        start: EndpointRef,
        end: EndpointRef,
        route: tuple[Point, ...] = (),
        *,
        merge_key: Hashable | None = None,
    ) -> str:
        def operation() -> str:
            self.circuit.assert_endpoint(start)
            self.circuit.assert_endpoint(end)
            wire_id = self.circuit.next_wire_id()
            self.circuit.wires[wire_id] = Wire(wire_id, start, end, route)
            self.circuit.touch()
            return wire_id

        result = self._execute(operation, merge_key)
        assert isinstance(result, str)
        return result

    def connect_to_new_junction(
        self, start: EndpointRef, position: Point, route: tuple[Point, ...] = ()
    ) -> tuple[str, str]:
        """Finish a wire on empty canvas as one undoable edit."""

        def operation() -> tuple[str, str]:
            self.circuit.assert_endpoint(start)
            junction_id = self.circuit.next_junction_id()
            junction_ref = JunctionRef(junction_id)
            self.circuit.junctions[junction_id] = Junction(junction_id, position)
            wire_id = self.circuit.next_wire_id()
            self.circuit.wires[wire_id] = Wire(wire_id, start, junction_ref, route)
            self.circuit.touch()
            return junction_id, wire_id

        result = self._execute(operation)
        assert isinstance(result, tuple) and len(result) == 2
        junction_id, wire_id = result
        assert isinstance(junction_id, str) and isinstance(wire_id, str)
        return junction_id, wire_id

    def insert_component_on_wire(
        self,
        wire_id: str,
        kind: ComponentKind | str,
        value: float,
        position: Point,
        rotation: int,
        start_route: tuple[Point, ...] = (),
        end_route: tuple[Point, ...] = (),
        *,
        merge_key: Hashable | None = None,
    ) -> str:
        """Replace one ideal-wire span with a component as one history entry."""
        component_kind = _kind(kind)

        def operation() -> str:
            original = self.circuit.wires[wire_id]
            component_id = self.circuit.next_id(_PREFIX[component_kind])
            self.circuit.add_component(
                make_component(
                    component_kind,
                    component_id,
                    f"loose_{component_id}_a",
                    f"loose_{component_id}_b",
                    value,
                )
            )
            self._replace_wire(component_id, original, position, rotation, start_route, end_route)
            return component_id

        result = self._execute(operation, merge_key)
        assert isinstance(result, str)
        return result

    def shift_layout(
        self, cut: float, distance: float, *, merge_key: Hashable | None = None
    ) -> None:
        """Open up horizontal space at ``x = cut`` (see :func:`shift_layout`)."""
        self._execute(lambda: shift_layout(self.circuit, cut, distance), merge_key)

    def dissolve_junction(self, junction_id: str, *, merge_key: Hashable | None = None) -> None:
        """Make the two wires that meet at a junction one wire (see :func:`dissolve_junction`)."""
        self._execute(lambda: dissolve_junction(self.circuit, junction_id), merge_key)

    def splice_component_into_wire(
        self,
        component_id: str,
        wire_id: str,
        position: Point,
        rotation: int,
        start_route: tuple[Point, ...] = (),
        end_route: tuple[Point, ...] = (),
    ) -> None:
        """Put an unconnected component into a wire, as if it had been dropped there."""

        def operation() -> None:
            if component_id not in self.circuit.components:
                raise KeyError(component_id)
            terminals = {TerminalRef(component_id, "a"), TerminalRef(component_id, "b")}
            if any(
                endpoint in terminals
                for wire in self.circuit.wires.values()
                for endpoint in (wire.start, wire.end)
            ):
                raise ValueError(f"{component_id} is already wired")
            original = self.circuit.wires[wire_id]
            self._replace_wire(component_id, original, position, rotation, start_route, end_route)

        self._execute(operation)

    def _replace_wire(
        self,
        component_id: str,
        original: Wire,
        position: Point,
        rotation: int,
        start_route: tuple[Point, ...],
        end_route: tuple[Point, ...],
    ) -> None:
        """Swap one wire for wire → component → wire, keeping both original ends."""
        self.circuit.positions[component_id] = position
        self.circuit.rotations[component_id] = rotation % 360
        del self.circuit.wires[original.id]
        start_wire_id = self.circuit.next_wire_id()
        end_wire_id = self.circuit.next_wire_id()
        self.circuit.wires[start_wire_id] = Wire(
            start_wire_id, original.start, TerminalRef(component_id, "a"), start_route
        )
        self.circuit.wires[end_wire_id] = Wire(
            end_wire_id, TerminalRef(component_id, "b"), original.end, end_route
        )
        self.circuit.touch()

    def add_parallel_wired(
        self,
        target_component_id: str,
        kind: ComponentKind | str,
        value: float,
        position: Point,
        rotation: int,
        route_a: tuple[Point, ...] = (),
        route_b: tuple[Point, ...] = (),
    ) -> str:
        """Create a component and connect both terminals across a target branch."""
        component_kind = _kind(kind)

        def operation() -> str:
            if target_component_id not in self.circuit.components:
                raise KeyError(target_component_id)
            component_id = self.circuit.next_id(_PREFIX[component_kind])
            self.circuit.add_component(
                make_component(
                    component_kind,
                    component_id,
                    f"loose_{component_id}_a",
                    f"loose_{component_id}_b",
                    value,
                )
            )
            self.circuit.positions[component_id] = position
            self.circuit.rotations[component_id] = rotation % 360
            connections = (
                (
                    TerminalRef(target_component_id, "a"),
                    TerminalRef(component_id, "a"),
                    route_a,
                ),
                (
                    TerminalRef(target_component_id, "b"),
                    TerminalRef(component_id, "b"),
                    route_b,
                ),
            )
            for start, end, route in connections:
                wire_id = self.circuit.next_wire_id()
                self.circuit.wires[wire_id] = Wire(
                    wire_id,
                    start,
                    end,
                    route,
                )
            self.circuit.touch()
            return component_id

        result = self._execute(operation)
        assert isinstance(result, str)
        return result

    def split_wire(
        self,
        wire_id: str,
        position: Point,
        start_route: tuple[Point, ...] = (),
        end_route: tuple[Point, ...] = (),
        *,
        merge_key: Hashable | None = None,
    ) -> str:
        def operation() -> str:
            wire = self.circuit.wires[wire_id]
            junction_id = self.circuit.next_junction_id()
            junction_ref = JunctionRef(junction_id)
            self.circuit.junctions[junction_id] = Junction(junction_id, position)
            self.circuit.wires[wire_id] = replace(wire, end=junction_ref, route=start_route)
            second_id = self.circuit.next_wire_id()
            self.circuit.wires[second_id] = Wire(second_id, junction_ref, wire.end, end_route)
            self.circuit.touch()
            return junction_id

        result = self._execute(operation, merge_key)
        assert isinstance(result, str)
        return result

    def move_component(self, component_id: str, position: Point) -> None:
        def operation() -> None:
            if component_id not in self.circuit.components:
                raise KeyError(component_id)
            self.circuit.positions[component_id] = position
            self.circuit.touch()

        self._execute(operation)

    def rotate_component(self, component_id: str) -> None:
        def operation() -> None:
            component = self.circuit.components[component_id]
            current = self.circuit.rotations.get(component_id, component.rotation)
            self.circuit.rotations[component_id] = (current + 90) % 360
            self.circuit.touch()

        self._execute(operation)

    def move_junction(self, junction_id: str, position: Point) -> None:
        def operation() -> None:
            junction = self.circuit.junctions[junction_id]
            self.circuit.junctions[junction_id] = replace(junction, position=position)
            self.circuit.touch()

        self._execute(operation)

    def set_wire_route(self, wire_id: str, route: tuple[Point, ...]) -> None:
        def operation() -> None:
            self.circuit.wires[wire_id] = replace(self.circuit.wires[wire_id], route=route)
            self.circuit.touch()

        self._execute(operation)

    def undo(self) -> bool:
        if self._index == 0:
            return False
        self._index -= 1
        self._merge_key = None
        self._states[self._index].restore(self.circuit)
        return True

    def redo(self) -> bool:
        if self._index >= len(self._states) - 1:
            return False
        self._index += 1
        self._merge_key = None
        self._states[self._index].restore(self.circuit)
        return True
