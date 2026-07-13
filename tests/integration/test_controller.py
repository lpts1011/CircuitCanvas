from circuitcanvas.commands.circuit_commands import insert_series
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.solver.transient import simulate
from circuitcanvas.ui.simulation_controller import SimulationController


def test_controller_debounces_to_latest_revision(qtbot) -> None:
    circuit = Circuit.new()
    insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)
    calls = []

    def solver(snapshot):
        calls.append(snapshot.revision)
        return simulate(snapshot)

    controller = SimulationController(solver_fn=solver, debounce_ms=10)
    with qtbot.waitSignal(controller.result_ready, timeout=2000) as signal:
        controller.request(1, circuit.snapshot())
        circuit.revision = 2
        controller.request(2, circuit.snapshot())

    assert calls == [2]
    assert signal.args[0] == 2


def test_controller_reports_validation_without_starting_solver(qtbot) -> None:
    circuit = Circuit.new()
    controller = SimulationController(debounce_ms=0)

    with qtbot.waitSignal(controller.diagnostics_ready) as signal:
        controller.request(circuit.revision, circuit.snapshot())

    assert signal.args[1][0].code == "open-circuit"
