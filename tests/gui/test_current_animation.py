from PySide6.QtCore import QPointF

from circuitcanvas.domain.wiring import TerminalRef, Wire
from circuitcanvas.ui.playback import PlaybackController
from circuitcanvas.ui.routing import is_octilinear
from circuitcanvas.ui.wire_items import WireItem


def sample_wire_item() -> WireItem:
    wire = Wire("W1", TerminalRef("V1", "a"), TerminalRef("R1", "a"))
    return WireItem(wire, QPointF(0.0, 0.0), QPointF(200.0, 0.0))


def test_wire_arrow_direction_follows_signed_current(qtbot) -> None:
    item = sample_wire_item()
    item.phase = 0.25
    item.set_current(0.25)
    item.advance_phase(0.01)
    forward = item.phase

    item.phase = 0.75
    item.set_current(-0.25)
    item.advance_phase(0.01)
    reverse = item.phase

    assert forward > 0.25
    assert reverse < 0.75


def test_zero_or_stale_current_hides_arrows(qtbot) -> None:
    item = sample_wire_item()
    item.set_current(1e-15)
    assert not item.arrows_visible

    item.set_current(0.2)
    assert item.arrows_visible
    item.set_stale(True)
    assert not item.arrows_visible


def test_playback_uses_one_timer_for_time_and_animation(qtbot) -> None:
    playback = PlaybackController()
    playback.set_timeline(samples=10, duration=0.09)

    with qtbot.waitSignal(playback.time_index_changed, timeout=500):
        playback.set_playing(True)

    assert playback.timer.interval() == 16
    playback.set_playing(False)


def test_wire_item_path_contains_only_horizontal_vertical_or_45_degree_segments(qtbot) -> None:
    wire = Wire(
        "W1",
        TerminalRef("V1", "a"),
        TerminalRef("R1", "a"),
        ((31.0, 17.0),),
    )
    item = WireItem(wire, QPointF(0.0, 0.0), QPointF(100.0, 60.0))

    points = item.polyline_points()

    assert all(
        is_octilinear((left.x(), left.y()), (right.x(), right.y()))
        for left, right in zip(points, points[1:], strict=False)
    )
