"""Right-hand panel: the circuit overview, or the selected component and its readings."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.domain.components import Component

from .formatting import format_component_value
from .icons import component_icon, icon
from .inspector import ComponentInspector
from .theme import (
    CURRENT_TEXT,
    DANGER,
    KIND_NAMES,
    TEXT,
    TEXT_MUTED,
    TEXT_SECONDARY,
    VOLTAGE_TEXT,
)


class ReadingCard(QFrame):
    """A small labelled number, such as "Voltage 7.4 V"."""

    def __init__(self, label: str, *, style: str = "card", color: str = TEXT) -> None:
        super().__init__()
        self.setObjectName(style)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self.label = QLabel(label)
        self.label.setStyleSheet(f"color:{color if color != TEXT else TEXT_SECONDARY}")
        self.value = QLabel("—")
        self.value.setStyleSheet(f"color:{color};font-size:17px;font-weight:600")
        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


class DetailsPanel(QWidget):
    back_requested = Signal()

    def __init__(self, inspector: ComponentInspector, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.inspector = inspector
        self.stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.stack.addWidget(self._build_overview())
        self.stack.addWidget(self._build_component_page())
        self.show_overview()

    # ----- Pages ------------------------------------------------------------------

    def _build_overview(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(_title("Battery"))
        row = QHBoxLayout()
        voltage_label = QLabel("Voltage")
        voltage_label.setStyleSheet(f"color:{TEXT_SECONDARY}")
        row.addWidget(voltage_label)
        self.source_voltage = QDoubleSpinBox()
        self.source_voltage.setRange(0.001, 1000.0)
        self.source_voltage.setDecimals(3)
        self.source_voltage.setValue(12.0)
        self.source_voltage.setSuffix(" V")
        self.source_voltage.setToolTip(
            "Voltage of the ideal DC battery. It is switched on at t = 0.\n"
            "Tip: double-click the battery on the canvas to edit this."
        )
        row.addWidget(self.source_voltage, 1)
        layout.addLayout(row)

        self.status_card = QFrame()
        self.status_card.setObjectName("statusCard")
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(10, 8, 10, 8)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        layout.addWidget(self.status_card)

        layout.addSpacing(4)
        layout.addWidget(_title("Whole circuit"))
        self.overview_time = QLabel()
        self.overview_time.setObjectName("muted")
        layout.addWidget(self.overview_time)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.battery_current = ReadingCard(
            "Current from battery", style="currentCard", color=CURRENT_TEXT
        )
        self.battery_power = ReadingCard("Power")
        self.stored_energy = ReadingCard("Stored energy")
        self.component_count = ReadingCard("Components")
        grid.addWidget(self.battery_current, 0, 0)
        grid.addWidget(self.battery_power, 0, 1)
        grid.addWidget(self.stored_energy, 1, 0)
        grid.addWidget(self.component_count, 1, 1)
        layout.addLayout(grid)

        hint = QLabel(
            "Select a component on the canvas to change it and see its own readings. "
            "Double-click one to type a new value."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _build_component_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.component_symbol = QLabel()
        self.component_name = QLabel()
        self.component_name.setStyleSheet(f"color:{TEXT};font-size:17px;font-weight:600")
        self.component_kind = QLabel()
        self.component_kind.setStyleSheet(f"color:{TEXT_MUTED}")
        self.back_button = QToolButton()
        self.back_button.setText("Done")
        self.back_button.setToolTip("Deselect and show the whole circuit (Esc)")
        self.back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(self.component_symbol)
        header.addWidget(self.component_name)
        header.addWidget(self.component_kind)
        header.addStretch()
        header.addWidget(self.back_button)
        layout.addLayout(header)

        self.inspector.heading.hide()
        # The inspector ends in a stretch; inside this page it must not grow.
        self.inspector.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.inspector.parallel_button.setText("Parallel copy")
        for button, name, color in (
            (self.inspector.parallel_button, "parallel", TEXT_SECONDARY),
            (self.inspector.rotate_button, "rotate", TEXT_SECONDARY),
            (self.inspector.delete_button, "trash", DANGER),
        ):
            button.setIcon(icon(name, color, 16))
            button.setIconSize(QSize(16, 16))
        layout.addWidget(self.inspector)

        layout.addWidget(_title("Readings"))
        self.component_time = QLabel()
        self.component_time.setObjectName("muted")
        layout.addWidget(self.component_time)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.voltage_card = ReadingCard("Voltage", style="voltageCard", color=VOLTAGE_TEXT)
        self.current_card = ReadingCard("Current", style="currentCard", color=CURRENT_TEXT)
        self.power_card = ReadingCard("Power")
        self.energy_card = ReadingCard("Stored energy")
        grid.addWidget(self.voltage_card, 0, 0)
        grid.addWidget(self.current_card, 0, 1)
        grid.addWidget(self.power_card, 1, 0)
        grid.addWidget(self.energy_card, 1, 1)
        layout.addLayout(grid)
        layout.addStretch()
        return page

    # ----- Switching ----------------------------------------------------------------

    @property
    def showing_component(self) -> bool:
        return self.stack.currentIndex() == 1

    def show_overview(self) -> None:
        self.stack.setCurrentIndex(0)

    def show_component(self, component: Component) -> None:
        kind = component.kind.value
        self.component_symbol.setPixmap(component_icon(kind).pixmap(QSize(40, 18)))
        self.component_name.setText(component.id)
        self.component_kind.setText(
            f"{KIND_NAMES[kind]} · {format_component_value(kind, component.value)}"
        )
        self.stack.setCurrentIndex(1)

    # ----- Readings -----------------------------------------------------------------

    def set_status(self, kind: str, text: str) -> None:
        """``kind`` is "ok", "problem", or "info"; it picks the card colour."""
        self.status_card.setProperty("kind", kind)
        self.status_card.style().unpolish(self.status_card)
        self.status_card.style().polish(self.status_card)
        self.status_label.setText(text)

    def set_circuit_readings(
        self, when: str, current: str, power: str, energy: str, components: int
    ) -> None:
        self.overview_time.setText(when)
        self.battery_current.set_value(current)
        self.battery_power.set_value(power)
        self.stored_energy.set_value(energy)
        self.component_count.set_value(str(components))

    def set_component_readings(
        self, when: str, voltage: str, current: str, power: str, energy: str
    ) -> None:
        self.component_time.setText(when)
        self.voltage_card.set_value(voltage)
        self.current_card.set_value(current)
        self.power_card.set_value(power)
        self.energy_card.set_value(energy)

    def clear_readings(self, components: int, reason: str = "No result yet") -> None:
        for card in (
            self.battery_current,
            self.battery_power,
            self.stored_energy,
            self.voltage_card,
            self.current_card,
            self.power_card,
            self.energy_card,
        ):
            card.set_value("—")
        self.component_count.set_value(str(components))
        self.overview_time.setText(reason)
        self.component_time.setText(reason)
