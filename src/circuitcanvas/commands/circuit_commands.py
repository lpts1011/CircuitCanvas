"""Repeatable series/parallel edits with snapshot-based undo and redo."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import (
    Component,
    ComponentKind,
    make_component,
    replace_value,
)
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


def delete_component(circuit: Circuit, component_id: str) -> Component:
    try:
        component = circuit.components[component_id]
        position = circuit.positions.get(component_id, (0.0, 0.0))
        rotation = circuit.rotations.get(component_id, component.rotation) % 360
        terminal_junctions: dict[str, JunctionRef] = {}
        for terminal in ("a", "b"):
            ref = TerminalRef(component_id, terminal)
            if not any(ref in (wire.start, wire.end) for wire in circuit.wires.values()):
                continue
            junction_id = circuit.next_junction_id()
            direction = -1.0 if terminal == "a" else 1.0
            if rotation in {90, 270}:
                junction_position = (position[0], position[1] + direction * 84.0)
            else:
                junction_position = (position[0] + direction * 84.0, position[1])
            circuit.junctions[junction_id] = Junction(junction_id, junction_position)
            terminal_junctions[terminal] = JunctionRef(junction_id)
        for wire_id, wire in tuple(circuit.wires.items()):
            start = wire.start
            end = wire.end
            if isinstance(start, TerminalRef) and start.owner_id == component_id:
                start = terminal_junctions[start.terminal]
            if isinstance(end, TerminalRef) and end.owner_id == component_id:
                end = terminal_junctions[end.terminal]
            circuit.wires[wire_id] = replace(wire, start=start, end=end)
        return circuit.remove_component(component_id)
    except KeyError:
        raise KeyError(component_id) from None


@dataclass(slots=True)
class _CircuitState:
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

    def _execute(self, operation: Callable[[], object | None]) -> object | None:
        result = operation()
        del self._states[self._index + 1 :]
        self._states.append(_CircuitState.capture(self.circuit))
        self._index += 1
        return result

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

    def update_value(self, component_id: str, value: float) -> None:
        self._execute(lambda: update_component_value(self.circuit, component_id, value))

    def delete(self, component_id: str) -> None:
        self._execute(lambda: delete_component(self.circuit, component_id))

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

    def connect(self, start: EndpointRef, end: EndpointRef, route: tuple[Point, ...] = ()) -> str:
        def operation() -> str:
            self.circuit.assert_endpoint(start)
            self.circuit.assert_endpoint(end)
            wire_id = self.circuit.next_wire_id()
            self.circuit.wires[wire_id] = Wire(wire_id, start, end, route)
            self.circuit.touch()
            return wire_id

        result = self._execute(operation)
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
            self.circuit.positions[component_id] = position
            self.circuit.rotations[component_id] = rotation % 360
            del self.circuit.wires[wire_id]
            start_wire_id = self.circuit.next_wire_id()
            end_wire_id = self.circuit.next_wire_id()
            self.circuit.wires[start_wire_id] = Wire(
                start_wire_id,
                original.start,
                TerminalRef(component_id, "a"),
                start_route,
            )
            self.circuit.wires[end_wire_id] = Wire(
                end_wire_id,
                TerminalRef(component_id, "b"),
                original.end,
                end_route,
            )
            self.circuit.touch()
            return component_id

        result = self._execute(operation)
        assert isinstance(result, str)
        return result

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

    def split_wire(self, wire_id: str, position: Point) -> str:
        def operation() -> str:
            wire = self.circuit.wires[wire_id]
            junction_id = self.circuit.next_junction_id()
            junction_ref = JunctionRef(junction_id)
            self.circuit.junctions[junction_id] = Junction(junction_id, position)
            self.circuit.wires[wire_id] = replace(wire, end=junction_ref, route=())
            second_id = self.circuit.next_wire_id()
            self.circuit.wires[second_id] = Wire(second_id, junction_ref, wire.end)
            self.circuit.touch()
            return junction_id

        result = self._execute(operation)
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
        self._states[self._index].restore(self.circuit)
        return True

    def redo(self) -> bool:
        if self._index >= len(self._states) - 1:
            return False
        self._index += 1
        self._states[self._index].restore(self.circuit)
        return True
