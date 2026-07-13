import pytest

from circuitcanvas.commands.circuit_commands import (
    CircuitCommandStack,
    add_parallel,
    delete_component,
    insert_series,
    update_component_value,
)
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind


def test_repeated_series_and_parallel_additions_preserve_connectivity() -> None:
    circuit = Circuit.new(9.0)
    r1 = insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)
    c1 = insert_series(circuit, circuit.edge_after(r1), ComponentKind.CAPACITOR, 1e-6)
    r2 = add_parallel(circuit, c1, ComponentKind.RESISTOR, 220.0)

    assert set(circuit.components) == {r1, c1, r2}
    assert circuit.components[c1].endpoints == circuit.components[r2].endpoints
    assert circuit.components[r1].node_b == circuit.components[c1].node_a


def test_component_ids_increment_per_kind() -> None:
    circuit = Circuit.new()
    first = insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)
    second = add_parallel(circuit, first, ComponentKind.RESISTOR, 200.0)

    assert (first, second) == ("R1", "R2")


def test_update_and_delete_reject_missing_ids() -> None:
    circuit = Circuit.new()
    with pytest.raises(KeyError):
        update_component_value(circuit, "R9", 10.0)
    with pytest.raises(KeyError):
        delete_component(circuit, "C7")


def test_command_stack_restores_complete_graph_state() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    stack.insert_series(circuit.open_edge, ComponentKind.INDUCTOR, 0.02)
    stack.add_parallel("L1", ComponentKind.CAPACITOR, 1e-6)
    assert set(circuit.components) == {"L1", "C1"}

    stack.undo()
    assert set(circuit.components) == {"L1"}
    stack.redo()
    assert set(circuit.components) == {"L1", "C1"}
