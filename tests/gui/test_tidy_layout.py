"""Circuits the app lays out itself stay readable: nothing overlaps, no wire hides."""

import pytest
from PySide6.QtCore import QRectF

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.examples import EXAMPLES, Example, load_example
from circuitcanvas.solver.validation import validate
from circuitcanvas.ui.circuit_scene import CircuitScene
from circuitcanvas.ui.main_window import MainWindow


def _cards(scene: CircuitScene) -> dict[str, QRectF]:
    cards = {name: item.sceneBoundingRect() for name, item in scene.component_items.items()}
    assert scene.battery_item is not None
    cards["battery"] = scene.battery_item.sceneBoundingRect()
    return cards


def overlapping_cards(scene: CircuitScene) -> list[tuple[str, str]]:
    cards = sorted(_cards(scene).items())
    return [
        (first, second)
        for index, (first, first_rect) in enumerate(cards)
        for second, second_rect in cards[index + 1 :]
        if first_rect.intersects(second_rect)
    ]


def wires_under_cards(scene: CircuitScene) -> list[tuple[str, str]]:
    """Wires that run through the inside of a component card (the battery draws its own)."""
    hidden = []
    for name, rect in scene.component_items.items():
        inside = rect.sceneBoundingRect().adjusted(6, 6, -6, -6)
        for wire_id, item in scene.wire_items.items():
            points = item.polyline_points()
            for start, end in zip(points, points[1:], strict=False):
                if (
                    QRectF(start, end)
                    .normalized()
                    .adjusted(-0.5, -0.5, 0.5, 0.5)
                    .intersects(inside)
                ):
                    hidden.append((wire_id, name))
    return hidden


def test_clicking_add_many_times_never_stacks_components(qtbot) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)

    for kind in ("resistor", "capacitor", "inductor") * 4:
        window.add_component(kind)
        assert overlapping_cards(window.scene) == []
        assert wires_under_cards(window.scene) == []
        assert validate(window.circuit.snapshot()) == ()

    assert len(window.circuit.components) == 12


def test_a_crowded_loop_grows_and_one_undo_takes_both_back(qtbot) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    for _ in range(6):
        window.add_component("resistor")
    corner_before = window.circuit.junctions["J1"].position
    positions_before = dict(window.circuit.positions)

    window.add_component("resistor")

    assert window.circuit.junctions["J1"].position[0] > corner_before[0]  # the loop got wider
    window.undo()
    assert len(window.circuit.components) == 6
    assert window.circuit.junctions["J1"].position == corner_before
    assert window.circuit.positions == positions_before


def test_the_whole_circuit_stays_in_view_as_it_grows(qtbot) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.resize(1100, 700)
    window.show()
    qtbot.waitExposed(window)

    for _ in range(9):
        window.add_component("resistor")
    window._duplicate_parallel("R1")
    window._duplicate_parallel("R1")

    visible = window.view.mapToScene(window.view.viewport().rect()).boundingRect()
    for name, rect in _cards(window.scene).items():
        assert visible.contains(rect), f"{name} is partly off screen"


def test_inserted_components_face_along_their_wire(qtbot) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)

    top = window.add_component("resistor")
    bottom = window.add_component("capacitor")

    # The bottom wire runs right to left, so the capacitor is turned to match:
    # each wire then reaches the nearer end instead of passing underneath.
    assert window.circuit.rotations[top] == 0
    assert window.circuit.rotations[bottom] == 180
    assert window.circuit.positions[top][0] == window.circuit.positions[bottom][0]


def test_parallel_copies_stack_on_empty_canvas(qtbot) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")
    window.add_component("capacitor")  # sits directly below R1 on the bottom wire

    window._duplicate_parallel("R1")
    window._duplicate_parallel("R1")
    window._duplicate_parallel("C1")

    scene = window.scene
    assert overlapping_cards(scene) == []
    assert wires_under_cards(scene) == []
    assert validate(window.circuit.snapshot()) == ()
    # No copy lies on top of a wire it is not part of (it would look like a series part).
    for name, item in scene.component_items.items():
        own = {
            wire_id
            for wire_id, wire in scene.circuit.wires.items()
            if any(getattr(end, "owner_id", None) == name for end in (wire.start, wire.end))
        }
        card = item.sceneBoundingRect().adjusted(2, 2, -2, -2)
        for wire_id, wire_item in scene.wire_items.items():
            if wire_id in own:
                continue
            points = wire_item.polyline_points()
            for start, end in zip(points, points[1:], strict=False):
                assert (
                    not QRectF(start, end)
                    .normalized()
                    .adjusted(-0.5, -0.5, 0.5, 0.5)
                    .intersects(card)
                ), f"{wire_id} runs behind {name}"
    # All three resistors share the same two ends.
    snapshot = {c.id: c for c in window.circuit.snapshot().components}
    assert {frozenset(snapshot[name].endpoints) for name in ("R1", "R2", "R3")} == {
        frozenset(snapshot["R1"].endpoints)
    }


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.filename)
def test_bundled_examples_are_drawn_tidily(qtbot, example: Example) -> None:
    scene = CircuitScene(load_example(example))

    assert overlapping_cards(scene) == []
    assert wires_under_cards(scene) == []


def test_starter_loop_has_room_for_six_components_before_it_grows(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    corner = scene.circuit.junctions["J1"].position

    for _ in range(6):
        scene.add_component_in_series("resistor")

    assert scene.circuit.junctions["J1"].position == corner
    assert overlapping_cards(scene) == []
