"""Repeatable series/parallel edits with snapshot-based undo and redo."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import (
    Component,
    ComponentKind,
    make_component,
    replace_value,
)

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

    @classmethod
    def capture(cls, circuit: Circuit) -> _CircuitState:
        return cls(
            deepcopy(circuit.components),
            set(circuit.nodes),
            dict(circuit.positions),
            circuit.open_edge,
            dict(circuit._id_counters),
        )

    def restore(self, circuit: Circuit) -> None:
        circuit.components = deepcopy(self.components)
        circuit.nodes = set(self.nodes)
        circuit.positions = dict(self.positions)
        circuit.open_edge = self.open_edge
        circuit._id_counters = dict(self.counters)
        circuit.revision += 1


class CircuitCommandStack:
    """Small domain-level history used by tests and the Qt undo adapter."""

    def __init__(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self._states = [_CircuitState.capture(circuit)]
        self._index = 0

    def _execute(self, operation: Callable[[], str | Component | None]) -> str | Component | None:
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
