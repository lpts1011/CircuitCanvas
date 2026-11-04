import pytest
from PySide6.QtCore import Qt


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


@pytest.mark.parametrize("key", [Qt.Key.Key_Backspace, Qt.Key.Key_Delete])
def test_keyboard_delete_keys_remove_selected_component(qtbot, key: Qt.Key) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.wait(20)
    component_id = window.add_component("resistor")
    window.scene.component_items[component_id].setSelected(True)
    window.view.setFocus()

    qtbot.keyClick(window.view, key)

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


def test_inspector_rotate_button_rotates_component(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    before = window.circuit.rotations[component_id]

    window.inspector.rotate_button.click()

    assert window.circuit.rotations[component_id] == (before + 90) % 360
    assert window.scene.selected_component_id() == component_id


def test_deselecting_clears_the_inspector(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    assert window.inspector.component is not None
    assert window.inspector.component.id == component_id

    window.scene.clearSelection()

    assert window.inspector.component is None
    assert not window.inspector.isEnabled()


def test_value_edit_keeps_component_selected_in_inspector(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")

    window._update_value(component_id, 470.0)

    assert window.inspector.component is not None
    assert window.inspector.component.value == 470.0
    assert window.inspector.isEnabled()


def test_slider_drag_is_one_undo_step(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    original = window.circuit.components[component_id].value
    slider = window.inspector.slider

    slider.sliderPressed.emit()
    for _ in range(40):
        slider.setValue(slider.value() + 5)
    assert window.circuit.components[component_id].value != original

    window.undo()

    assert window.circuit.components[component_id].value == pytest.approx(original)
    window.undo()
    assert component_id not in window.circuit.components


def test_battery_voltage_edit_is_undoable(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")

    window.source_voltage.setValue(1.0)
    window.source_voltage.setValue(17.0)
    window.source_voltage.editingFinished.emit()
    assert window.circuit.source.voltage == 17.0

    window.undo()

    assert window.circuit.source.voltage == 12.0
    assert window.source_voltage.value() == 12.0


def test_delete_action_removes_selected_wire_and_junction(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)

    window.scene.wire_items["W2"].setSelected(True)
    window.delete_action.trigger()
    assert "W2" not in window.circuit.wires

    window.scene.junction_items["J1"].setSelected(True)
    window.delete_action.trigger()
    assert "J1" not in window.circuit.junctions
    assert "W1" not in window.circuit.wires

    window.undo()
    window.undo()
    assert {"W1", "W2", "W3"} <= set(window.circuit.wires)


def test_title_marks_unsaved_changes(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    assert window.windowTitle().startswith("Untitled")
    assert not window.isWindowModified()

    window.add_component("resistor")
    assert window.isWindowModified()

    window.undo()
    assert not window.isWindowModified()


def test_new_keeps_circuit_when_user_cancels_unsaved_prompt(qtbot, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    monkeypatch.setattr(window, "_ask_save_changes", lambda: QMessageBox.StandardButton.Cancel)

    window.reset_circuit()

    assert component_id in window.circuit.components


def test_save_writes_file_marks_clean_and_names_window(qtbot, monkeypatch, tmp_path) -> None:
    from PySide6.QtWidgets import QFileDialog

    from circuitcanvas.domain.serialization import load_circuit
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    target = tmp_path / "my-loop"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *args, **kwargs: (str(target), ""))
    )

    assert window.save_file()

    saved = tmp_path / "my-loop.circuitcanvas"
    assert component_id in load_circuit(saved).components
    assert not window.isWindowModified()
    assert window.windowTitle().startswith("my-loop.circuitcanvas")


def test_save_failure_is_reported_instead_of_crashing(qtbot, monkeypatch, tmp_path) -> None:
    from PySide6.QtWidgets import QMessageBox

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda parent, title, text: warnings.append(title))
    )
    window._current_path = tmp_path / "missing-folder" / "circuit.circuitcanvas"

    assert not window.save_file()

    assert warnings == ["Could not save circuit"]
    assert window.isWindowModified()
