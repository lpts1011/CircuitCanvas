"""Vector schematic items used by the circuit scene."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from circuitcanvas.domain.components import Capacitor, Component, Inductor
from circuitcanvas.domain.wiring import TerminalRef

from .wire_items import TerminalItem


class BatteryItem(QGraphicsObject):
    def __init__(self, voltage: float, source_id: str = "V1") -> None:
        super().__init__()
        self.voltage = voltage
        self.terminals = {
            "a": TerminalItem(TerminalRef(source_id, "a"), self),
            "b": TerminalItem(TerminalRef(source_id, "b"), self),
        }
        self.terminals["a"].setPos(0, -70)
        self.terminals["b"].setPos(0, 70)

    def boundingRect(self) -> QRectF:
        return QRectF(-42, -70, 84, 140)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#3b82f6"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(-24, -14), QPointF(24, -14))
        painter.drawLine(QPointF(-14, 16), QPointF(14, 16))
        painter.drawLine(QPointF(0, -70), QPointF(0, -14))
        painter.drawLine(QPointF(0, 16), QPointF(0, 70))
        painter.setPen(QColor("#1e3a8a"))
        painter.setFont(QFont("Arial", 10, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(-42, -48, 84, 20), Qt.AlignmentFlag.AlignCenter, f"{self.voltage:g} V"
        )
        painter.drawText(QRectF(-38, -7, 16, 16), Qt.AlignmentFlag.AlignCenter, "+")
        painter.drawText(QRectF(-38, 20, 16, 16), Qt.AlignmentFlag.AlignCenter, "−")


class DropTargetItem(QGraphicsObject):
    def boundingRect(self) -> QRectF:
        return QRectF(-94, -36, 188, 72)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        pen = QPen(QColor("#60a5fa"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor("#eff6ff"))
        painter.drawRoundedRect(self.boundingRect(), 12, 12)
        painter.setPen(QColor("#1d4ed8"))
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, "Drop a component here")


class ComponentItem(QGraphicsObject):
    moved = Signal(str, float, float)
    COLORS = {
        "resistor": ("#ef4444", "#fff7f7"),
        "capacitor": ("#f59e0b", "#fffbeb"),
        "inductor": ("#8b5cf6", "#faf5ff"),
    }

    def __init__(self, component: Component) -> None:
        super().__init__()
        self.component = component
        self.measurement_text = "V —  ·  I —"
        self.terminals = {
            "a": TerminalItem(TerminalRef(component.id, "a"), self),
            "b": TerminalItem(TerminalRef(component.id, "b"), self),
        }
        self.terminals["a"].setPos(-84, 0)
        self.terminals["b"].setPos(84, 0)
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsObject.GraphicsItemFlag.ItemIsMovable
        )
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def boundingRect(self) -> QRectF:
        return QRectF(-84, -49, 168, 98)

    def set_measurement(self, voltage: float, current: float) -> None:
        self.measurement_text = f"V {voltage:.3f} V  ·  I {current:.4g} A"
        self.update()

    def _draw_symbol(self, painter: QPainter) -> None:
        if isinstance(self.component, Capacitor):
            painter.drawLine(QPointF(-8, -12), QPointF(-8, 12))
            painter.drawLine(QPointF(8, -12), QPointF(8, 12))
            painter.drawLine(QPointF(-62, 0), QPointF(-8, 0))
            painter.drawLine(QPointF(8, 0), QPointF(62, 0))
        elif isinstance(self.component, Inductor):
            path = QPainterPath(QPointF(-62, 0))
            for x in (-38, -14, 10, 34):
                path.cubicTo(x - 10, -18, x + 10, -18, x + 14, 0)
            path.lineTo(62, 0)
            painter.drawPath(path)
        else:
            path = QPainterPath(QPointF(-62, 0))
            points = [
                (-50, 0),
                (-42, -12),
                (-28, 12),
                (-14, -12),
                (0, 12),
                (14, -12),
                (28, 12),
                (42, -12),
                (50, 0),
                (62, 0),
            ]
            for x, y in points:
                path.lineTo(x, y)
            painter.drawPath(path)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color, background = self.COLORS[self.component.kind.value]
        if self.isSelected():
            painter.setBrush(QColor("#dbeafe"))
            painter.setPen(QPen(QColor("#2563eb"), 2))
            painter.drawRoundedRect(self.boundingRect(), 12, 12)
        else:
            painter.setBrush(QColor(background))
            painter.setPen(QPen(QColor("#dbe2ea"), 1))
            painter.drawRoundedRect(self.boundingRect(), 12, 12)
        painter.setPen(QPen(QColor(color), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self._draw_symbol(painter)
        painter.setPen(QColor("#172033"))
        painter.setFont(QFont("Arial", 10, QFont.Weight.DemiBold))
        painter.drawText(QRectF(-78, -44, 156, 20), Qt.AlignmentFlag.AlignCenter, self._title())
        painter.setPen(QColor("#475569"))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            QRectF(-80, 25, 160, 18), Qt.AlignmentFlag.AlignCenter, self.measurement_text
        )

    def _title(self) -> str:
        value = self.component.value
        if isinstance(self.component, Capacitor):
            return f"{self.component.id} · {value * 1e6:g} μF"
        if isinstance(self.component, Inductor):
            return f"{self.component.id} · {value * 1e3:g} mH"
        return f"{self.component.id} · {value:g} Ω"

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        position = self.scenePos()
        self.moved.emit(self.component.id, position.x(), position.y())
