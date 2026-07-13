from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import Capacitor, Inductor, Resistor
from circuitcanvas.solver.equations import build_equation_report
from circuitcanvas.solver.transient import simulate


def parallel_series_circuit() -> Circuit:
    circuit = Circuit.new(17.0)
    circuit.nodes.add("n_mid")
    circuit.add_component(Resistor("R1", "n_pos", "n_mid", 100.0))
    circuit.add_component(Resistor("R2", "n_mid", "n_neg", 100.0))
    circuit.add_component(Resistor("R3", "n_pos", "n_neg", 200.0))
    circuit.open_edge = None
    return circuit


def test_parallel_series_fixture_has_independent_kcl_and_kvl() -> None:
    snapshot = parallel_series_circuit().snapshot()
    result = simulate(snapshot)

    report = build_equation_report(snapshot, result, len(result.time) - 1)

    assert len(report.kcl) == len(snapshot.nodes) - 1
    assert len(report.kvl) == 2
    assert max(abs(line.residual) for line in (*report.kcl, *report.kvl)) < 1e-9
    assert "0.085" in "\n".join(line.substituted for line in report.kcl)
    assert any("-0.17 + 0.085 + 0.085 = 0" in line.substituted for line in report.kcl)


def test_differential_report_expands_reactive_laws_and_mna() -> None:
    circuit = Circuit.new(10.0)
    circuit.nodes.update({"n1", "n2"})
    circuit.add_component(Resistor("R1", "n_pos", "n1", 10.0))
    circuit.add_component(Inductor("L1", "n1", "n2", 0.05))
    circuit.add_component(Capacitor("C1", "n2", "n_neg", 1e-4))
    circuit.open_edge = None
    snapshot = circuit.snapshot()

    report = build_equation_report(snapshot, simulate(snapshot), 20)

    assert "C1·dv_C1/dt" in report.differential_text
    assert "L1·di_L1/dt" in report.differential_text
    assert "C x_dot(t) + G x(t) = b(t)" in report.descriptor_text
    assert "Differential-algebraic MNA system" in report.descriptor_text
