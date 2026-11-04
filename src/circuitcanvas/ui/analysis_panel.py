"""Graphs of voltage and current over time, with a time cursor, plus the data table."""

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
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.solver.results import BranchResult

from .formatting import format_si, parse_quantity
from .theme import BORDER, CURRENT, DANGER, TEXT_MUTED, TEXT_SECONDARY, VOLTAGE

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


def _styled_plot(plot: pg.PlotItem, label: str, units: str, color: str) -> None:
    plot.showGrid(x=True, y=True, alpha=0.12)
    plot.setMenuEnabled(False)
    plot.hideButtons()
    plot.setMouseEnabled(x=False, y=False)
    # The name sits above the plot; the rotated axis label carries only the unit
    # (with its prefix, e.g. mA), so short plots never overlap their labels.
    plot.setTitle(label, color=color, size="9pt", bold=True, justify="left")
    plot.setLabel("left", units=units, color=color)
    for side in ("left", "bottom"):
        axis = plot.getAxis(side)
        axis.setPen(pg.mkPen(BORDER))
        axis.setTextPen(pg.mkPen(TEXT_SECONDARY))
    # Equal widths keep the two plots' time axes exactly aligned.
    plot.getAxis("left").setWidth(64)


class AnalysisPanel(QWidget):
    """Shows how one thing (a component, or the battery) behaves over the simulated time."""

    #: The user dragged the time cursor on a graph to this sample.
    cursor_index_changed = Signal(int)
    auto_span_requested = Signal()
    manual_span_requested = Signal(float)

    MIN_SPAN_S = 1e-9
    MAX_SPAN_S = 1e5
    _PLACEHOLDER, _GRAPHS, _TABLE = range(3)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._time = np.array([], dtype=float)
        self._moving_cursor = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title = QLabel("Over time")
        self.title.setObjectName("sectionTitle")
        self.metrics = QLabel("")
        self.metrics.setObjectName("muted")
        titles.addWidget(self.title)
        titles.addWidget(self.metrics)
        header.addLayout(titles)
        header.addStretch()

        self.graphs_button = QToolButton()
        self.graphs_button.setText("Graphs")
        self.table_button = QToolButton()
        self.table_button.setText("Table")
        self.view_group = QButtonGroup(self)
        for button in (self.graphs_button, self.table_button):
            button.setObjectName("segment")
            button.setCheckable(True)
            self.view_group.addButton(button)
            header.addWidget(button)
        self.graphs_button.setChecked(True)
        self.table_button.setToolTip("Every simulated sample as numbers")
        header.addSpacing(14)

        self._span_seconds = 0.1
        self._span_auto = True
        span_label = QLabel("Time span")
        span_label.setObjectName("muted")
        self.span_edit = QLineEdit()
        self.span_edit.setFixedWidth(84)
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
        header.addWidget(span_label)
        header.addWidget(self.span_edit)
        header.addWidget(self.span_auto)
        layout.addLayout(header)

        self.body = QStackedWidget()
        self.placeholder = QLabel()
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet(f"color:{TEXT_MUTED};font-size:13px")
        self.body.addWidget(self.placeholder)

        self.plots = pg.GraphicsLayoutWidget()
        self.plots.setBackground("w")
        self.plots.ci.setSpacing(4)
        self.voltage_plot = self.plots.addPlot(row=0, col=0)
        self.current_plot = self.plots.addPlot(row=1, col=0)
        self.current_plot.setXLink(self.voltage_plot)
        _styled_plot(self.voltage_plot, "Voltage", "V", VOLTAGE)
        _styled_plot(self.current_plot, "Current", "A", CURRENT)
        self.voltage_plot.getAxis("bottom").setStyle(showValues=False)
        self.current_plot.setLabel("bottom", "Time", units="s", color=TEXT_SECONDARY)
        self.voltage_curve = self.voltage_plot.plot(pen=pg.mkPen(VOLTAGE, width=2))
        self.current_curve = self.current_plot.plot(pen=pg.mkPen(CURRENT, width=2))
        self.cursors = []
        for plot in (self.voltage_plot, self.current_plot):
            cursor = pg.InfiniteLine(
                angle=90,
                movable=True,
                pen=pg.mkPen("#64748b", width=1, style=Qt.PenStyle.DashLine),
                hoverPen=pg.mkPen("#0f172a", width=2),
            )
            cursor.setToolTip("Drag to see the circuit at another moment")
            cursor.sigPositionChanged.connect(self._cursor_dragged)
            plot.addItem(cursor)
            self.cursors.append(cursor)
        self.body.addWidget(self.plots)

        self.table_model = TransientTableModel()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.body.addWidget(self.table)
        layout.addWidget(self.body, 1)

        self.view_group.buttonClicked.connect(lambda _button: self._show_current_view())
        self.span_edit.editingFinished.connect(self._span_edited)
        self.span_auto.clicked.connect(self._span_auto_clicked)
        self.show_time_span(self._span_seconds, auto=True)
        self.clear()

    # ----- Content ------------------------------------------------------------------

    def set_branch(
        self, name: str, time: np.ndarray, branch: BranchResult, *, title: str | None = None
    ) -> None:
        """Plot one component (or the battery) and fill the table with its samples."""
        self._time = time
        self.title.setText(title or f"{name} over time")
        self.voltage_curve.setData(time, branch.voltage)
        self.current_curve.setData(time, branch.current)
        self.voltage_plot.setXRange(0.0, float(time[-1]) if len(time) else 1.0, padding=0.01)
        self.table_model.set_data(time, branch)
        peak = float(np.max(np.abs(branch.current))) if len(time) else 0.0
        final = float(branch.voltage[-1]) if len(time) else 0.0
        self.metrics.setText(
            f"Peak current {format_si(peak, 'A')}   ·   Final voltage {format_si(final, 'V')}"
        )
        self._show_current_view()

    def show_placeholder(self, text: str) -> None:
        """Replace stale graphs with a short explanation."""
        self._time = np.array([], dtype=float)
        self.title.setText("Over time")
        self.metrics.setText("")
        self.voltage_curve.setData([], [])
        self.current_curve.setData([], [])
        empty = np.array([], dtype=float)
        self.table_model.set_data(empty, BranchResult(empty, empty, empty, empty))
        self.placeholder.setText(text)
        self.body.setCurrentIndex(self._PLACEHOLDER)

    def clear(self) -> None:
        self.show_placeholder("Add a component to see how it behaves over time.")

    @property
    def showing_placeholder(self) -> bool:
        return self.body.currentIndex() == self._PLACEHOLDER

    def _show_current_view(self) -> None:
        if not len(self._time):
            return
        self.body.setCurrentIndex(self._TABLE if self.table_button.isChecked() else self._GRAPHS)

    # ----- Time cursor --------------------------------------------------------------

    def set_cursor_index(self, index: int) -> None:
        """Move the dashed time line to a sample without emitting ``cursor_index_changed``."""
        if not len(self._time):
            return
        position = float(self._time[max(0, min(index, len(self._time) - 1))])
        self._moving_cursor = True
        try:
            for cursor in self.cursors:
                cursor.setValue(position)
        finally:
            self._moving_cursor = False
        self.table.selectRow(index)

    def _cursor_dragged(self, line: pg.InfiniteLine) -> None:
        if self._moving_cursor or not len(self._time):
            return
        index = int(np.argmin(np.abs(self._time - float(line.value()))))
        self.set_cursor_index(index)
        self.cursor_index_changed.emit(index)

    # ----- Time span ----------------------------------------------------------------

    def show_time_span(self, seconds: float, *, auto: bool) -> None:
        """Display the span used by the latest simulation without emitting requests."""
        self._span_seconds = seconds
        self._span_auto = auto
        self.span_edit.setText(format_si(seconds, "s", digits=3))
        self.span_auto.blockSignals(True)
        self.span_auto.setChecked(auto)
        self.span_auto.blockSignals(False)
        self.span_edit.setStyleSheet("")

    @property
    def time_span(self) -> float:
        return self._span_seconds

    def _span_edited(self) -> None:
        text = self.span_edit.text()
        if text == format_si(self._span_seconds, "s", digits=3):
            return
        try:
            parsed = parse_quantity(text, "s")
        except ValueError:
            self.span_edit.setStyleSheet(f"border:1px solid {DANGER}")
            self.span_edit.setToolTip("Could not read that time. Try 50 ms, 2 s or 200u.")
            return
        # A bare number keeps the unit that was on screen ("50" after "25 ms" is 50 ms).
        seconds = parsed.value if parsed.scaled else parsed.value * self._display_factor()
        seconds = min(self.MAX_SPAN_S, max(self.MIN_SPAN_S, seconds))
        self.show_time_span(seconds, auto=False)
        self.manual_span_requested.emit(seconds)

    def _display_factor(self) -> float:
        unit = format_si(self._span_seconds, "s", digits=3).split()[-1]
        return parse_quantity(f"1 {unit}", "s").value

    def _span_auto_clicked(self, checked: bool) -> None:
        if checked:
            self.auto_span_requested.emit()
        else:
            self.manual_span_requested.emit(self._span_seconds)
