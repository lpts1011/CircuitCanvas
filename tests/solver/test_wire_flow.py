import pytest

from circuitcanvas.commands.circuit_commands import CircuitCommandStack
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.wiring import TerminalRef
from circuitcanvas.solver.transient import simulate
from circuitcanvas.solver.wire_flow import reconstruct_wire_flows


def parallel_series_wired_circuit(*, reverse_first: bool = False) -> Circuit:
    circuit = Circuit.new(17.0)
    stack = CircuitCommandStack(circuit)
    r1 = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))
    r2 = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (520.0, 180.0))
    r3 = stack.add_loose_component(ComponentKind.RESISTOR, 200.0, (410.0, 340.0))
    first_start = TerminalRef(r1, "a") if reverse_first else TerminalRef("V1", "a")
    first_end = TerminalRef("V1", "a") if reverse_first else TerminalRef(r1, "a")
    stack.connect(first_start, first_end)
    stack.connect(TerminalRef(r1, "b"), TerminalRef(r2, "a"))
    stack.connect(TerminalRef(r2, "b"), TerminalRef("V1", "b"))
    stack.connect(TerminalRef("V1", "a"), TerminalRef(r3, "a"))
    stack.connect(TerminalRef(r3, "b"), TerminalRef("V1", "b"))
    return circuit


def test_wire_flows_obey_kcl_and_split_equally() -> None:
    snapshot = parallel_series_wired_circuit().snapshot()
    result = simulate(snapshot)

    flows = reconstruct_wire_flows(snapshot, result, len(result.time) - 1)

    assert max(flows.net_residuals.values(), default=0.0) < 1e-9
    assert flows.currents["W1"] == pytest.approx(0.085, rel=1e-4)
    assert flows.currents["W4"] == pytest.approx(0.085, rel=1e-4)
    assert abs(result.source_current[-1]) == pytest.approx(0.17, rel=1e-4)


def test_wire_flow_sign_follows_stored_wire_orientation() -> None:
    snapshot = parallel_series_wired_circuit(reverse_first=True).snapshot()
    result = simulate(snapshot)

    flows = reconstruct_wire_flows(snapshot, result, -1)

    assert flows.currents["W1"] == pytest.approx(-0.085, rel=1e-4)
