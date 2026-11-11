"""Graphics items for explicit terminals, junctions, wires, and route handles."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from circuitcanvas.domain.wiring import EndpointRef, Wire

from .routing import normalized_octilinear_polyline

TARGET_GREEN = "#16a34a"


def _paint_dot_halo(painter: QPainter, *, targeted: bool, candidate: bool) -> None:
    """The ring around a dot while a wire is being drawn."""
    if targeted:
        halo = QColor(TARGET_GREEN)
        halo.setAlpha(70)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QPointF(0, 0), 15, 15)
    elif candidate:
        painter.setPen(QPen(QColor(TARGET_GREEN), 1.5, Qt.PenStyle.DotLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), 12, 12)


class TerminalItem(QGraphicsObject):
    """A component or battery terminal: where wires start and end."""

    def __init__(self, ref: EndpointRef, parent: QGraphicsObject) -> None:
        super().__init__(parent)
        self.ref = ref
        self.connected = False
        #: The wire being drawn will end here if released now.
        self.targeted = False
        #: A wire is being drawn and could end here.
        self.candidate = False
        self.hovered = False
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(5)
        self.setToolTip(
            "Drag from this dot to another dot or onto a wire to connect them.\n"
            "Orange = not connected yet, blue = connected."
        )

    def boundingRect(self) -> QRectF:
        return QRectF(-16, -16, 32, 32)

    def shape(self) -> QPainterPath:
        # A grab area a little larger than the dot, so it is easy to hit.
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), 11, 11)
        return path

    def set_wire_state(self, *, candidate: bool, targeted: bool) -> None:
        if (candidate, targeted) != (self.candidate, self.targeted):
            self.candidate = candidate
            self.targeted = targeted
            self.update()

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self.hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self.hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_dot_halo(painter, targeted=self.targeted, candidate=self.candidate)
        idle = "#2563eb" if self.connected else "#f97316"
        color = TARGET_GREEN if self.targeted else idle
        radius = 10.0 if self.targeted or self.hovered else 8.0
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(0, 0), radius, radius)


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
        self.targeted = False
        self.candidate = False
        #: The loose end of a wire: only one wire reaches this dot.
        self.dangling = False
        self.set_dangling(False)

    def set_dangling(self, dangling: bool) -> None:
        """A loose wire end is drawn orange and starts a new wire when dragged."""
        self.dangling = dangling
        if dangling:
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setToolTip(
                "Loose wire end: it is not connected to anything yet.\n"
                "Drag it onto a dot or a wire to connect it, or press Delete to remove it."
            )
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.setToolTip(
                "Junction: wires that meet here are connected.\n"
                "Drag to slide it along its wire · Shift-drag to draw a new wire · "
                "Delete to remove"
            )
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-16, -16, 32, 32)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), 10, 10)
        return path

    def set_wire_state(self, *, candidate: bool, targeted: bool) -> None:
        if (candidate, targeted) != (self.candidate, self.targeted):
            self.candidate = candidate
            self.targeted = targeted
            self.update()

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_dot_halo(painter, targeted=self.targeted, candidate=self.candidate)
        idle = "#2563eb" if self.isSelected() else ("#f97316" if self.dangling else "#334155")
        color = TARGET_GREEN if self.targeted else idle
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor(color))
        radius = 9.0 if self.targeted else (8.0 if self.dangling else 7.0)
        painter.drawEllipse(QPointF(0, 0), radius, radius)

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
        #: Glows while a dragged component would be inserted here.
        self.drop_target = False
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

    def set_drop_target(self, target: bool) -> None:
        if target != self.drop_target:
            self.drop_target = target
            self.update()

    def set_stale(self, stale: bool) -> None:
        self.stale = stale
        self.update()

    #: Roughly how far apart the current arrows are, in scene units.
    ARROW_SPACING = 90.0

    def _arrow_count(self) -> int:
        """Arrows are evenly spaced, so a short wire carries one and a long wire several."""
        return max(1, round(self._path.length() / self.ARROW_SPACING))

    def advance_phase(self, seconds: float) -> None:
        if not self.arrows_visible:
            return
        # Arrows travel at the same pace on every wire, faster for a larger current.
        pace = 40.0 * min(2.5, max(0.15, 0.15 + 0.45 * math.log10(1 + abs(self.current) / 1e-6)))
        gap = max(self._path.length() / self._arrow_count(), 1.0)
        direction = 1.0 if self.current >= 0 else -1.0
        self.phase = (self.phase + direction * pace * seconds / gap) % 1.0
        self.update()

    def arrow_positions(self) -> tuple[float, ...]:
        """Where the arrows sit, as fractions of the wire's length."""
        if not self.arrows_visible:
            return ()
        count = self._arrow_count()
        return tuple(((self.phase + index) % count) / count for index in range(count))

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.drop_target:
            glow = QColor("#2563eb")
            glow.setAlpha(70)
            painter.setPen(
                QPen(
                    glow,
                    16,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPath(self._path)
        painter.setPen(
            QPen(
                QColor("#2563eb" if self.isSelected() or self.drop_target else "#334155"),
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
