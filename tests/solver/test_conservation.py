import numpy as np

from circuitcanvas.commands.circuit_commands import insert_series
from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.solver.transient import simulate


def test_series_rc_has_small_kcl_residual_after_first_step() -> None:
    circuit = Circuit.new(10.0)
    r1 = insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 1000.0)
    insert_series(circuit, r1, ComponentKind.CAPACITOR, 1e-6)
    circuit.settings = SimulationSettings(duration=0.01, samples=1001)

    result = simulate(circuit.snapshot())

    assert np.max(np.abs(result.kcl_residual[2:])) < 1e-8
