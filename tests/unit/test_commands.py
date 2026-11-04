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
from circuitcanvas.solver.validation import validate


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


def test_insert_component_on_wire_removes_conductive_bypass_and_undoes_atomically() -> None:
    circuit = Circuit.starter_loop(12.0)
    stack = CircuitCommandStack(circuit)

    component_id = stack.insert_component_on_wire(
        "W1", ComponentKind.RESISTOR, 100.0, (520.0, 290.0), 0, (), ()
    )

    assert "W1" not in circuit.wires
    assert len(circuit.wires) == 4
    assert component_id in circuit.components
    assert validate(circuit.snapshot()) == ()
    assert stack.undo()
    assert circuit.components == {}
    assert "W1" in circuit.wires
    assert stack.redo()
    assert component_id in circuit.components


def test_merge_key_collapses_consecutive_edits_into_one_undo_step() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))

    for value in (150.0, 220.0, 330.0, 470.0):
        stack.update_value(resistor, value, merge_key=("drag", 1))

    assert circuit.components[resistor].value == 470.0
    assert stack.undo()
    assert circuit.components[resistor].value == 100.0
    assert stack.redo()
    assert circuit.components[resistor].value == 470.0


def test_new_merge_key_or_other_edit_starts_a_new_undo_step() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))

    stack.update_value(resistor, 150.0, merge_key=("drag", 1))
    stack.update_value(resistor, 220.0, merge_key=("drag", 2))
    stack.move_component(resistor, (320.0, 180.0))
    stack.update_value(resistor, 330.0, merge_key=("drag", 2))

    assert stack.undo()
    assert circuit.components[resistor].value == 220.0
    assert stack.undo()
    assert circuit.positions[resistor] == (300.0, 180.0)
    assert stack.undo()
    assert circuit.components[resistor].value == 150.0


def test_edit_after_undo_does_not_merge_into_redo_history() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))
    stack.update_value(resistor, 150.0, merge_key=("drag", 1))
    stack.undo()

    stack.update_value(resistor, 680.0, merge_key=("drag", 1))

    assert circuit.components[resistor].value == 680.0
    assert stack.undo()
    assert circuit.components[resistor].value == 100.0


def test_source_voltage_is_part_of_undo_history() -> None:
    circuit = Circuit.new(12.0)
    stack = CircuitCommandStack(circuit)

    stack.set_source_voltage(1.0, merge_key=("source", 0))
    stack.set_source_voltage(17.0, merge_key=("source", 0))

    assert circuit.source.voltage == 17.0
    assert stack.undo()
    assert circuit.source.voltage == 12.0
    assert stack.redo()
    assert circuit.source.voltage == 17.0


def test_clean_state_tracks_save_point_through_undo_and_redo() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    assert stack.is_clean

    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))
    assert not stack.is_clean
    stack.mark_clean()
    assert stack.is_clean

    stack.update_value(resistor, 220.0)
    assert not stack.is_clean
    stack.undo()
    assert stack.is_clean
    stack.redo()
    assert not stack.is_clean


def test_delete_elements_removes_a_wire_and_keeps_its_junctions() -> None:
    circuit = Circuit.starter_loop()
    stack = CircuitCommandStack(circuit)

    stack.delete_elements(wire_ids=["W2"])

    assert "W2" not in circuit.wires
    assert set(circuit.junctions) == {"J1", "J2"}
    assert stack.undo()
    assert "W2" in circuit.wires


def test_delete_elements_removes_junction_with_attached_wires_and_orphans() -> None:
    circuit = Circuit.starter_loop()
    stack = CircuitCommandStack(circuit)

    stack.delete_elements(junction_ids=["J1"])

    assert "J1" not in circuit.junctions
    assert set(circuit.wires) == {"W3"}
    assert set(circuit.junctions) == {"J2"}


def test_delete_elements_drops_selected_wire_bends_only() -> None:
    circuit = Circuit.starter_loop()
    stack = CircuitCommandStack(circuit)
    stack.set_wire_route("W2", ((980.0, 320.0), (980.0, 360.0), (980.0, 400.0)))

    stack.delete_elements(bends=[("W2", 0), ("W2", 2)])

    assert circuit.wires["W2"].route == ((980.0, 360.0),)


def test_delete_elements_handles_component_and_its_wire_in_one_step() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))
    wire = stack.connect(TerminalRef("V1", "a"), TerminalRef(resistor, "a"))

    stack.delete_elements(component_ids=[resistor], wire_ids=[wire])

    assert circuit.components == {}
    assert circuit.wires == {}
    assert circuit.junctions == {}
    assert stack.undo()
    assert resistor in circuit.components
    assert wire in circuit.wires


def test_simulation_settings_are_part_of_undo_history() -> None:
    from dataclasses import replace

    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    original = circuit.settings

    stack.set_simulation_settings(replace(original, duration=2.0, auto_duration=False))
    assert circuit.settings.duration == 2.0

    assert stack.undo()
    assert circuit.settings == original
