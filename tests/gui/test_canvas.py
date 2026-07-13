from circuitcanvas.domain.circuit import Circuit
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

    assert scene.circuit.components[resistor].endpoints == scene.circuit.components[capacitor].endpoints


def test_result_updates_component_annotation(qtbot) -> None:
    scene = CircuitScene(Circuit.new(10.0))
    resistor = scene.insert_component_for_test("resistor")
    result = simulate(scene.circuit.snapshot())

    scene.set_result(result, len(result.time) - 1)

    assert "10.000 V" in scene.component_items[resistor].measurement_text
    assert "A" in scene.component_items[resistor].measurement_text
