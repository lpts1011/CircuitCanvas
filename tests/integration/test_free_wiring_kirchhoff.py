import pytest

from circuitcanvas.commands.circuit_commands import CircuitCommandStack
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.wiring import TerminalRef
from circuitcanvas.solver.equations import build_equation_report
from circuitcanvas.solver.transient import simulate
from circuitcanvas.solver.wire_flow import reconstruct_wire_flows


def parallel_series_17v_fixture() -> Circuit:
    circuit = Circuit.new(17.0)
    stack = CircuitCommandStack(circuit)
    r1 = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (340.0, 180.0))
    r2 = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (560.0, 180.0))
    r3 = stack.add_loose_component(ComponentKind.RESISTOR, 200.0, (450.0, 360.0))
    stack.connect(TerminalRef("V1", "a"), TerminalRef(r1, "a"))
    stack.connect(TerminalRef(r1, "b"), TerminalRef(r2, "a"))
    stack.connect(TerminalRef(r2, "b"), TerminalRef("V1", "b"))
    stack.connect(TerminalRef("V1", "a"), TerminalRef(r3, "a"))
    stack.connect(TerminalRef(r3, "b"), TerminalRef("V1", "b"))
    return circuit


def test_r3_parallel_with_r1_plus_r2_obeys_kirchhoff() -> None:
    snapshot = parallel_series_17v_fixture().snapshot()
    result = simulate(snapshot)
    report = build_equation_report(snapshot, result, -1)
    flows = reconstruct_wire_flows(snapshot, result, -1)

    assert result.branches["R1"].current[-1] == pytest.approx(0.085, rel=1e-4)
    assert result.branches["R2"].current[-1] == pytest.approx(0.085, rel=1e-4)
    assert result.branches["R3"].current[-1] == pytest.approx(0.085, rel=1e-4)
    assert abs(result.source_current[-1]) == pytest.approx(0.17, rel=1e-4)
    assert max(abs(equation.residual) for equation in (*report.kcl, *report.kvl)) < 1e-9
    assert max(flows.net_residuals.values()) < 1e-9
