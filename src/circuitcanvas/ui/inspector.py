"""Selected-component value editor with SI units and logarithmic slider."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.domain.components import Capacitor, Component, Inductor

_UNITS = {
    "resistor": {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
    "capacitor": {"pF": 1e-12, "nF": 1e-9, "μF": 1e-6, "mF": 1e-3, "F": 1.0},
    "inductor": {"μH": 1e-6, "mH": 1e-3, "H": 1.0},
}
_RANGES = {
    "resistor": (0.1, 10e6),
    "capacitor": (1e-12, 1.0),
    "inductor": (1e-6, 100.0),
}


class ComponentInspector(QWidget):
    value_changed = Signal(str, float)
    delete_requested = Signal(str)
    rotate_requested = Signal(str)
    parallel_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.component: Component | None = None
        self._si_value = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.heading = QLabel("SELECT A COMPONENT")
        self.heading.setStyleSheet(
            "font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px"
        )
        layout.addWidget(self.heading)

        form = QFormLayout()
        self.value_edit = QLineEdit()
        validator = QDoubleValidator(bottom=1e-15, top=1e15, decimals=12)
        validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        self.value_edit.setValidator(validator)
        self.unit_combo = QComboBox()
        value_row = QHBoxLayout()
        value_row.addWidget(self.value_edit, 1)
        value_row.addWidget(self.unit_combo)
        form.addRow("Value", value_row)
        layout.addLayout(form)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        layout.addWidget(self.slider)
        self.range_label = QLabel("")
        self.range_label.setStyleSheet("color:#94a3b8;font-size:10px")
        layout.addWidget(self.range_label)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#dc2626;font-size:11px")
        layout.addWidget(self.error_label)

        row = QHBoxLayout()
        self.parallel_button = QPushButton("Add parallel")
        self.rotate_button = QPushButton("Rotate")
        self.delete_button = QPushButton("Delete")
        self.delete_button.setStyleSheet("color:#dc2626")
        row.addWidget(self.parallel_button)
        row.addWidget(self.rotate_button)
        row.addWidget(self.delete_button)
        layout.addLayout(row)

        self.value_edit.editingFinished.connect(self._commit_value)
        self.unit_combo.currentTextChanged.connect(self._unit_changed)
        self.slider.valueChanged.connect(self._slider_changed)
        self.delete_button.clicked.connect(self._delete)
        self.rotate_button.clicked.connect(self._rotate)
        self.parallel_button.clicked.connect(self._parallel)
        self.setEnabled(False)

    def set_component(self, component: Component) -> None:
        self.component = component
        self._si_value = component.value
        self.setEnabled(True)
        self.heading.setText(f"SELECTED · {component.id}")
        units = _UNITS[component.kind.value]
        self.unit_combo.blockSignals(True)
        self.unit_combo.clear()
        self.unit_combo.addItems(list(units))
        preferred = self._preferred_unit(component)
        self.unit_combo.setCurrentText(preferred)
        self.unit_combo.blockSignals(False)
        self._show_si_value()
        self.sync_slider_to_value()
        low, high = _RANGES[component.kind.value]
        self.range_label.setText(f"Range: {low:g} to {high:g} SI")
        self.error_label.clear()

    def clear_component(self) -> None:
        self.component = None
        self.heading.setText("SELECT A COMPONENT")
        self.value_edit.clear()
        self.setEnabled(False)

    def _preferred_unit(self, component: Component) -> str:
        value = component.value
        if isinstance(component, Capacitor):
            if value < 1e-9:
                return "pF"
            if value < 1e-6:
                return "nF"
            if value < 1e-3:
                return "μF"
            if value < 1:
                return "mF"
            return "F"
        if isinstance(component, Inductor):
            if value < 1e-3:
                return "μH"
            if value < 1:
                return "mH"
            return "H"
        if value >= 1e6:
            return "MΩ"
        if value >= 1e3:
            return "kΩ"
        return "Ω"

    def _show_si_value(self) -> None:
        if self.component is None:
            return
        factor = _UNITS[self.component.kind.value][self.unit_combo.currentText()]
        self.value_edit.setText(f"{self._si_value / factor:.12g}")

    def _unit_changed(self) -> None:
        self._show_si_value()

    def _commit_value(self) -> None:
        if self.component is None or not self.value_edit.text():
            return
        factor = _UNITS[self.component.kind.value][self.unit_combo.currentText()]
        value = float(self.value_edit.text()) * factor
        if not math.isfinite(value) or value <= 0:
            self.error_label.setText("Enter a positive finite value.")
            return
        self.error_label.clear()
        self._si_value = value
        self.sync_slider_to_value()
        self.value_changed.emit(self.component.id, value)

    def sync_slider_to_value(self) -> None:
        if self.component is None:
            return
        low, high = _RANGES[self.component.kind.value]
        clipped = min(high, max(low, self._si_value))
        position = round(
            1000 * (math.log10(clipped) - math.log10(low)) / (math.log10(high) - math.log10(low))
        )
        self.slider.blockSignals(True)
        self.slider.setValue(position)
        self.slider.blockSignals(False)

    def _slider_changed(self, position: int) -> None:
        if self.component is None:
            return
        low, high = _RANGES[self.component.kind.value]
        exponent = math.log10(low) + position / 1000 * (math.log10(high) - math.log10(low))
        self._si_value = 10**exponent
        self._show_si_value()
        self.value_changed.emit(self.component.id, self._si_value)

    def _delete(self) -> None:
        if self.component is not None:
            self.delete_requested.emit(self.component.id)

    def _rotate(self) -> None:
        if self.component is not None:
            self.rotate_requested.emit(self.component.id)

    def _parallel(self) -> None:
        if self.component is not None:
            self.parallel_requested.emit(self.component.id)
