from importlib.resources import files

import numpy as np
import pytest

from circuitcanvas.examples import EXAMPLES, Example, load_example
from circuitcanvas.solver.transient import simulate
from circuitcanvas.solver.validation import validate


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.filename)
def test_bundled_example_loads_and_simulates(example: Example) -> None:
    circuit = load_example(example)

    assert validate(circuit.snapshot()) == ()
    result = simulate(circuit.snapshot())

    assert len(result.time) == circuit.settings.samples
    assert np.isfinite(result.state).all()


def test_every_shipped_example_file_is_listed_in_the_menu() -> None:
    shipped = {
        resource.name
        for resource in files("circuitcanvas.examples").iterdir()
        if resource.name.endswith(".json")
    }

    assert shipped == {example.filename for example in EXAMPLES}
