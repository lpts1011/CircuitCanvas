"""Vector schematic items used by the circuit scene."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from circuitcanvas.domain.components import Component
from circuitcanvas.domain.wiring import TerminalRef

from .formatting import format_component_value, format_si
from .icons import draw_component_symbol
from .theme import (
    ACCENT,
    COMPONENT_COLORS,
    CURRENT_BG,
    CURRENT_TEXT,
    DANGER,
    DANGER_BG,
    INFO_BG,
    KIND_NAMES,
    TEXT,
    TEXT_MUTED,
    VOLTAGE_BG,
    VOLTAGE_TEXT,
)
from .wire_items import TerminalItem

HIGHLIGHT_FILL = "#fef3c7"
HIGHLIGHT_EDGE = "#d97706"


def _font(point_size: float, *, bold: bool = False) -> QFont:
    font = QFont()
    font.setPointSizeF(point_size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def _draw_chip(
    painter: QPainter, center: QPointF, text: str, fill: str, color: str, font: QFont
) -> None:
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(text) + 12
    height = metrics.height() + 4
    rect = QRectF(center.x() - width / 2, center.y() - height / 2, width, height)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(fill))
    painter.drawRoundedRect(rect, 5, 5)
    painter.setPen(QColor(color))
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class BatteryItem(QGraphicsObject):
    def __init__(self, voltage: float, source_id: str = "V1") -> None:
        super().__init__()
        self.voltage = voltage
        self.highlighted = False
        self.terminals = {
            "a": TerminalItem(TerminalRef(source_id, "a"), self),
            "b": TerminalItem(TerminalRef(source_id, "b"), self),
        }
        self.terminals["a"].setPos(0, -70)
        self.terminals["b"].setPos(0, 70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            f"Battery: {format_si(voltage, 'V')} DC, switched on at t = 0.\n"
            "Double-click to change the voltage."
        )

    def boundingRect(self) -> QRectF:
        return QRectF(-42, -70, 136, 140)

    def set_highlighted(self, highlighted: bool) -> None:
        if highlighted != self.highlighted:
            self.highlighted = highlighted
            self.update()

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.highlighted:
            painter.setBrush(QColor(HIGHLIGHT_FILL))
            painter.setPen(QPen(QColor(HIGHLIGHT_EDGE), 2, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(self.boundingRect().adjusted(1, 1, -1, -1), 10, 10)
        painter.setPen(QPen(QColor("#3b82f6"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(-24, -14), QPointF(24, -14))
        painter.drawLine(QPointF(-14, 16), QPointF(14, 16))
        painter.drawLine(QPointF(0, -70), QPointF(0, -14))
        painter.drawLine(QPointF(0, 16), QPointF(0, 70))
        painter.setPen(QColor("#1e3a8a"))
        painter.setFont(_font(9, bold=True))
        painter.drawText(QRectF(-40, -24, 16, 16), Qt.AlignmentFlag.AlignCenter, "+")
        painter.drawText(QRectF(-40, 10, 16, 16), Qt.AlignmentFlag.AlignCenter, "−")
        # The voltage sits beside the plates so it never covers a wire.
        painter.setFont(_font(11, bold=True))
        painter.drawText(
            QRectF(32, -12, 62, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            format_si(self.voltage, "V"),
        )


class GuideItem(QGraphicsObject):
    """A "start here" card shown on a circuit that has no components yet."""

    WIDTH = 540.0
    HEIGHT = 118.0
    LINES = (
        ("Start here", True),
        ("1   Click Resistor, Capacitor or Inductor on the left, or drag one onto a wire.", False),
        ("2   Press Play to watch it happen, or drag the time slider at the top.", False),
        ("Need more?  Help ▸ Quick Start Guide, or File ▸ Open Example.", False),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        return QRectF(-self.WIDTH / 2, -self.HEIGHT / 2, self.WIDTH, self.HEIGHT)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#93c5fd"), 1.5))
        painter.setBrush(QColor(INFO_BG))
        painter.drawRoundedRect(self.boundingRect(), 14, 14)
        y = -self.HEIGHT / 2 + 14
        for text, heading in self.LINES:
            painter.setFont(_font(12 if heading else 10, bold=heading))
            painter.setPen(QColor("#1e3a8a" if heading else "#334155"))
            height = 26.0 if heading else 22.0
            painter.drawText(
                QRectF(-self.WIDTH / 2 + 20, y, self.WIDTH - 40, height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            y += height


class DropTargetItem(QGraphicsObject):
    def boundingRect(self) -> QRectF:
        return QRectF(-94, -36, 188, 72)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        pen = QPen(QColor("#60a5fa"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(INFO_BG))
        painter.drawRoundedRect(self.boundingRect(), 12, 12)
        painter.setPen(QColor("#1d4ed8"))
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, "Drop a component here")


class ComponentItem(QGraphicsObject):
    """A component card: name and value, schematic symbol, and live voltage/current chips."""

    moved = Signal(str, float, float)
    COLORS = COMPONENT_COLORS

    def __init__(self, component: Component) -> None:
        super().__init__()
        self.component = component
        self.voltage_text = "—"
        self.current_text = "—"
        self.measurement_text = "V —  ·  I —"
        # Equation highlight is separate from selection so it never changes
        # what Delete or Rotate act on.
        self.highlighted = False
        #: Outlined in red when the circuit cannot be solved because of this component.
        self.problem = False
        self.terminals = {
            "a": TerminalItem(TerminalRef(component.id, "a"), self),
            "b": TerminalItem(TerminalRef(component.id, "b"), self),
        }
        self.terminals["a"].setPos(-84, 0)
        self.terminals["b"].setPos(84, 0)
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsObject.GraphicsItemFlag.ItemIsMovable
            | QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip(
            f"{KIND_NAMES[component.kind.value]} {component.id}: drag to move · "
            "double-click to edit the value · right-click for more"
        )

    @property
    def vertical(self) -> bool:
        return round(self.rotation()) % 180 == 90

    def boundingRect(self) -> QRectF:
        # Vertical components are drawn wider so upright labels fit beside the symbol.
        return QRectF(-84, -66, 168, 132) if self.vertical else QRectF(-84, -49, 168, 98)

    def itemChange(self, change: QGraphicsObject.GraphicsItemChange, value: object) -> object:
        if change == QGraphicsObject.GraphicsItemChange.ItemRotationChange:
            self.prepareGeometryChange()
        elif change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if scene is not None and hasattr(scene, "component_dragging"):
                scene.component_dragging(self)
        return super().itemChange(change, value)

    def set_highlighted(self, highlighted: bool) -> None:
        if highlighted != self.highlighted:
            self.highlighted = highlighted
            self.update()

    def set_problem(self, problem: bool) -> None:
        if problem != self.problem:
            self.problem = problem
            self.update()

    def set_measurement(self, voltage: float, current: float) -> None:
        self.voltage_text = format_si(voltage, "V")
        self.current_text = format_si(current, "A")
        self.measurement_text = f"{self.voltage_text}  ·  {self.current_text}"
        self.update()

    def clear_measurement(self) -> None:
        self.voltage_text = "—"
        self.current_text = "—"
        self.measurement_text = "V —  ·  I —"
        self.update()

    def _card_colors(self) -> tuple[QColor, QPen]:
        _color, background = self.COLORS[self.component.kind.value]
        if self.problem:
            # A problem stays visible even on the selected component.
            fill = INFO_BG if self.isSelected() else DANGER_BG
            return QColor(fill), QPen(QColor(DANGER), 2.5, Qt.PenStyle.DashLine)
        if self.isSelected():
            return QColor(INFO_BG), QPen(QColor(ACCENT), 2.5)
        if self.highlighted:
            return QColor(HIGHLIGHT_FILL), QPen(QColor(HIGHLIGHT_EDGE), 2, Qt.PenStyle.DashLine)
        return QColor(background), QPen(QColor("#dbe2ea"), 1)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        fill, border = self._card_colors()
        painter.setBrush(fill)
        painter.setPen(border)
        painter.drawRoundedRect(self.boundingRect(), 12, 12)
        color, _background = self.COLORS[self.component.kind.value]
        symbol = QPen(QColor(color), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        symbol.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(symbol)
        draw_component_symbol(painter, self.component.kind.value)

        # Text is drawn upright whatever the item's rotation.
        painter.save()
        painter.rotate(-self.rotation())
        if self.vertical:
            self._paint_vertical_labels(painter)
        else:
            self._paint_horizontal_labels(painter)
        painter.restore()

    def _paint_horizontal_labels(self, painter: QPainter) -> None:
        painter.setPen(QColor(TEXT))
        painter.setFont(_font(10, bold=True))
        painter.drawText(QRectF(-80, -45, 160, 20), Qt.AlignmentFlag.AlignCenter, self._title())
        chip_font = _font(9)
        metrics = QFontMetricsF(chip_font)
        voltage_width = metrics.horizontalAdvance(self.voltage_text) + 12
        current_width = metrics.horizontalAdvance(self.current_text) + 12
        gap = 6.0
        left = -(voltage_width + gap + current_width) / 2
        _draw_chip(
            painter,
            QPointF(left + voltage_width / 2, 33),
            self.voltage_text,
            VOLTAGE_BG,
            VOLTAGE_TEXT,
            chip_font,
        )
        _draw_chip(
            painter,
            QPointF(left + voltage_width + gap + current_width / 2, 33),
            self.current_text,
            CURRENT_BG,
            CURRENT_TEXT,
            chip_font,
        )

    def _paint_vertical_labels(self, painter: QPainter) -> None:
        # Terminals sit at the top and bottom, so labels go beside the symbol:
        # name and value on the left, voltage and current on the right.
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        painter.setPen(QColor(TEXT))
        painter.setFont(_font(10, bold=True))
        painter.drawText(QRectF(-66, -30, 50, 18), right, self.component.id)
        painter.setPen(QColor(TEXT_MUTED))
        painter.setFont(_font(9))
        value = format_component_value(self.component.kind.value, self.component.value)
        painter.drawText(QRectF(-66, -10, 50, 18), right, value)
        chip_font = _font(8)
        _draw_chip(
            painter, QPointF(40, -12), self.voltage_text, VOLTAGE_BG, VOLTAGE_TEXT, chip_font
        )
        _draw_chip(painter, QPointF(40, 12), self.current_text, CURRENT_BG, CURRENT_TEXT, chip_font)

    def _title(self) -> str:
        value = format_component_value(self.component.kind.value, self.component.value)
        return f"{self.component.id} · {value}"

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        position = self.scenePos()
        self.moved.emit(self.component.id, position.x(), position.y())
