"""Transient curves, metrics, time cursor, and numeric data table."""

from __future__ import annotations

from typing import cast

import numpy as np
import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.solver.results import BranchResult

from .formatting import format_si, parse_quantity

_INVALID_INDEX = QModelIndex()


class TransientTableModel(QAbstractTableModel):
    HEADERS = ("Time (s)", "Voltage (V)", "Current (A)", "Power (W)", "Energy (J)")

    def __init__(self) -> None:
        super().__init__()
        self._columns = [np.array([], dtype=float) for _ in self.HEADERS]

    def set_data(self, time: np.ndarray, branch: BranchResult) -> None:
        self.beginResetModel()
        self._columns = [time, branch.voltage, branch.current, branch.power, branch.energy]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(self._columns[0])

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return f"{float(self._columns[index.column()][index.row()]):.6g}"

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return cast(object, super().headerData(section, orientation, role))


class AnalysisPanel(QWidget):
    time_index_changed = Signal(int)
    play_toggled = Signal(bool)
    speed_changed = Signal(float)
    auto_span_requested = Signal()
    manual_span_requested = Signal(float)

    MIN_SPAN_S = 1e-9
    MAX_SPAN_S = 1e5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.title = QLabel("Transient response")
        self.title.setStyleSheet("font-weight:700;color:#172033")
        self.metrics = QLabel("Select a component to inspect its response")
        self.metrics.setStyleSheet("color:#64748b")
        top.addWidget(self.title)
        top.addStretch()

        self._span_seconds = 0.1
        self._span_auto = True
        span_label = QLabel("Time span")
        span_label.setStyleSheet("color:#475569")
        self.span_edit = QLineEdit()
        self.span_edit.setFixedWidth(90)
        self.span_edit.setToolTip(
            "How much time to simulate after the battery is connected.\n"
            "Type a value such as 50 ms, 2 s or 200u."
        )
        self.span_auto = QCheckBox("Auto")
        self.span_auto.setChecked(True)
        self.span_auto.setToolTip(
            "Pick the time span from the circuit's time constants,\n"
            "so the whole charge, decay or oscillation is visible."
        )
        top.addWidget(span_label)
        top.addWidget(self.span_edit)
        top.addWidget(self.span_auto)
        top.addSpacing(12)

        self.play_button = QPushButton("▶ Play")
        self.play_button.setCheckable(True)
        self.play_button.setToolTip("Animate the response over time (the arrows show current flow)")
        self.speed_control = QDoubleSpinBox()
        self.speed_control.setRange(0.1, 10.0)
        self.speed_control.setSingleStep(0.5)
        self.speed_control.setValue(1.0)
        self.speed_control.setSuffix("×")
        self.speed_control.setFixedWidth(75)
        self.speed_control.setToolTip("Playback speed")
        top.addWidget(self.play_button)
        top.addWidget(self.speed_control)
        layout.addLayout(top)
        layout.addWidget(self.metrics)

        self.tabs = QTabWidget()
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget(background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.18)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Voltage", units="V", color="#2563eb")
        plot_item = self.plot.getPlotItem()
        plot_item.showAxis("right")
        plot_item.setLabel("right", "Current", units="A", color="#f97316")
        self.current_view = pg.ViewBox()
        plot_item.scene().addItem(self.current_view)
        plot_item.getAxis("right").linkToView(self.current_view)
        self.current_view.setXLink(plot_item)
        plot_item.vb.sigResized.connect(self._sync_current_view)
        legend = self.plot.addLegend(offset=(8, 8))
        self.voltage_curve = self.plot.plot(pen=pg.mkPen("#2563eb", width=2), name="Voltage (V)")
        self.current_curve = pg.PlotCurveItem(pen=pg.mkPen("#f97316", width=2))
        self.current_view.addItem(self.current_curve)
        legend.addItem(self.current_curve, "Current (A)")
        self._sync_current_view()
        plot_layout.addWidget(self.plot)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 0)
        plot_layout.addWidget(self.time_slider)
        self.tabs.addTab(plot_container, "Curves")

        self.table_model = TransientTableModel()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.table, "Data table")
        layout.addWidget(self.tabs)
        self.time_slider.valueChanged.connect(self.time_index_changed.emit)
        self.play_button.toggled.connect(self._play_toggled)
        self.speed_control.valueChanged.connect(self.speed_changed.emit)
        self.span_edit.editingFinished.connect(self._span_edited)
        self.span_auto.clicked.connect(self._span_auto_clicked)
        self.show_time_span(self._span_seconds, auto=True)

    def show_time_span(self, seconds: float, *, auto: bool) -> None:
        """Display the span used by the latest simulation without emitting requests."""
        self._span_seconds = seconds
        self._span_auto = auto
        self.span_edit.setText(format_si(seconds, "s", digits=3))
        self.span_auto.blockSignals(True)
        self.span_auto.setChecked(auto)
        self.span_auto.blockSignals(False)
        self.span_edit.setStyleSheet("")

    def _span_edited(self) -> None:
        text = self.span_edit.text()
        if text == format_si(self._span_seconds, "s", digits=3):
            return
        try:
            parsed = parse_quantity(text, "s")
        except ValueError:
            self.span_edit.setStyleSheet("border:1px solid #dc2626")
            self.span_edit.setToolTip("Could not read that time. Try 50 ms, 2 s or 200u.")
            return
        # A bare number keeps the unit that was on screen ("50" after "25 ms" is 50 ms).
        seconds = parsed.value if parsed.scaled else parsed.value * self._display_factor()
        seconds = min(self.MAX_SPAN_S, max(self.MIN_SPAN_S, seconds))
        self.show_time_span(seconds, auto=False)
        self.manual_span_requested.emit(seconds)

    @property
    def time_span(self) -> float:
        return self._span_seconds

    def _display_factor(self) -> float:
        unit = format_si(self._span_seconds, "s", digits=3).split()[-1]
        return parse_quantity(f"1 {unit}", "s").value

    def _span_auto_clicked(self, checked: bool) -> None:
        if checked:
            self.auto_span_requested.emit()
        else:
            self.manual_span_requested.emit(self._span_seconds)

    def _play_toggled(self, playing: bool) -> None:
        self.play_button.setText("⏸ Pause" if playing else "▶ Play")
        self.play_toggled.emit(playing)

    def set_playing(self, playing: bool) -> None:
        self.play_button.blockSignals(True)
        self.play_button.setChecked(playing)
        self.play_button.setText("⏸ Pause" if playing else "▶ Play")
        self.play_button.blockSignals(False)

    def _sync_current_view(self) -> None:
        plot_item = self.plot.getPlotItem()
        self.current_view.setGeometry(plot_item.vb.sceneBoundingRect())
        self.current_view.linkedViewChanged(plot_item.vb, self.current_view.XAxis)

    def set_branch(self, component_id: str, time: np.ndarray, branch: BranchResult) -> None:
        self.title.setText(f"{component_id} transient response")
        self.voltage_curve.setData(time, branch.voltage)
        self.current_curve.setData(time, branch.current)
        self.table_model.set_data(time, branch)
        self.time_slider.setRange(0, max(0, len(time) - 1))
        self.time_slider.setValue(max(0, len(time) - 1))
        self.metrics.setText(
            f"Peak current {format_si(float(np.max(np.abs(branch.current))), 'A')}   ·   "
            f"Final voltage {format_si(float(branch.voltage[-1]), 'V')}   ·   "
            f"Stored energy {format_si(float(branch.energy[-1]), 'J')}"
        )

    def clear(self) -> None:
        self.title.setText("Transient response")
        self.metrics.setText("Select a component to inspect its response")
        self.voltage_curve.setData([], [])
        self.current_curve.setData([], [])
        empty = np.array([], dtype=float)
        self.table_model.set_data(empty, BranchResult(empty, empty, empty, empty))
        self.time_slider.setRange(0, 0)
