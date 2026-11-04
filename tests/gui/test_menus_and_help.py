from circuitcanvas.examples import EXAMPLES


def _window(qtbot):
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    return window


def test_menu_bar_has_standard_menus_and_every_example(qtbot) -> None:
    window = _window(qtbot)

    titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
    example_titles = [action.text() for action in window.examples_menu.actions()]

    assert titles == ["File", "Edit", "View", "Help"]
    assert example_titles == [example.title for example in EXAMPLES]


def test_opening_an_example_gives_an_untitled_clean_copy(qtbot) -> None:
    window = _window(qtbot)
    example = next(item for item in EXAMPLES if item.filename == "rc-charge.json")

    assert window.open_example(example)

    assert set(window.circuit.components) == {"R1", "C1"}
    assert window._current_path is None
    assert window.windowTitle().startswith("RC charging (example)")
    assert not window.has_unsaved_changes
    qtbot.waitUntil(lambda: "Circuit valid" in window.status_label.text(), timeout=3000)


def test_toolbar_labels_stay_short_while_menus_use_ellipses(qtbot) -> None:
    window = _window(qtbot)

    assert window.open_action.text() == "Open…"
    assert window.open_action.iconText() == "Open"


def test_help_windows_open_without_blocking(qtbot) -> None:
    window = _window(qtbot)

    guide = window.show_quick_start()
    assert guide.isVisible()
    assert "Build your first circuit" in guide.browser.toPlainText()

    shortcuts = window.show_shortcuts()
    text = shortcuts.browser.toPlainText()
    assert "Undo" in text
    assert "Double-click a component" in text
    assert not guide.isVisible()

    about = window.show_about()
    assert "MIT License" in about.browser.toPlainText()


def test_opening_another_circuit_does_not_keep_a_selection_by_id(qtbot) -> None:
    window = _window(qtbot)
    resistor = window.add_component("resistor")
    assert window.scene.selected_component_id() == resistor
    window.scene.command_stack.mark_clean()

    window.open_example(next(item for item in EXAMPLES if item.filename == "rc-charge.json"))

    assert window.scene.selected_component_id() is None
    assert window.inspector.component is None
