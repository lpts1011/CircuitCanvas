from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent


def _wheel(dy: int, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> QWheelEvent:
    return QWheelEvent(
        QPointF(200, 200),
        QPointF(200, 200),
        QPoint(0, dy),
        QPoint(0, dy),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _shown_window(qtbot):
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    qtbot.wait(20)  # let the deferred initial fit run
    return window


def test_plain_scroll_pans_instead_of_zooming(qtbot) -> None:
    window = _shown_window(qtbot)
    window.view.resetTransform()

    for _ in range(30):
        window.view.wheelEvent(_wheel(-30))

    assert window.view.zoom_level == 1.0


def test_ctrl_scroll_zooms_within_limits(qtbot) -> None:
    window = _shown_window(qtbot)
    view = window.view
    view.resetTransform()

    view.wheelEvent(_wheel(120, Qt.KeyboardModifier.ControlModifier))
    assert view.zoom_level > 1.0

    for _ in range(200):
        view.wheelEvent(_wheel(-120, Qt.KeyboardModifier.ControlModifier))
    assert view.zoom_level == view.MIN_ZOOM

    for _ in range(200):
        view.zoom_in()
    assert view.zoom_level == view.MAX_ZOOM


def test_whole_starter_circuit_is_visible_after_startup(qtbot) -> None:
    window = _shown_window(qtbot)

    def battery_visible() -> bool:
        visible = window.view.mapToScene(window.view.viewport().rect()).boundingRect()
        battery = window.scene.battery_item
        return battery is not None and visible.contains(battery.sceneBoundingRect())

    qtbot.waitUntil(battery_visible, timeout=2000)
    visible = window.view.mapToScene(window.view.viewport().rect()).boundingRect()
    assert visible.contains(window.scene.itemsBoundingRect())


def test_fit_view_never_magnifies_beyond_actual_size(qtbot) -> None:
    window = _shown_window(qtbot)
    window.view.zoom_out()

    window.fit_action.trigger()

    assert window.view.zoom_level <= 1.0
