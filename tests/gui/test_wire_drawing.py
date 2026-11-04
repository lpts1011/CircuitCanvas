from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef
from circuitcanvas.ui.circuit_scene import CircuitScene


def _scene_with_loose_capacitor() -> tuple[CircuitScene, str]:
    scene = CircuitScene(Circuit.starter_loop())
    scene.place_component("resistor", QPointF(545.0, 290.0))
    loose = scene.insert_component_at("capacitor", QPointF(600.0, 600.0))
    return scene, loose


def _dot(scene: CircuitScene, owner: str, terminal: str) -> QPointF:
    return scene.component_items[owner].terminals[terminal].scenePos()


def test_preview_follows_the_pointer_in_empty_space(qtbot) -> None:
    scene, loose = _scene_with_loose_capacitor()
    scene.begin_wire(TerminalRef(loose, "a"))

    scene.update_wire_drag(QPointF(380.0, 520.0))

    assert scene._wire_target is None
    path = scene._wire_preview.path()
    end = path.elementAt(path.elementCount() - 1)
    assert (end.x, end.y) == (380.0, 520.0)


def test_release_near_a_dot_connects_to_it(qtbot) -> None:
    scene, loose = _scene_with_loose_capacitor()
    target = _dot(scene, "R1", "a")
    scene.begin_wire(TerminalRef(loose, "a"))

    scene.update_wire_drag(target + QPointF(-14.0, 16.0))
    assert scene.component_items["R1"].terminals["a"].targeted

    assert scene.finish_wire(target + QPointF(-14.0, 16.0))
    assert any(
        {wire.start, wire.end} == {TerminalRef(loose, "a"), TerminalRef("R1", "a")}
        for wire in scene.circuit.wires.values()
    )
    assert not scene.drawing_wire


def test_release_near_a_wire_adds_a_junction_in_one_undo_step(qtbot) -> None:
    scene, loose = _scene_with_loose_capacitor()
    steps = scene.command_stack._index
    scene.begin_wire(TerminalRef(loose, "a"))

    assert scene.finish_wire(QPointF(330.0, 430.0 + 10.0))

    junctions = [
        wire.end
        for wire in scene.circuit.wires.values()
        if wire.start == TerminalRef(loose, "a") and isinstance(wire.end, JunctionRef)
    ]
    assert len(junctions) == 1
    assert scene.command_stack._index == steps + 1
    assert scene.command_stack.undo()
    assert scene.is_unwired(loose)


def test_release_in_empty_space_adds_nothing_and_explains(qtbot) -> None:
    scene, loose = _scene_with_loose_capacitor()
    wires = dict(scene.circuit.wires)
    hints: list[str] = []
    scene.hint_requested.connect(hints.append)
    scene.begin_wire(TerminalRef(loose, "a"))

    assert not scene.finish_wire(QPointF(380.0, 700.0))

    assert scene.circuit.wires == wires
    assert hints and "Release on a dot or a wire" in hints[0]


def test_wire_heading_backwards_steps_out_of_its_component_first(qtbot) -> None:
    scene, loose = _scene_with_loose_capacitor()
    start = _dot(scene, loose, "b")  # right-hand end, pointing +x
    target = QPointF(start.x() - 300.0, start.y() - 200.0)

    route = scene.wire_route(TerminalRef(loose, "b"), start, target)

    assert route[0] == (start.x() + scene.WIRE_STUB, start.y())
    assert all(x > start.x() for x, _y in route)


def test_wire_heading_forwards_uses_one_bend(qtbot) -> None:
    scene, loose = _scene_with_loose_capacitor()
    start = _dot(scene, loose, "b")

    route = scene.wire_route(TerminalRef(loose, "b"), start, start + QPointF(200.0, -150.0))

    assert route == ((start.x() + 200.0, start.y()),)


def test_real_mouse_drag_from_beside_a_dot_to_beside_another(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.add_component("resistor")
    loose = window.scene.insert_component_at("capacitor", QPointF(600.0, 600.0))
    window.view.fit_circuit()
    qtbot.wait(20)
    viewport = window.view.viewport()
    start = window.view.mapFromScene(_dot(window.scene, loose, "a") + QPointF(5.0, 5.0))
    end = window.view.mapFromScene(_dot(window.scene, "R1", "a") + QPointF(-8.0, 10.0))

    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(viewport, end)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)

    assert any(
        {wire.start, wire.end} == {TerminalRef(loose, "a"), TerminalRef("R1", "a")}
        for wire in window.scene.circuit.wires.values()
    )


def test_escape_cancels_a_wire_being_drawn(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    loose = window.scene.insert_component_at("capacitor", QPointF(600.0, 600.0))
    window.scene.begin_wire(TerminalRef(loose, "a"))

    window.deselect_action.trigger()

    assert not window.scene.drawing_wire
    assert window.scene._wire_preview is None
