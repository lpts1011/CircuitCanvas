from PySide6.QtCore import QPointF
from PySide6.QtTest import QSignalSpy

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef
from circuitcanvas.solver.equations import EquationLine
from circuitcanvas.solver.transient import simulate
from circuitcanvas.ui.circuit_scene import CircuitScene


def test_scene_starts_with_battery_and_open_drop_target(qtbot) -> None:
    scene = CircuitScene(Circuit.new(12.0))

    assert scene.battery_item is not None
    assert scene.open_target is not None
    assert scene.component_items == {}


def test_scene_accepts_more_than_one_component_of_each_kind(qtbot) -> None:
    scene = CircuitScene(Circuit.new(12.0))
    ids = [
        scene.insert_component_for_test(kind)
        for kind in ("resistor", "resistor", "capacitor", "inductor", "capacitor")
    ]

    assert len(scene.circuit.components) == 5
    assert set(scene.component_items) == set(ids)


def test_parallel_drop_reuses_selected_component_endpoints(qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    resistor = scene.insert_component_for_test("resistor")
    capacitor = scene.insert_component_for_test("capacitor", parallel_to=resistor)

    assert (
        scene.circuit.components[resistor].endpoints
        == scene.circuit.components[capacitor].endpoints
    )


def test_result_updates_component_annotation(qtbot) -> None:
    scene = CircuitScene(Circuit.new(10.0))
    resistor = scene.insert_component_for_test("resistor")
    result = simulate(scene.circuit.snapshot())

    scene.set_result(result, len(result.time) - 1)

    assert "10.000 V" in scene.component_items[resistor].measurement_text
    assert "A" in scene.component_items[resistor].measurement_text


def test_canvas_expands_for_many_series_and_parallel_components(qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    first = scene.insert_component_for_test("resistor")
    for _ in range(8):
        scene.insert_component_for_test("resistor")
    for _ in range(5):
        scene.insert_component_for_test("capacitor", parallel_to=first)

    item_bounds = scene.itemsBoundingRect()

    assert scene.sceneRect().right() > item_bounds.right()
    assert scene.sceneRect().bottom() > item_bounds.bottom()


def test_free_component_keeps_drop_position_and_exposes_terminals(qtbot) -> None:
    scene = CircuitScene(Circuit.new())

    component_id = scene.insert_component_at("resistor", QPointF(410.0, 280.0))
    item = scene.component_items[component_id]

    assert item.pos() == QPointF(410.0, 280.0)
    assert set(item.terminals) == {"a", "b"}
    assert scene.circuit.positions[component_id] == (410.0, 280.0)


def test_scene_connects_arbitrary_component_terminals(qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    r1 = scene.insert_component_at("resistor", QPointF(360.0, 180.0))
    r2 = scene.insert_component_at("resistor", QPointF(580.0, 300.0))

    wire_id = scene.connect_for_test(TerminalRef(r1, "b"), TerminalRef(r2, "a"))

    assert wire_id in scene.wire_items
    assert scene.circuit.wires[wire_id].start == TerminalRef(r1, "b")
    assert scene.circuit.wires[wire_id].end == TerminalRef(r2, "a")
    assert len(scene.circuit.wires[wire_id].route) == 2
    assert len(scene.route_handle_items) == 2


def test_equation_highlight_does_not_retrigger_component_navigation(qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    resistor = scene.insert_component_at("resistor", QPointF(360.0, 180.0))
    spy = QSignalSpy(scene.selection_changed)
    line = EquationLine("KVL1", "kvl", "V_R1 = 0", "0 = 0", "residual = 0", 0.0, (resistor,), ())

    scene.highlight_equation(line)

    assert scene.component_items[resistor].isSelected()
    assert spy.count() == 0


def test_junction_dot_is_a_wire_start_and_end_target(qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    resistor = scene.insert_component_at("resistor", QPointF(360.0, 180.0))
    junction_id, _ = scene.command_stack.connect_to_new_junction(
        TerminalRef(resistor, "b"), (560.0, 260.0)
    )
    scene.rebuild()

    assert scene._endpoint_for_item(scene.junction_items[junction_id]) == JunctionRef(junction_id)
