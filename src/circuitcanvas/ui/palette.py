"""Left-hand rail for adding resistors, capacitors, and inductors."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from .icons import component_icon
from .theme import KIND_NAMES

_DESCRIPTIONS = {
    "resistor": "Limits current. Its voltage and current are proportional (Ohm's law).",
    "capacitor": "Stores energy in an electric field; it charges up over time.",
    "inductor": "Stores energy in a magnetic field; it resists changes in current.",
}


class DraggableComponentButton(QToolButton):
    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._press_position = QPoint()
        self.setObjectName("paletteButton")
        self.setText(KIND_NAMES[kind])
        self.setIcon(component_icon(kind))
        self.setIconSize(QSize(56, 24))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(62)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(
            f"{KIND_NAMES[kind]}: {_DESCRIPTIONS[kind]}\n\n"
            "Click to add it in series on the longest wire,\n"
            "or drag it onto the wire where you want it."
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
        drag.setPixmap(self.icon().pixmap(QSize(56, 24)))
        # Hold the symbol by its middle, so lining it up with a wire drops it there.
        drag.setHotSpot(QPoint(28, 12))
        drag.exec(Qt.DropAction.CopyAction)
        self.setDown(False)


class ComponentPalette(QWidget):
    component_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(96)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)
        title = QLabel("Add")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        self.buttons: dict[str, DraggableComponentButton] = {}
        for kind in ("resistor", "capacitor", "inductor"):
            button = DraggableComponentButton(kind)
            button.clicked.connect(
                lambda checked=False, value=kind: self.component_clicked.emit(value)
            )
            layout.addWidget(button)
            self.buttons[kind] = button
        hint = QLabel("Click, or drag onto a wire")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(hint)
        layout.addStretch()
