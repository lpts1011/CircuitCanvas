from circuitcanvas.commands.circuit_commands import CircuitCommandStack, insert_series
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind, Resistor
from circuitcanvas.domain.wiring import TerminalRef
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


def test_dangling_terminal_blocks_free_wiring_simulation() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (320.0, 220.0))
    stack.connect(TerminalRef("V1", "a"), TerminalRef(resistor, "a"))

    diagnostics = validate(circuit.snapshot())

    assert diagnostics[0].code == "dangling-terminal"
    assert diagnostics[0].component_ids == (resistor,)


def test_direct_wire_short_across_battery_is_rejected() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    stack.connect(TerminalRef("V1", "a"), TerminalRef("V1", "b"))

    diagnostics = validate(circuit.snapshot())

    assert diagnostics[0].code == "source-short"
