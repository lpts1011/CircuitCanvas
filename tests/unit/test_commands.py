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
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef


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


def test_free_wiring_commands_connect_split_move_and_undo() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)

    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))
    wire = stack.connect(TerminalRef("V1", "a"), TerminalRef(resistor, "a"))
    junction = stack.split_wire(wire, (210.0, 180.0))
    stack.move_component(resistor, (420.0, 260.0))
    stack.rotate_component(resistor)

    assert circuit.positions[resistor] == (420.0, 260.0)
    assert circuit.rotations[resistor] == 90
    assert any(
        isinstance(candidate.start, JunctionRef) or isinstance(candidate.end, JunctionRef)
        for candidate in circuit.wires.values()
    )
    assert circuit.junctions[junction].position == (210.0, 180.0)

    assert stack.undo()
    assert circuit.rotations[resistor] == 0
    assert stack.undo()
    assert circuit.positions[resistor] == (300.0, 180.0)


def test_deleting_connected_component_leaves_reconnectable_junctions() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (320.0, 220.0))
    stack.connect(TerminalRef("V1", "a"), TerminalRef(resistor, "a"))

    stack.delete(resistor)

    assert resistor not in circuit.components
    assert all(
        not (isinstance(endpoint, TerminalRef) and endpoint.owner_id == resistor)
        for wire in circuit.wires.values()
        for endpoint in (wire.start, wire.end)
    )
    assert circuit.junctions


def test_connect_to_new_junction_is_one_undoable_edit() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (320.0, 220.0))

    junction_id, wire_id = stack.connect_to_new_junction(
        TerminalRef(resistor, "b"), (540.0, 300.0), ((430.0, 220.0), (430.0, 300.0))
    )

    assert circuit.junctions[junction_id].position == (540.0, 300.0)
    assert circuit.wires[wire_id].end == JunctionRef(junction_id)
    assert len(circuit.wires[wire_id].route) == 2
    assert stack.undo()
    assert junction_id not in circuit.junctions
    assert wire_id not in circuit.wires
