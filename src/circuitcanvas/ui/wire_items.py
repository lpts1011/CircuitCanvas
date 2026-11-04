"""Graphics items for explicit terminals, junctions, wires, and route handles."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from circuitcanvas.domain.wiring import EndpointRef, Wire

from .routing import normalized_octilinear_polyline


class TerminalItem(QGraphicsObject):
    def __init__(self, ref: EndpointRef, parent: QGraphicsObject) -> None:
        super().__init__(parent)
        self.ref = ref
        self.connected = False
        self.targeted = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(5)
        self.setToolTip(
            "Terminal: drag to another terminal or onto a wire to connect it.\n"
            "Orange = not connected yet, blue = connected."
        )

    def boundingRect(self) -> QRectF:
        return QRectF(-8, -8, 16, 16)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        color = "#22c55e" if self.targeted else ("#2563eb" if self.connected else "#f97316")
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor(color))
        painter.drawEllipse(self.boundingRect())


class JunctionItem(QGraphicsObject):
    moved = Signal(str, float, float)

    def __init__(self, junction_id: str) -> None:
        super().__init__()
        self.junction_id = junction_id
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable
            | QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
        )
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(4)
        self.setToolTip(
            "Junction: wires that meet here are connected.\n"
            "Drag to slide it along its wire · Shift-drag to draw a new wire · "
            "Delete to remove"
        )

    def boundingRect(self) -> QRectF:
        return QRectF(-7, -7, 14, 14)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor("#2563eb" if self.isSelected() else "#334155"))
        painter.drawEllipse(self.boundingRect())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        position = self.scenePos()
        self.moved.emit(self.junction_id, position.x(), position.y())


class RouteHandleItem(QGraphicsObject):
    moved = Signal(str, int, float, float)

    def __init__(self, wire_id: str, route_index: int) -> None:
        super().__init__()
        self.wire_id = wire_id
        self.route_index = route_index
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable
            | QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
        )
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(6)
        self.setToolTip("Bend: drag to reshape the wire · Delete to remove")

    def boundingRect(self) -> QRectF:
        return QRectF(-6, -6, 12, 12)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setPen(QPen(QColor("#2563eb"), 2))
        painter.setBrush(QColor("#dbeafe"))
        painter.drawRect(self.boundingRect())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        position = self.scenePos()
        self.moved.emit(self.wire_id, self.route_index, position.x(), position.y())


class WireItem(QGraphicsObject):
    STOP_CURRENT = 1e-12

    def __init__(self, wire: Wire, start: QPointF, end: QPointF) -> None:
        super().__init__()
        self.wire = wire
        self.current = 0.0
        self.phase = 0.0
        self.stale = True
        raw_points = (
            (start.x(), start.y()),
            *wire.route,
            (end.x(), end.y()),
        )
        normalized = normalized_octilinear_polyline(raw_points)
        self._points = tuple(QPointF(x, y) for x, y in normalized)
        self._path = self._path_from_points()
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(-1)
        self.setToolTip(
            "Wire (no resistance). Drop a component here to insert it in series.\n"
            "Double-click to add a bend · drop a new wire here to make a junction · "
            "Delete to remove"
        )

    def _path_from_points(self) -> QPainterPath:
        path = QPainterPath(self._points[0])
        for point in self._points[1:]:
            path.lineTo(point)
        return path

    def polyline_points(self) -> tuple[QPointF, ...]:
        return self._points

    def path(self) -> QPainterPath:
        return self._path

    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().adjusted(-12, -12, 12, 12)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(18.0)
        return stroker.createStroke(self._path)

    @property
    def arrows_visible(self) -> bool:
        return not self.stale and abs(self.current) >= self.STOP_CURRENT

    def set_current(self, current: float) -> None:
        self.current = current
        self.stale = False
        self.update()

    def set_stale(self, stale: bool) -> None:
        self.stale = stale
        self.update()

    def advance_phase(self, seconds: float) -> None:
        if not self.arrows_visible:
            return
        speed = min(2.5, max(0.15, 0.15 + 0.45 * math.log10(1 + abs(self.current) / 1e-6)))
        direction = 1.0 if self.current >= 0 else -1.0
        self.phase = (self.phase + direction * speed * seconds) % 1.0
        self.update()

    def arrow_positions(self) -> tuple[float, ...]:
        if not self.arrows_visible:
            return ()
        return tuple((self.phase + offset) % 1.0 for offset in (0.0, 0.25, 0.5, 0.75))

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor("#2563eb" if self.isSelected() else "#334155"),
                4,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPath(self._path)
        if not self.arrows_visible:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0ea5e9"))
        for percent in self.arrow_positions():
            point = self._path.pointAtPercent(percent)
            angle = math.radians(-self._path.angleAtPercent(percent))
            if self.current < 0:
                angle += math.pi
            direction = QPointF(math.cos(angle), math.sin(angle))
            normal = QPointF(-direction.y(), direction.x())
            triangle = QPolygonF(
                [
                    point + direction * 8.0,
                    point - direction * 5.0 + normal * 5.0,
                    point - direction * 5.0 - normal * 5.0,
                ]
            )
            painter.drawPolygon(triangle)
