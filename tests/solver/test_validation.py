from circuitcanvas.commands.circuit_commands import insert_series
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind, Resistor
from circuitcanvas.solver.validation import validate


def test_open_circuit_reports_actionable_diagnostic() -> None:
    diagnostics = validate(Circuit.new(12.0).snapshot())

    assert diagnostics[0].code == "open-circuit"
    assert "component" in diagnostics[0].message.lower()


def test_connected_resistor_circuit_is_valid() -> None:
    circuit = Circuit.new()
    insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)

    assert validate(circuit.snapshot()) == ()


def test_disconnected_component_is_identified() -> None:
    circuit = Circuit.new()
    insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)
    circuit.add_component(Resistor("R2", "floating_a", "floating_b", 50.0))

    diagnostics = validate(circuit.snapshot())

    assert diagnostics[0].code == "floating-subcircuit"
    assert diagnostics[0].component_ids == ("R2",)
