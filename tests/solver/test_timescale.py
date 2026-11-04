import math

import pytest

from circuitcanvas.commands.circuit_commands import insert_series
from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.solver.mna import assemble
from circuitcanvas.solver.timescale import estimate_time_span, natural_frequencies, nice_ceil
from circuitcanvas.solver.transient import simulate


def _series(*parts: tuple[ComponentKind, float], auto: bool = True) -> Circuit:
    circuit = Circuit.new(5.0)
    target = circuit.open_edge
    for kind, value in parts:
        target = insert_series(circuit, target, kind, value)
    circuit.settings = SimulationSettings(auto_duration=auto)
    return circuit


def _span(circuit: Circuit) -> float | None:
    return estimate_time_span(assemble(circuit.snapshot()))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.047, 0.05), (0.05, 0.05), (0.0123, 0.02), (0.21, 0.25), (3.0, 5.0), (7.0, 10.0)],
)
def test_nice_ceil_rounds_up_to_tidy_values(value: float, expected: float) -> None:
    assert nice_ceil(value) == pytest.approx(expected)


def test_rc_span_is_five_time_constants() -> None:
    # tau = 10 kΩ × 1 mF = 10 s, which the old fixed 0.1 s window could not show.
    circuit = _series((ComponentKind.RESISTOR, 10e3), (ComponentKind.CAPACITOR, 1e-3))

    frequencies = natural_frequencies(assemble(circuit.snapshot()))

    assert frequencies.real == pytest.approx([-0.1])
    assert _span(circuit) == pytest.approx(50.0)


def test_rl_span_uses_l_over_r() -> None:
    circuit = _series((ComponentKind.RESISTOR, 10.0), (ComponentKind.INDUCTOR, 0.1))

    assert _span(circuit) == pytest.approx(0.05)


def test_underdamped_rlc_span_covers_the_decay_envelope() -> None:
    circuit = _series(
        (ComponentKind.RESISTOR, 10.0),
        (ComponentKind.INDUCTOR, 0.05),
        (ComponentKind.CAPACITOR, 1e-4),
    )

    frequencies = natural_frequencies(assemble(circuit.snapshot()))

    assert sorted(abs(f.imag) for f in frequencies) == pytest.approx([435.889894, 435.889894])
    assert _span(circuit) == pytest.approx(0.05)


def test_lossless_lc_span_shows_several_periods() -> None:
    circuit = _series((ComponentKind.INDUCTOR, 1e-3), (ComponentKind.CAPACITOR, 1e-6))
    period = 2 * math.pi * math.sqrt(1e-3 * 1e-6)

    span = _span(circuit)

    assert span is not None
    assert 5 * period <= span < 10 * period


def test_resistive_circuit_has_no_time_scale() -> None:
    assert _span(_series((ComponentKind.RESISTOR, 100.0))) is None


def test_simulation_uses_auto_span_only_when_enabled() -> None:
    parts = ((ComponentKind.RESISTOR, 10e3), (ComponentKind.CAPACITOR, 1e-3))
    automatic = simulate(_series(*parts, auto=True).snapshot())
    fixed = simulate(_series(*parts, auto=False).snapshot())

    assert automatic.time[-1] == pytest.approx(50.0)
    # After 5 time constants the capacitor is within 1 % of the battery voltage.
    assert automatic.branches["C1"].voltage[-1] == pytest.approx(5.0, rel=0.01)
    assert fixed.time[-1] == pytest.approx(SimulationSettings().duration)


def test_resistive_auto_circuit_keeps_configured_span() -> None:
    circuit = _series((ComponentKind.RESISTOR, 100.0))

    assert simulate(circuit.snapshot()).time[-1] == pytest.approx(circuit.settings.duration)
