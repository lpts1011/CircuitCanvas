"""Selected-component value editor with SI units and logarithmic slider."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
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

from circuitcanvas.domain.components import Component

from .formatting import BASE_UNITS, format_component_value, parse_quantity

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
    # Slider moves carry a session number; equal numbers belong to one gesture
    # and are recorded as a single undo step.
    value_adjusted = Signal(str, float, int)
    delete_requested = Signal(str)
    rotate_requested = Signal(str)
    parallel_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.component: Component | None = None
        self._si_value = 0.0
        self._slider_session = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.heading = QLabel("SELECT A COMPONENT")
        self.heading.setStyleSheet(
            "font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px"
        )
        layout.addWidget(self.heading)
        self.empty_hint = QLabel(
            "Click a component on the canvas to change its value, rotate it, "
            "or add a parallel copy.\n\nTip: double-click a component to jump "
            "straight to its value."
        )
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setStyleSheet("color:#64748b;padding:6px 0")
        layout.addWidget(self.empty_hint)

        self.editor = QWidget()
        editor_layout = QVBoxLayout(self.editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)
        layout.addStretch()

        form = QFormLayout()
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("e.g. 4.7k, 10u, 4k7")
        self.value_edit.setToolTip(
            "Type a number, optionally with a prefix or unit:\n"
            "4.7k or 4k7 = 4 700, 10u = 10 μ, 2.2M = 2.2 mega, 15m = 15 milli.\n"
            "A plain number uses the unit chosen on the right."
        )
        self.unit_combo = QComboBox()
        self.unit_combo.setToolTip("Unit for plain numbers typed on the left")
        value_row = QHBoxLayout()
        value_row.addWidget(self.value_edit, 1)
        value_row.addWidget(self.unit_combo)
        form.addRow("Value", value_row)
        editor_layout.addLayout(form)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setToolTip("Drag to sweep the value on a logarithmic scale")
        editor_layout.addWidget(self.slider)
        self.range_label = QLabel("")
        self.range_label.setStyleSheet("color:#94a3b8;font-size:10px")
        editor_layout.addWidget(self.range_label)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#dc2626;font-size:11px")
        editor_layout.addWidget(self.error_label)

        row = QHBoxLayout()
        self.parallel_button = QPushButton("Add parallel")
        self.parallel_button.setToolTip("Add a copy of this component connected in parallel")
        self.rotate_button = QPushButton("Rotate")
        self.rotate_button.setToolTip("Rotate 90° (R)")
        self.delete_button = QPushButton("Delete")
        self.delete_button.setToolTip("Remove this component (Delete or Backspace)")
        self.delete_button.setStyleSheet("color:#dc2626")
        row.addWidget(self.parallel_button)
        row.addWidget(self.rotate_button)
        row.addWidget(self.delete_button)
        editor_layout.addLayout(row)

        self.value_edit.editingFinished.connect(self._commit_value)
        self.unit_combo.currentTextChanged.connect(self._unit_changed)
        self.slider.valueChanged.connect(self._slider_changed)
        self.slider.sliderPressed.connect(self._start_slider_session)
        self.delete_button.clicked.connect(self._delete)
        self.rotate_button.clicked.connect(self._rotate)
        self.parallel_button.clicked.connect(self._parallel)
        self.editor.hide()

    def set_component(self, component: Component) -> None:
        if self.component is None or self.component.id != component.id:
            self._start_slider_session()
        self.component = component
        self._si_value = component.value
        self.empty_hint.hide()
        self.editor.show()
        self.heading.setText(f"{component.id} · {component.kind.value.upper()}")
        units = _UNITS[component.kind.value]
        self.unit_combo.blockSignals(True)
        self.unit_combo.clear()
        self.unit_combo.addItems(list(units))
        self.unit_combo.setCurrentText(self._preferred_unit(component.kind.value, component.value))
        self.unit_combo.blockSignals(False)
        self._show_si_value()
        self.sync_slider_to_value()
        low, high = _RANGES[component.kind.value]
        kind = component.kind.value
        self.range_label.setText(
            f"Slider range: {format_component_value(kind, low)}"
            f" – {format_component_value(kind, high)}"
        )
        self.error_label.clear()

    def clear_component(self) -> None:
        self.component = None
        self.heading.setText("SELECT A COMPONENT")
        self.value_edit.clear()
        self.range_label.clear()
        self.error_label.clear()
        self.editor.hide()
        self.empty_hint.show()

    def focus_value(self) -> None:
        """Put the cursor in the value field with its text selected, ready to type."""
        if self.component is not None:
            self.value_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            self.value_edit.selectAll()

    @staticmethod
    def _preferred_unit(kind: str, value: float) -> str:
        if kind == "capacitor":
            if value < 1e-9:
                return "pF"
            if value < 1e-6:
                return "nF"
            if value < 1e-3:
                return "μF"
            if value < 1:
                return "mF"
            return "F"
        if kind == "inductor":
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
        if self.component is None:
            return
        if not self.value_edit.text().strip():
            self._show_si_value()
            return
        kind = self.component.kind.value
        try:
            parsed = parse_quantity(self.value_edit.text(), BASE_UNITS[kind])
        except ValueError:
            self.error_label.setText(
                f"Couldn't read “{self.value_edit.text().strip()}”. Try 4.7k, 10u, 4k7 or 0.001."
            )
            return
        factor = _UNITS[kind][self.unit_combo.currentText()]
        value = parsed.value if parsed.scaled else parsed.value * factor
        if value <= 0:
            self.error_label.setText("The value must be greater than zero.")
            return
        self.error_label.clear()
        if parsed.scaled:
            # "4.7n" typed while showing μF: switch the unit so the field reads 4.7 nF.
            self.unit_combo.blockSignals(True)
            self.unit_combo.setCurrentText(self._preferred_unit(kind, value))
            self.unit_combo.blockSignals(False)
        unchanged = math.isclose(value, self._si_value, rel_tol=1e-12)
        self._si_value = value
        self._show_si_value()
        if unchanged:
            # Leaving the field without editing must not add an undo step.
            return
        self._start_slider_session()
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
        # Three significant figures: the slider yields 120 Ω, not 123.0268770812 Ω.
        self._si_value = float(f"{10**exponent:.3g}")
        self._show_si_value()
        self.value_adjusted.emit(self.component.id, self._si_value, self._slider_session)

    def _start_slider_session(self) -> None:
        self._slider_session += 1

    def _delete(self) -> None:
        if self.component is not None:
            self.delete_requested.emit(self.component.id)

    def _rotate(self) -> None:
        if self.component is not None:
            self.rotate_requested.emit(self.component.id)

    def _parallel(self) -> None:
        if self.component is not None:
            self.parallel_requested.emit(self.component.id)
