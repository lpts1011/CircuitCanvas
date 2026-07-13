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
    QHBoxLayout,
    QLabel,
    QSlider,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.solver.results import BranchResult

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
        top.addWidget(self.metrics)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget(background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.18)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.addLegend(offset=(8, 8))
        self.voltage_curve = self.plot.plot(pen=pg.mkPen("#2563eb", width=2), name="Voltage (V)")
        self.current_curve = self.plot.plot(pen=pg.mkPen("#f97316", width=2), name="Current (A)")
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

    def set_branch(self, component_id: str, time: np.ndarray, branch: BranchResult) -> None:
        self.title.setText(f"{component_id} transient response")
        self.voltage_curve.setData(time, branch.voltage)
        self.current_curve.setData(time, branch.current)
        self.table_model.set_data(time, branch)
        self.time_slider.setRange(0, max(0, len(time) - 1))
        self.time_slider.setValue(max(0, len(time) - 1))
        self.metrics.setText(
            f"Peak |I| {np.max(np.abs(branch.current)):.4g} A   ·   "
            f"Final V {branch.voltage[-1]:.4g} V   ·   Energy {branch.energy[-1]:.4g} J"
        )

    def clear(self) -> None:
        self.title.setText("Transient response")
        self.metrics.setText("Select a component to inspect its response")
        self.voltage_curve.setData([], [])
        self.current_curve.setData([], [])
        empty = np.array([], dtype=float)
        self.table_model.set_data(empty, BranchResult(empty, empty, empty, empty))
        self.time_slider.setRange(0, 0)
