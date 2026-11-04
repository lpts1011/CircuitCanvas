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

    qtbot.waitUntil(lambda: window.current_result is not None, timeout=3000)

    assert len(window.circuit.components) == 4
    assert window.details.component_count.value.text() == "4"
    assert window.details.battery_current.value.text().endswith("A")
    assert "Circuit solved" in window.status_label.text()


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

    qtbot.waitUntil(lambda: "add a component to the loop" in window.status_label.text().lower())


def test_parallel_helper_creates_a_wired_parallel_branch(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    first = window.add_component("resistor")

    window._duplicate_parallel(first)

    qtbot.waitUntil(lambda: "Circuit solved" in window.status_label.text(), timeout=3000)
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
    assert window.inspector.editor.isHidden()
    assert not window.inspector.empty_hint.isHidden()


def test_value_edit_keeps_component_selected_in_inspector(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")

    window._update_value(component_id, 470.0)

    assert window.inspector.component is not None
    assert window.inspector.component.value == 470.0
    assert not window.inspector.editor.isHidden()


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


def test_new_results_do_not_change_the_users_selection(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    first = window.add_component("resistor")
    second = window.add_component("resistor")
    window.scene.clearSelection()
    window.scene.component_items[first].setSelected(True)

    window._update_value(first, 220.0)
    qtbot.waitUntil(lambda: window.equations.current_line() is not None, timeout=3000)

    selected = [
        item.component.id for item in window.scene.component_items.values() if item.isSelected()
    ]
    assert selected == [first]
    assert not window.scene.component_items[second].highlighted


def test_equation_outline_only_shows_on_the_equations_tab(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    qtbot.waitUntil(lambda: window.equations.current_line() is not None, timeout=3000)
    item = window.scene.component_items[component_id]
    assert not item.highlighted

    window.sidebar_tabs.setCurrentWidget(window.equations)
    window.equations.select_equation("LAW-" + component_id)
    assert item.highlighted

    window.sidebar_tabs.setCurrentWidget(window.details)
    assert not item.highlighted


def test_slow_rc_circuit_gets_a_long_enough_time_span(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    resistor = window.add_component("resistor")
    capacitor = window.add_component("capacitor")
    window._update_value(resistor, 10e3)
    window._update_value(capacitor, 1e-3)

    qtbot.waitUntil(
        lambda: window.current_result is not None and window.current_result.time[-1] > 1,
        timeout=3000,
    )

    assert window.analysis.span_edit.text() == "50 s"
    assert window.analysis.span_auto.isChecked()


def test_manual_time_span_is_undoable(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")
    window.add_component("capacitor")

    window._use_manual_span(0.2)
    assert not window.circuit.settings.auto_duration
    assert window.circuit.settings.duration == 0.2

    window.undo()

    assert window.circuit.settings.auto_duration
    assert window.analysis.span_auto.isChecked()


def test_double_clicking_a_component_opens_its_value_for_editing(qtbot) -> None:
    from PySide6.QtCore import QPointF

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    component_id = window.add_component("resistor")
    window.sidebar_tabs.setCurrentWidget(window.equations)
    window.scene.clearSelection()
    item = window.scene.component_items[component_id]
    window.view.centerOn(item)
    qtbot.wait(20)
    point = window.view.mapFromScene(item.scenePos() + QPointF(0, -30))

    with qtbot.waitSignal(window.scene.component_activated) as signal:
        qtbot.mouseDClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)

    assert signal.args == [component_id]
    assert window.sidebar_tabs.currentWidget() is window.details
    assert window.scene.selected_component_id() == component_id
    assert window.inspector.value_edit.selectedText() == window.inspector.value_edit.text()


def test_palette_stays_visible_next_to_the_inspector(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    window.add_component("resistor")

    assert window.component_palette.isVisible()
    assert window.sidebar_tabs.currentWidget() is window.details


def test_export_csv_without_selection_saves_every_component(qtbot, monkeypatch, tmp_path) -> None:
    from PySide6.QtWidgets import QFileDialog

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.add_component("resistor")
    window.add_component("capacitor")
    qtbot.waitUntil(lambda: window.current_result is not None, timeout=3000)
    window.scene.clearSelection()
    target = tmp_path / "all.csv"
    suggested: list[str] = []

    def fake_dialog(parent, caption, name, filters):
        suggested.append(name)
        return str(target), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fake_dialog))

    window.export_csv()

    assert suggested == ["circuit-data.csv"]
    header = target.read_text(encoding="utf-8").splitlines()[0]
    assert "R1_voltage_v" in header and "C1_current_a" in header


def test_adding_a_component_selects_only_the_new_one(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    first = window.add_component("resistor")
    second = window.add_component("capacitor")

    selected = [
        item.component.id for item in window.scene.component_items.values() if item.isSelected()
    ]
    assert selected == [second]
    assert window.inspector.component is not None
    assert window.inspector.component.id == second

    window.delete_action.trigger()
    assert first in window.circuit.components
    assert second not in window.circuit.components


def test_readme_quick_start_edits_the_double_clicked_resistor(qtbot) -> None:
    import pytest

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    resistor = window.add_component("resistor")
    capacitor = window.add_component("capacitor")

    window.edit_component(resistor)
    window.inspector.value_edit.setText("10k")
    window.inspector.value_edit.editingFinished.emit()

    assert window.circuit.components[resistor].value == pytest.approx(10e3)
    assert window.circuit.components[capacitor].value == pytest.approx(47e-6)


def test_window_opens_no_larger_than_the_screen(qtbot) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    available = window.screen().availableGeometry()

    assert window.width() <= max(window.minimumWidth(), available.width())
    assert window.height() <= max(window.minimumHeight(), available.height())
