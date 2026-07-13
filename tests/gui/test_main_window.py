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
