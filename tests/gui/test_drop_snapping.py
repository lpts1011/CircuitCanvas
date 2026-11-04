from PySide6.QtCore import QPointF

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.wiring import TerminalRef
from circuitcanvas.ui.circuit_scene import CircuitScene

BOTTOM_WIRE_Y = 430.0


def _wired(scene: CircuitScene, component_id: str) -> bool:
    terminals = {TerminalRef(component_id, "a"), TerminalRef(component_id, "b")}
    return all(
        any(terminal in (wire.start, wire.end) for wire in scene.circuit.wires.values())
        for terminal in terminals
    )


def test_drop_a_little_off_the_wire_still_inserts_into_it(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())

    component_id = scene.place_component("capacitor", QPointF(545.0, BOTTOM_WIRE_Y - 20.0))

    assert _wired(scene, component_id)
    assert scene.circuit.positions[component_id] == (545.0, BOTTOM_WIRE_Y)


def test_drop_far_from_any_wire_stays_loose(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())

    component_id = scene.place_component("capacitor", QPointF(545.0, 640.0))

    assert scene.is_unwired(component_id)


def test_dragging_a_loose_component_onto_a_wire_connects_it(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    scene.place_component("resistor", QPointF(545.0, 290.0))
    loose = scene.insert_component_at("capacitor", QPointF(545.0, 640.0))
    scene.command_stack.update_value(loose, 1e-3)
    scene.rebuild()

    # The user drags it so it overlaps the bottom wire, 15 px off.
    scene._component_moved(loose, 560.0, BOTTOM_WIRE_Y + 15.0)

    assert _wired(scene, loose)
    assert scene.circuit.components[loose].value == 1e-3
    assert scene.circuit.positions[loose] == (560.0, BOTTOM_WIRE_Y)
    assert scene.selected_component_id() == loose

    assert scene.command_stack.undo()
    assert scene.is_unwired(loose)


def test_loose_component_drag_lights_up_the_target_wire(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    loose = scene.insert_component_at("capacitor", QPointF(545.0, 640.0))
    item = scene.component_items[loose]

    item.setPos(545.0, BOTTOM_WIRE_Y + 10.0)

    assert sum(wire.drop_target for wire in scene.wire_items.values()) == 1
    item.setPos(545.0, 700.0)
    assert not any(wire.drop_target for wire in scene.wire_items.values())


def test_clicking_a_component_is_not_an_edit(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    component_id = scene.place_component("resistor", QPointF(545.0, 290.0))
    scene.command_stack.mark_clean()
    x, y = scene.circuit.positions[component_id]

    scene._component_moved(component_id, x, y)

    assert scene.command_stack.is_clean
