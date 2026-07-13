from pathlib import Path

import numpy as np
import pytest

from circuitcanvas.domain.serialization import load_circuit
from circuitcanvas.solver.transient import simulate


@pytest.mark.parametrize(
    "filename",
    [
        "resistor.json",
        "rc-charge.json",
        "rl-step.json",
        "rlc-underdamped.json",
        "parallel-series-17v.json",
    ],
)
def test_bundled_example_loads_and_simulates(filename: str) -> None:
    circuit = load_circuit(Path("examples") / filename)

    result = simulate(circuit.snapshot())

    assert len(result.time) == circuit.settings.samples
    assert np.isfinite(result.state).all()
