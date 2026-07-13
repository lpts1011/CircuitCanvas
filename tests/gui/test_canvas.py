import pytest
from PySide6.QtCore import QPointF
from PySide6.QtTest import QSignalSpy

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef
from circuitcanvas.solver.equations import EquationLine
from circuitcanvas.solver.transient import simulate
from circuitcanvas.ui.circuit_scene import CircuitScene
from circuitcanvas.ui.routing import is_octilinear


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
    assert len(scene.circuit.wires[wire_id].route) == 1
    assert len(scene.route_handle_items) == 1


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


def test_route_handle_move_is_projected_back_to_its_wire(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    scene.command_stack.set_wire_route("W1", ((500.0, 290.0),))
    scene.rebuild()

    scene._route_moved("W1", 0, 410.0, 337.0)

    assert scene.circuit.wires["W1"].route[0] == pytest.approx((410.0, 290.0))


def test_junction_move_is_projected_onto_an_incident_wire(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())

    scene._junction_moved("J1", 850.0, 360.0)

    assert scene.circuit.junctions["J1"].position == pytest.approx((850.0, 290.0))


def test_component_inserted_on_wire_replaces_the_conductive_span(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop(12.0))

    component_id = scene.insert_component_on_wire("resistor", "W1", QPointF(520.0, 290.0))

    assert "W1" not in scene.circuit.wires
    assert scene.circuit.positions[component_id] == pytest.approx((520.0, 290.0))
    assert scene.circuit.rotations[component_id] == 0
    assert simulate(scene.circuit.snapshot()).branches[component_id].voltage[-1] == pytest.approx(
        12.0
    )


def test_component_inserted_on_vertical_wire_rotates_90_degrees(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop(12.0))

    component_id = scene.insert_component_on_wire("resistor", "W2", QPointF(980.0, 360.0))

    assert scene.circuit.rotations[component_id] == 90
    assert all(
        is_octilinear(
            (left.x(), left.y()),
            (right.x(), right.y()),
        )
        for item in scene.wire_items.values()
        for left, right in zip(item.polyline_points(), item.polyline_points()[1:], strict=False)
    )


def test_free_wire_endpoint_snaps_to_nearest_allowed_direction(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())

    snapped = scene._snapped_endpoint(QPointF(0.0, 0.0), QPointF(20.0, 7.0))

    assert snapped == QPointF(20.0, 0.0)


def test_new_route_handle_is_projected_onto_wire(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())

    scene.add_route_handle_at("W1", QPointF(410.0, 337.0))

    assert scene.circuit.wires["W1"].route[-1] == pytest.approx((410.0, 290.0))


def test_placing_component_on_visible_wire_inserts_it_in_series(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())

    component_id = scene.place_component("resistor", QPointF(520.0, 290.0))

    assert "W1" not in scene.circuit.wires
    assert component_id in scene.circuit.components


def test_inserting_on_a_bent_wire_preserves_routes_before_and_after_component(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    scene.command_stack.set_wire_route("W1", ((400.0, 290.0), (400.0, 350.0), (700.0, 350.0)))
    scene.rebuild()

    component_id = scene.insert_component_on_wire("resistor", "W1", QPointF(550.0, 350.0))

    start_wire = next(
        wire for wire in scene.circuit.wires.values() if wire.start == TerminalRef("V1", "a")
    )
    end_wire = next(wire for wire in scene.circuit.wires.values() if wire.end == JunctionRef("J1"))
    assert component_id in scene.circuit.components
    assert start_wire.route == ((400.0, 290.0), (400.0, 350.0))
    assert end_wire.route[0] == (700.0, 350.0)


def test_adding_handle_to_bent_wire_keeps_path_order(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    scene.command_stack.set_wire_route("W1", ((400.0, 290.0), (400.0, 350.0), (700.0, 350.0)))
    scene.rebuild()

    scene.add_route_handle_at("W1", QPointF(412.0, 320.0))

    assert scene.circuit.wires["W1"].route[:3] == (
        (400.0, 290.0),
        (400.0, 320.0),
        (400.0, 350.0),
    )


def test_splitting_bent_wire_keeps_junction_and_bends_on_original_path(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    scene.command_stack.set_wire_route("W1", ((400.0, 290.0), (400.0, 350.0), (700.0, 350.0)))
    scene.rebuild()

    junction_id = scene.split_wire_at("W1", QPointF(412.0, 320.0))

    second = next(
        wire for wire in scene.circuit.wires.values() if wire.start == JunctionRef(junction_id)
    )
    assert scene.circuit.junctions[junction_id].position == (400.0, 320.0)
    assert scene.circuit.wires["W1"].route == ((400.0, 290.0),)
    assert second.route[:2] == ((400.0, 350.0), (700.0, 350.0))
