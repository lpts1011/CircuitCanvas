"""Ready-to-open example circuits shipped inside the package."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.serialization import CircuitFileError, circuit_from_dict


@dataclass(frozen=True, slots=True)
class Example:
    filename: str
    title: str
    description: str


EXAMPLES: tuple[Example, ...] = (
    Example(
        "resistor.json",
        "Ohm's law: one resistor",
        "A 100 Ω resistor on a 12 V battery. The current is simply V / R.",
    ),
    Example(
        "parallel-series-17v.json",
        "Series and parallel resistors",
        "A 200 Ω resistor in parallel with two 100 Ω resistors in series, on 17 V.",
    ),
    Example(
        "rc-charge.json",
        "RC charging",
        "A capacitor charges through a resistor. Time constant τ = RC = 10 ms.",
    ),
    Example(
        "rl-step.json",
        "RL current rise",
        "Inductor current rises toward V / R. Time constant τ = L / R = 10 ms.",
    ),
    Example(
        "rlc-underdamped.json",
        "RLC ringing (underdamped)",
        "Energy swings between L and C while the resistor slowly damps the oscillation.",
    ),
)


def load_example(example: Example) -> Circuit:
    """Load an example from the installed package (works in the bundled app too)."""
    resource = files(__name__).joinpath(example.filename)
    try:
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CircuitFileError(f"Could not read example {example.filename}: {exc}") from exc
    return circuit_from_dict(payload)
