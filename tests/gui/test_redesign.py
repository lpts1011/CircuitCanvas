import pytest
from PySide6.QtCore import QPointF

from circuitcanvas.ui.formatting import format_si


def _window(qtbot):
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    return window


def _solved(qtbot, window) -> None:
    qtbot.waitUntil(lambda: window.current_result is not None, timeout=3000)


def test_details_panel_shows_overview_then_the_selected_component(qtbot) -> None:
    window = _window(qtbot)
    resistor = window.add_component("resistor")
    _solved(qtbot, window)

    assert window.details.showing_component
    assert window.details.component_name.text() == resistor
    assert window.details.voltage_card.value.text() == "12 V"
    assert window.details.current_card.value.text() == "120 mA"

    window.scene.clearSelection()
    assert not window.details.showing_component
    assert window.details.battery_current.value.text() == "120 mA"


def test_graph_shows_the_battery_when_nothing_is_selected(qtbot) -> None:
    window = _window(qtbot)
    window.add_component("resistor")
    _solved(qtbot, window)

    window.scene.clearSelection()

    assert window.analysis.title.text().startswith("Battery over time")
    _, current = window.analysis.current_curve.getData()
    assert current[-1] == pytest.approx(0.12)


def test_scrubbing_updates_canvas_readings_graph_cursor_and_time_label(qtbot) -> None:
    window = _window(qtbot)
    window.add_component("resistor")
    capacitor = window.add_component("capacitor")
    _solved(qtbot, window)
    result = window.current_result
    middle = len(result.time) // 4

    window.time_bar.slider.setValue(middle)

    item = window.scene.component_items[capacitor]
    expected = result.branches[capacitor].voltage[middle]
    assert window.current_time_index == middle
    assert window.analysis.cursors[0].value() == pytest.approx(result.time[middle])
    assert item.voltage_text == format_si(float(expected), "V")
    assert window.details.voltage_card.value.text() == format_si(float(expected), "V")
    assert abs(expected) < abs(result.branches[capacitor].voltage[-1])
    assert window.time_bar.time_text().startswith("t = ")


def test_problem_is_explained_on_the_canvas_and_the_component_outlined(qtbot) -> None:
    window = _window(qtbot)
    window.add_component("resistor")
    _solved(qtbot, window)

    loose = window.scene.insert_component_at("inductor", QPointF(560.0, 640.0))
    qtbot.waitUntil(lambda: window.current_result is None, timeout=3000)

    assert not window.view.banner.isHidden()
    assert loose in window.view.banner_label.text()
    assert window.scene.component_items[loose].problem
    assert window.analysis.showing_placeholder
    assert window.time_bar.isEnabled() is False


def test_starting_state_uses_the_guide_card_instead_of_a_warning_banner(qtbot) -> None:
    window = _window(qtbot)

    qtbot.waitUntil(lambda: "add a component" in window.status_label.text().lower(), timeout=3000)

    assert window.view.banner.isHidden()
    assert window.scene.guide_item is not None


def test_right_click_menus_offer_the_actions_for_what_is_under_the_pointer(qtbot) -> None:
    window = _window(qtbot)
    window.show()
    qtbot.waitExposed(window)
    resistor = window.add_component("resistor")
    item = window.scene.component_items[resistor]
    window.view.centerOn(item)
    qtbot.wait(20)

    menu = window.view.build_context_menu(window.view.mapFromScene(item.scenePos()))
    labels = [action.text() for action in menu.actions() if action.text()]
    assert labels == ["Edit value…", "Rotate", "Add parallel copy", "Delete"]

    empty = window.view.build_context_menu(window.view.mapFromScene(QPointF(2000.0, 2000.0)))
    assert "Add resistor here" in [action.text() for action in empty.actions()]


def test_play_runs_the_whole_span_in_a_few_seconds_then_stops(qtbot) -> None:
    from circuitcanvas.ui.playback import PlaybackController

    playback = PlaybackController()
    playback.set_timeline(samples=100, duration=50.0)
    playback.set_speed(10.0)
    seen: list[int] = []
    playback.time_index_changed.connect(seen.append)

    playback.set_playing(True)
    qtbot.waitUntil(lambda: not playback.timer.isActive(), timeout=2000)

    assert seen[0] == 0
    assert seen[-1] == 99


def test_rotated_component_keeps_upright_wider_card(qtbot) -> None:
    window = _window(qtbot)
    resistor = window.add_component("resistor")
    window.scene.rotate_component(resistor)

    item = window.scene.component_items[resistor]

    assert item.vertical
    assert item.boundingRect().height() == 132
