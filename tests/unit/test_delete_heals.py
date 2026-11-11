"""Deleting a component leaves a circuit that still makes sense."""

from circuitcanvas.commands.circuit_commands import CircuitCommandStack
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.wiring import TerminalRef
from circuitcanvas.solver.validation import validate
from circuitcanvas.ui.routing import simplify_polyline


def _loop_with(*kinds: ComponentKind) -> tuple[Circuit, CircuitCommandStack, list[str]]:
    """The starter loop with components inserted left to right along the top wire."""
    circuit = Circuit.starter_loop(12.0)
    stack = CircuitCommandStack(circuit)
    ids = []
    wire_id = "W1"
    for index, kind in enumerate(kinds):
        component_id = stack.insert_component_on_wire(
            wire_id, kind, 100.0, (330.0 + 220.0 * index, 290.0), 0, (), ()
        )
        ids.append(component_id)
        # The wire that continues to the right of the new component.
        wire_id = next(
            wire.id
            for wire in circuit.wires.values()
            if wire.start == TerminalRef(component_id, "b")
        )
    return circuit, stack, ids


def _codes(circuit: Circuit) -> list[str]:
    return [diagnostic.code for diagnostic in validate(circuit.snapshot())]


def test_deleting_a_series_component_closes_the_loop_behind_it() -> None:
    circuit, stack, (r1, c1) = _loop_with(ComponentKind.RESISTOR, ComponentKind.CAPACITOR)
    assert _codes(circuit) == []

    stack.delete(r1)

    assert set(circuit.components) == {c1}
    assert _codes(circuit) == []  # still a complete circuit: no loose wire ends
    assert set(circuit.junctions) == {"J1", "J2"}  # no new dots where R1 was
    assert len(circuit.wires) == 4
    healed = next(wire for wire in circuit.wires.values() if wire.end == TerminalRef(c1, "a"))
    assert healed.start == TerminalRef("V1", "a")
    assert healed.route == ()  # a straight wire needs no bends

    assert stack.undo()
    assert set(circuit.components) == {r1, c1}
    assert _codes(circuit) == []


def test_deleting_the_only_component_gives_back_the_empty_starter_loop() -> None:
    circuit, stack, (r1,) = _loop_with(ComponentKind.RESISTOR)

    stack.delete_elements(component_ids=[r1])

    assert circuit.components == {}
    assert len(circuit.wires) == 3
    assert set(circuit.junctions) == {"J1", "J2"}
    assert _codes(circuit) == ["source-short"]  # the friendly "add a component" state


def test_deleting_a_parallel_copy_removes_its_two_leads() -> None:
    circuit, stack, (r1, c1) = _loop_with(ComponentKind.RESISTOR, ComponentKind.CAPACITOR)
    wires_before = set(circuit.wires)
    copy = stack.add_parallel_wired(r1, ComponentKind.RESISTOR, 100.0, (330.0, 430.0), 0)

    stack.delete(copy)

    assert set(circuit.components) == {r1, c1}
    assert set(circuit.wires) == wires_before  # no bare wire left across R1
    assert _codes(circuit) == []


def test_deleting_the_original_keeps_its_parallel_copy_in_the_circuit() -> None:
    circuit, stack, (r1, c1) = _loop_with(ComponentKind.RESISTOR, ComponentKind.CAPACITOR)
    copy = stack.add_parallel_wired(r1, ComponentKind.RESISTOR, 100.0, (330.0, 430.0), 0)

    stack.delete(r1)

    assert set(circuit.components) == {c1, copy}
    assert _codes(circuit) == []


def test_deleting_a_half_wired_component_takes_its_lead_with_it() -> None:
    circuit, stack, (r1,) = _loop_with(ComponentKind.RESISTOR)
    loose = stack.add_loose_component(ComponentKind.CAPACITOR, 1e-6, (600.0, 600.0))
    stack.connect(TerminalRef(r1, "b"), TerminalRef(loose, "a"))
    assert _codes(circuit) == ["dangling-terminal"]

    stack.delete(loose)

    assert _codes(circuit) == []
    assert set(circuit.junctions) == {"J1", "J2"}


def test_healed_wire_keeps_the_corners_it_needs() -> None:
    circuit, stack, (r1,) = _loop_with(ComponentKind.RESISTOR)
    stack.move_component(r1, (330.0, 200.0))  # lifted above the top wire

    stack.delete(r1)

    assert len(circuit.wires) == 3
    healed = next(wire for wire in circuit.wires.values() if wire.start == TerminalRef("V1", "a"))
    # The wire still runs through where the resistor's two ends were.
    assert healed.route == ((246.0, 200.0), (414.0, 200.0))


def test_simplify_polyline_drops_points_on_a_straight_run() -> None:
    points = ((0.0, 0.0), (10.0, 0.0), (10.0, 0.0), (30.0, 0.0), (30.0, 20.0), (30.0, 50.0))

    assert simplify_polyline(points) == ((0.0, 0.0), (30.0, 0.0), (30.0, 50.0))
    assert simplify_polyline(((1.0, 1.0),)) == ((1.0, 1.0),)
