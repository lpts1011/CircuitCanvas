"""Line icons and component symbols drawn with QPainter, so they look the same everywhere.

Icons use a 24 × 24 design grid and are rendered at 2× for high-density screens.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from .theme import COMPONENT_COLORS, TEXT_SECONDARY

_SCALE = 2


def _path(*points: tuple[float, float]) -> QPainterPath:
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        path.lineTo(QPointF(*point))
    return path


def _new(p: QPainter) -> None:
    p.drawPath(_path((6, 3), (14, 3), (18, 7), (18, 21), (6, 21), (6, 3)))
    p.drawLine(QPointF(12, 10), QPointF(12, 16))
    p.drawLine(QPointF(9, 13), QPointF(15, 13))


def _open(p: QPainter) -> None:
    p.drawPath(_path((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19), (3, 6)))


def _save(p: QPainter) -> None:
    p.drawLine(QPointF(12, 4), QPointF(12, 14))
    p.drawPath(_path((8, 10), (12, 14), (16, 10)))
    p.drawPath(_path((4, 14), (4, 20), (20, 20), (20, 14)))


def _undo(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 10))
    path.lineTo(14, 10)
    path.arcTo(QRectF(9, 10, 10, 10), 90, -180)
    path.lineTo(10, 20)
    p.drawPath(path)
    p.drawPath(_path((9, 6), (5, 10), (9, 14)))


def _redo(p: QPainter) -> None:
    p.save()
    p.translate(24, 0)
    p.scale(-1, 1)
    _undo(p)
    p.restore()


def _play(p: QPainter) -> None:
    p.setBrush(p.pen().color())
    p.drawPolygon(QPolygonF([QPointF(8, 5), QPointF(19, 12), QPointF(8, 19)]))


def _pause(p: QPainter) -> None:
    p.setBrush(p.pen().color())
    p.drawRoundedRect(QRectF(7, 5, 3, 14), 1, 1)
    p.drawRoundedRect(QRectF(14, 5, 3, 14), 1, 1)


def _help(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 9, 9)
    font = QFont()
    font.setPixelSize(13)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(3, 3, 18, 18), Qt.AlignmentFlag.AlignCenter, "?")


def _rotate(p: QPainter) -> None:
    path = QPainterPath()
    path.arcMoveTo(QRectF(5, 5, 14, 14), 60)
    path.arcTo(QRectF(5, 5, 14, 14), 60, 280)
    p.drawPath(path)
    p.drawPath(_path((14, 3), (16, 6.5), (12.5, 8)))


def _parallel(p: QPainter) -> None:
    # "Duplicate": the parallel copy is a second component of the same kind.
    p.drawRoundedRect(QRectF(9, 9, 11, 11), 2, 2)
    p.drawPath(_path((15, 9), (15, 4), (4, 4), (4, 15), (9, 15)))


def _trash(p: QPainter) -> None:
    p.drawLine(QPointF(4, 7), QPointF(20, 7))
    p.drawPath(_path((9, 7), (9, 4), (15, 4), (15, 7)))
    p.drawPath(_path((6, 7), (7, 20), (17, 20), (18, 7)))
    p.drawLine(QPointF(10, 11), QPointF(10, 16))
    p.drawLine(QPointF(14, 11), QPointF(14, 16))


def _magnifier(p: QPainter) -> None:
    p.drawEllipse(QPointF(10, 10), 6, 6)
    p.drawLine(QPointF(14.5, 14.5), QPointF(20, 20))


def _zoom_in(p: QPainter) -> None:
    _magnifier(p)
    p.drawLine(QPointF(7, 10), QPointF(13, 10))
    p.drawLine(QPointF(10, 7), QPointF(10, 13))


def _zoom_out(p: QPainter) -> None:
    _magnifier(p)
    p.drawLine(QPointF(7, 10), QPointF(13, 10))


def _fit(p: QPainter) -> None:
    for x, y, dx, dy in ((4, 4, 1, 1), (20, 4, -1, 1), (4, 20, 1, -1), (20, 20, -1, -1)):
        p.drawPath(_path((x, y + 5 * dy), (x, y), (x + 5 * dx, y)))


def _edit(p: QPainter) -> None:
    p.drawPath(_path((5, 19), (6, 15), (16, 5), (19, 8), (9, 18), (5, 19)))
    p.drawLine(QPointF(14, 7), QPointF(17, 10))


_ICONS: dict[str, Callable[[QPainter], None]] = {
    "new": _new,
    "open": _open,
    "save": _save,
    "undo": _undo,
    "redo": _redo,
    "play": _play,
    "pause": _pause,
    "help": _help,
    "rotate": _rotate,
    "parallel": _parallel,
    "trash": _trash,
    "zoom-in": _zoom_in,
    "zoom-out": _zoom_out,
    "fit": _fit,
    "edit": _edit,
}

ICON_NAMES = tuple(_ICONS)


@cache
def icon(name: str, color: str = TEXT_SECONDARY, size: int = 24) -> QIcon:
    """A line icon drawn on the 24 × 24 grid, e.g. ``icon("undo")``."""
    pixmap = QPixmap(size * _SCALE, size * _SCALE)
    pixmap.setDevicePixelRatio(_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.scale(size / 24, size / 24)
    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _ICONS[name](painter)
    painter.end()
    return QIcon(pixmap)


def draw_component_symbol(painter: QPainter, kind: str, width: float = 124.0) -> None:
    """Draw a resistor, capacitor, or inductor symbol centred on the origin."""
    half = width / 2
    if kind == "capacitor":
        painter.drawLine(QPointF(-8, -12), QPointF(-8, 12))
        painter.drawLine(QPointF(8, -12), QPointF(8, 12))
        painter.drawLine(QPointF(-half, 0), QPointF(-8, 0))
        painter.drawLine(QPointF(8, 0), QPointF(half, 0))
    elif kind == "inductor":
        path = QPainterPath(QPointF(-half, 0))
        path.lineTo(-48, 0)
        for center in (-38.0, -14.0, 10.0, 34.0):
            path.cubicTo(center - 10, -18, center + 10, -18, center + 14, 0)
        path.lineTo(half, 0)
        painter.drawPath(path)
    else:
        path = QPainterPath(QPointF(-half, 0))
        zigzag = (-50.0, -42.0, -28.0, -14.0, 0.0, 14.0, 28.0, 42.0, 50.0)
        heights = (0.0, -12.0, 12.0, -12.0, 12.0, -12.0, 12.0, -12.0, 0.0)
        for x, y in zip(zigzag, heights, strict=True):
            path.lineTo(x, y)
        path.lineTo(half, 0)
        painter.drawPath(path)


@cache
def component_icon(kind: str) -> QIcon:
    """A coloured schematic symbol for the component palette."""
    width, height = 56, 24
    pixmap = QPixmap(width * _SCALE, height * _SCALE)
    pixmap.setDevicePixelRatio(_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(width / 2, height / 2)
    painter.scale(width / 132, width / 132)
    color, _background = COMPONENT_COLORS[kind]
    pen = QPen(QColor(color), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    draw_component_symbol(painter, kind)
    painter.end()
    return QIcon(pixmap)
