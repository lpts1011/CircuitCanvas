def test_main_window_adds_repeated_components_and_updates_summary(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")
    window.add_component("capacitor")
    window.add_component("inductor")
    window.add_component("resistor")

    qtbot.waitUntil(lambda: "Total current" in window.summary_label.text(), timeout=3000)

    assert len(window.circuit.components) == 4
    assert "Total power" in window.summary_label.text()
    assert "Circuit valid" in window.status_label.text()


def test_undo_and_redo_restore_component(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")
    assert len(window.circuit.components) == 1

    window.undo()
    assert len(window.circuit.components) == 0
    window.redo()
    assert len(window.circuit.components) == 1


def test_toolbar_rotates_and_deletes_selected_component(qtbot) -> None:
    from PySide6.QtCore import QPointF

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.scene.insert_component_at("resistor", QPointF(420.0, 260.0))

    window.rotate_action.trigger()
    assert window.circuit.rotations[component_id] == 90

    window.delete_action.trigger()
    assert component_id not in window.circuit.components


def test_main_window_starts_and_resets_to_construction_loop(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)

    assert window.circuit.components == {}
    assert len(window.circuit.wires) == 3
    window.add_component("resistor")
    assert len(window.circuit.components) == 1

    window.reset_circuit()

    assert window.circuit.components == {}
    assert len(window.circuit.wires) == 3


def test_starter_short_gives_component_insertion_instruction(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)

    qtbot.waitUntil(lambda: "place a component on a wire" in window.status_label.text().lower())


def test_parallel_helper_creates_a_wired_parallel_branch(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    first = window.add_component("resistor")

    window._duplicate_parallel(first)

    qtbot.waitUntil(lambda: "Circuit valid" in window.status_label.text(), timeout=3000)
    snapshot = window.circuit.snapshot()
    components = {component.id: component for component in snapshot.components}
    assert len(components) == 2
    assert components[first].endpoints == components["R2"].endpoints
