"""Rebuild the example circuits in src/circuitcanvas/examples/.

Run from the repository root after changing how circuits are laid out:

    python scripts/make_examples.py

Each example is built with the same edits the app makes, so it looks exactly like
a circuit a user could have drawn: components evenly spaced on the battery loop,
and no wire hidden underneath a component.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.serialization import save_circuit
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef
from circuitcanvas.ui.circuit_scene import CircuitScene

TARGET = Path("src/circuitcanvas/examples")

#: The top and bottom wires of the starter loop, and the clear span between the
#: battery and the right-hand corner.
TOP, BOTTOM = 290.0, 430.0
LEFT, RIGHT = 234.0, 950.0

type Part = tuple[str, float]


def _spread(count: int) -> list[float]:
    """Evenly spaced x positions for ``count`` components on one wire of the loop."""
    return [LEFT + (RIGHT - LEFT) * (index + 0.5) / count for index in range(count)]


def build_loop(voltage: float, top: list[Part], bottom: list[Part]) -> CircuitScene:
    """A single loop: ``top`` components left to right, then ``bottom`` ones on the way back."""
    scene = CircuitScene(Circuit.starter_loop(voltage))
    for y, parts in ((TOP, top), (BOTTOM, bottom)):
        for x, (kind, value) in zip(_spread(len(parts)), parts, strict=True):
            component_id = scene.place_component(kind, QPointF(x, y))
            scene.command_stack.update_value(component_id, value)
    return scene


def build_series_parallel() -> CircuitScene:
    """Two 100 Ω resistors in series, with a 200 Ω resistor across both of them."""
    scene = build_loop(17.0, [("resistor", 100.0), ("resistor", 100.0)], [])
    stack = scene.command_stack

    def junction_on_top_wire(x: float) -> JunctionRef:
        target = scene.nearest_wire(QPointF(x, TOP), 1.0)
        assert target is not None
        return JunctionRef(scene.split_wire_at(target[0], QPointF(x, TOP)))

    left = junction_on_top_wire(270.0)
    right = junction_on_top_wire(914.0)
    upper = TOP - CircuitScene.PARALLEL_STEP[0]
    bypass = stack.add_loose_component("resistor", 200.0, ((LEFT + RIGHT) / 2, upper))
    stack.connect(left, TerminalRef(bypass, "a"), ((270.0, upper),))
    stack.connect(TerminalRef(bypass, "b"), right, ((914.0, upper),))
    scene.rebuild()
    return scene


def main() -> int:
    app = QApplication([])
    examples = {
        "resistor.json": build_loop(12.0, [("resistor", 100.0)], []),
        "parallel-series-17v.json": build_series_parallel(),
        "rc-charge.json": build_loop(5.0, [("resistor", 1000.0)], [("capacitor", 10e-6)]),
        "rl-step.json": build_loop(5.0, [("resistor", 10.0)], [("inductor", 0.1)]),
        "rlc-underdamped.json": build_loop(
            10.0, [("resistor", 10.0), ("inductor", 0.05)], [("capacitor", 100e-6)]
        ),
    }
    for filename, scene in examples.items():
        save_circuit(TARGET / filename, scene.circuit)
        print(f"Saved {TARGET / filename}")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
