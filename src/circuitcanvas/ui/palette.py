"""Draggable R, C, and L component palette."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class DraggableComponentButton(QPushButton):
    def __init__(self, title: str, kind: str, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.kind = kind
        self._press_position = QPoint()
        self.setMinimumHeight(52)
        self.setStyleSheet(
            f"QPushButton {{text-align:left;padding:10px 14px;border:1px solid {accent};"
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
        label = QLabel("COMPONENTS")
        label.setStyleSheet("font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px")
        layout.addWidget(label)
        for title, kind, accent in (
            ("〰  Resistor", "resistor", "#fecaca"),
            ("┃┃  Capacitor", "capacitor", "#fde68a"),
            ("∿  Inductor", "inductor", "#ddd6fe"),
        ):
            button = DraggableComponentButton(title, kind, accent)
            button.clicked.connect(
                lambda checked=False, value=kind: self.component_clicked.emit(value)
            )
            layout.addWidget(button)
        hint = QLabel(
            "Drag onto the wire for series.\nDrop below a component for a parallel branch."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b;font-size:11px;margin-top:6px")
        layout.addWidget(hint)
