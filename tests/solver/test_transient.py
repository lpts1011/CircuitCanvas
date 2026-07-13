from dataclasses import replace

import numpy as np
import pytest

from circuitcanvas.commands.circuit_commands import insert_series
from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.solver.transient import simulate


def _series_circuit(
    parts: list[tuple[ComponentKind, float]],
    *,
    voltage: float = 5.0,
    duration: float = 0.05,
    samples: int = 2001,
) -> Circuit:
    circuit = Circuit.new(voltage)
    target = circuit.open_edge
    for kind, value in parts:
        target = insert_series(circuit, target, kind, value)
    circuit.settings = SimulationSettings(duration=duration, samples=samples)
    return circuit


def test_resistor_result_obeys_ohms_law_after_step() -> None:
    circuit = _series_circuit([(ComponentKind.RESISTOR, 100.0)], voltage=12.0)

    result = simulate(circuit.snapshot())

    assert result.branches["R1"].current[-1] == pytest.approx(0.12)
    assert result.branches["R1"].voltage[-1] == pytest.approx(12.0)
    assert result.source_power[-1] == pytest.approx(-1.44)


def test_rc_step_matches_analytic_curve() -> None:
    circuit = _series_circuit(
        [(ComponentKind.RESISTOR, 1_000.0), (ComponentKind.CAPACITOR, 10e-6)]
    )

    result = simulate(circuit.snapshot())
    expected = 5.0 * (1.0 - np.exp(-result.time / 0.01))

    np.testing.assert_allclose(result.branches["C1"].voltage[1:], expected[1:], atol=8e-3)
    assert result.branches["C1"].energy[-1] == pytest.approx(
        0.5 * 10e-6 * result.branches["C1"].voltage[-1] ** 2
    )


def test_rl_step_matches_analytic_curve() -> None:
    circuit = _series_circuit(
        [(ComponentKind.RESISTOR, 10.0), (ComponentKind.INDUCTOR, 0.1)],
        duration=0.05,
    )

    result = simulate(circuit.snapshot())
    expected = 0.5 * (1.0 - np.exp(-result.time / 0.01))

    np.testing.assert_allclose(result.branches["L1"].current[1:], expected[1:], atol=8e-4)


def test_backward_euler_is_available_and_finite() -> None:
    circuit = _series_circuit(
        [
            (ComponentKind.RESISTOR, 20.0),
            (ComponentKind.INDUCTOR, 0.02),
            (ComponentKind.CAPACITOR, 10e-6),
        ],
        duration=0.01,
    )
    circuit.settings = replace(circuit.settings, method="backward-euler")

    result = simulate(circuit.snapshot())

    assert np.isfinite(result.state).all()
    assert result.metrics["peak_current_a"] > 0

