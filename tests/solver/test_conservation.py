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


def test_series_rl_obeys_kvl_and_energy_balance() -> None:
    circuit = Circuit.new(5.0)
    r1 = insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 10.0)
    insert_series(circuit, r1, ComponentKind.INDUCTOR, 0.1)
    circuit.settings = SimulationSettings(duration=0.05, samples=2001)

    result = simulate(circuit.snapshot())
    resistor = result.branches["R1"]
    inductor = result.branches["L1"]
    kvl_error = 5.0 - resistor.voltage[2:] - inductor.voltage[2:]
    energy_rate = np.gradient(inductor.energy, result.time)
    delivered_power = -result.source_power

    assert np.max(np.abs(kvl_error)) < 1e-9
    np.testing.assert_allclose(
        delivered_power[5:-5],
        resistor.power[5:-5] + energy_rate[5:-5],
        rtol=6e-3,
        atol=2e-4,
    )
