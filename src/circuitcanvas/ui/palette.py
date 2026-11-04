"""Always-visible palette for adding resistors, capacitors, and inductors."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_COMPONENTS = (
    (
        "resistor",
        "〰\nResistor",
        "#fecaca",
        "Resistor (R): limits current. Voltage and current are proportional (Ohm's law).",
    ),
    (
        "capacitor",
        "┃┃\nCapacitor",
        "#fde68a",
        "Capacitor (C): stores energy in an electric field; it charges up over time.",
    ),
    (
        "inductor",
        "∿\nInductor",
        "#ddd6fe",
        "Inductor (L): stores energy in a magnetic field; it resists changes in current.",
    ),
)


class DraggableComponentButton(QPushButton):
    def __init__(self, title: str, kind: str, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.kind = kind
        self._press_position = QPoint()
        self.setMinimumHeight(58)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            f"QPushButton {{padding:6px 4px;border:1px solid {accent};"
            "border-radius:10px;background:white;font-weight:600;}"
            "QPushButton:hover {background:#f8fafc;}"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if (event.position().toPoint() - self._press_position).manhattanLength() < 8:
            return
        mime = QMimeData()
        mime.setData("application/x-circuitcanvas-component", QByteArray(self.kind.encode()))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class ComponentPalette(QWidget):
    component_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel("ADD A COMPONENT")
        label.setStyleSheet("font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px")
        layout.addWidget(label)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.buttons: dict[str, DraggableComponentButton] = {}
        for kind, title, accent, description in _COMPONENTS:
            button = DraggableComponentButton(title, kind, accent)
            button.setToolTip(
                f"{description}\n\nClick to add it in series on the longest wire,\n"
                "or drag it onto the wire where you want it."
            )
            button.clicked.connect(
                lambda checked=False, value=kind: self.component_clicked.emit(value)
            )
            row.addWidget(button)
            self.buttons[kind] = button
        layout.addLayout(row)
        hint = QLabel(
            "Click to add in series, or drag onto a wire. Drop on empty canvas to wire it yourself."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b;font-size:11px")
        layout.addWidget(hint)
