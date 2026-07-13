"""Main CircuitCanvas desktop window."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.serialization import CircuitFileError, load_circuit, save_circuit
from circuitcanvas.solver.equations import build_equation_report
from circuitcanvas.solver.results import SimulationResult
from circuitcanvas.solver.validation import Diagnostic
from circuitcanvas.solver.wire_flow import reconstruct_wire_flows

from .analysis_panel import AnalysisPanel
from .circuit_scene import CircuitScene, CircuitView
from .equation_panel import EquationPanel
from .export import export_branch_csv, export_scene_png
from .inspector import ComponentInspector
from .palette import ComponentPalette
from .playback import PlaybackController
from .simulation_controller import SimulationController


class MainWindow(QMainWindow):
    def __init__(self, *, debounce_ms: int = 150) -> None:
        super().__init__()
        self.setWindowTitle("CircuitCanvas — Interactive RLC Simulator")
        self.resize(1420, 880)
        self.circuit = Circuit.new(12.0)
        self.current_result: SimulationResult | None = None
        self.current_time_index = 0
        self._current_path: Path | None = None

        self.scene = CircuitScene(self.circuit)
        self.view = CircuitView(self.scene)
        self.analysis = AnalysisPanel()
        self.component_palette = ComponentPalette()
        self.inspector = ComponentInspector()
        self.equations = EquationPanel()
        self.controller = SimulationController(debounce_ms=debounce_ms, parent=self)
        self.playback = PlaybackController(self)

        self._build_toolbar()
        self._build_layout()
        self._connect_signals()
        self.controller.request(self.circuit.revision, self.circuit.snapshot())

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.reset_circuit)
        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.undo)
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.redo)
        image_action = QAction("Export PNG", self)
        image_action.triggered.connect(self.export_png)
        data_action = QAction("Export CSV", self)
        data_action.triggered.connect(self.export_csv)
        for action in (
            new_action,
            open_action,
            save_action,
            undo_action,
            redo_action,
            image_action,
            data_action,
        ):
            toolbar.addAction(action)
        toolbar.addSeparator()
        brand = QLabel("  ⚡ CircuitCanvas")
        brand.setStyleSheet("font-size:16px;font-weight:700;color:#dbeafe;background:transparent")
        toolbar.addWidget(brand)

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        center = QSplitter(Qt.Orientation.Vertical)
        center.addWidget(self.view)
        analysis_frame = QFrame()
        analysis_layout = QVBoxLayout(analysis_frame)
        analysis_layout.setContentsMargins(16, 12, 16, 12)
        analysis_layout.addWidget(self.analysis)
        center.addWidget(analysis_frame)
        center.setSizes([590, 270])

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(320)
        sidebar.setMaximumWidth(390)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 20, 20, 20)
        side.setSpacing(18)

        source_heading = QLabel("DC SOURCE")
        source_heading.setStyleSheet(
            "font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px"
        )
        side.addWidget(source_heading)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Battery voltage"))
        self.source_voltage = QDoubleSpinBox()
        self.source_voltage.setRange(0.001, 1000.0)
        self.source_voltage.setDecimals(3)
        self.source_voltage.setValue(12.0)
        self.source_voltage.setSuffix(" V")
        source_row.addWidget(self.source_voltage)
        side.addLayout(source_row)
        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.addTab(self.component_palette, "Components")
        self.sidebar_tabs.addTab(self.inspector, "Inspector")
        self.sidebar_tabs.addTab(self.equations, "Equations")
        self.sidebar_tabs.setMinimumHeight(460)
        side.addWidget(self.sidebar_tabs, 1)
        side.addWidget(self._separator())
        summary_heading = QLabel("CIRCUIT SUMMARY")
        summary_heading.setStyleSheet(
            "font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px"
        )
        side.addWidget(summary_heading)
        self.summary_label = QLabel("Waiting for a complete circuit")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color:#475569;line-height:1.4")
        side.addWidget(self.summary_label)
        side.addStretch()
        self.status_label = QLabel("Open circuit · add a component")
        self.status_label.setWordWrap(True)
        side.addWidget(self.status_label)

        splitter.addWidget(center)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        root_layout.addWidget(splitter)
        self.setCentralWidget(root)

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e2e8f0")
        return line

    def _connect_signals(self) -> None:
        self.component_palette.component_clicked.connect(self.add_component)
        self.scene.circuit_changed.connect(self._circuit_changed)
        self.scene.selection_changed.connect(self._selection_changed)
        self.inspector.value_changed.connect(self._update_value)
        self.inspector.delete_requested.connect(self._delete_component)
        self.inspector.parallel_requested.connect(self._duplicate_parallel)
        self.analysis.time_index_changed.connect(self._time_index_changed)
        self.source_voltage.valueChanged.connect(self._source_changed)
        self.controller.result_ready.connect(self._apply_result)
        self.controller.diagnostics_ready.connect(self._apply_diagnostics)
        self.equations.equation_selected.connect(self.scene.highlight_equation)
        self.analysis.play_toggled.connect(self.playback.set_playing)
        self.analysis.speed_changed.connect(self.playback.set_speed)
        self.playback.playing_changed.connect(self.analysis.set_playing)
        self.playback.animation_tick.connect(self.scene.advance_arrows)
        self.playback.time_index_changed.connect(self.analysis.time_slider.setValue)

    def add_component(self, kind: str) -> str:
        return self.scene.insert_component_for_test(kind)

    def _circuit_changed(self, revision: int) -> None:
        self.circuit = self.scene.circuit
        self.controller.request(revision, self.circuit.snapshot())

    def _selection_changed(self, component_id: str) -> None:
        component = self.circuit.components.get(component_id)
        if component is None:
            return
        self.inspector.set_component(component)
        if self.current_result is not None and component_id in self.current_result.branches:
            self.analysis.set_branch(
                component_id,
                self.current_result.time,
                self.current_result.branches[component_id],
            )
        self.equations.reveal_component(component_id)

    def _update_value(self, component_id: str, value: float) -> None:
        self.scene.command_stack.update_value(component_id, value)
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _delete_component(self, component_id: str) -> None:
        self.scene.command_stack.delete(component_id)
        self.inspector.clear_component()
        self.analysis.clear()
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _duplicate_parallel(self, component_id: str) -> None:
        component = self.circuit.components[component_id]
        self.scene.insert_component_for_test(component.kind, parallel_to=component_id)

    def _source_changed(self, voltage: float) -> None:
        self.circuit.source = replace(self.circuit.source, voltage=voltage)
        self.circuit.revision += 1
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _apply_result(self, revision: int, result: SimulationResult) -> None:
        if revision != self.circuit.revision:
            return
        self.current_result = result
        index = len(result.time) - 1
        self.current_time_index = index
        self.playback.set_timeline(samples=len(result.time), duration=float(result.time[-1]))
        self.scene.set_result(result, index)
        snapshot = self.circuit.snapshot()
        self.equations.set_report(build_equation_report(snapshot, result, index))
        flows = reconstruct_wire_flows(snapshot, result, index)
        self.scene.set_wire_currents(dict(flows.currents))
        selected = self.scene.selected_component_id()
        if selected is not None and selected in result.branches:
            self.analysis.set_branch(selected, result.time, result.branches[selected])
        current = abs(float(result.source_current[-1]))
        power = abs(float(result.source_power[-1]))
        energy = float(result.metrics["stored_energy_j"])
        self.summary_label.setText(
            f"Source: {self.circuit.source.voltage:g} V DC\n"
            f"Total current: {current:.5g} A\n"
            f"Total power: {power:.5g} W\n"
            f"Stored energy: {energy:.5g} J\n"
            f"Components: {len(self.circuit.components)}"
        )
        self.status_label.setText("✓ Circuit valid · transient solution converged")
        self.status_label.setStyleSheet(
            "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;"
            "padding:10px;border-radius:9px"
        )

    def _apply_diagnostics(self, revision: int, diagnostics: tuple[Diagnostic, ...]) -> None:
        if revision != self.circuit.revision:
            return
        first = diagnostics[0]
        self.status_label.setText(f"⚠ {first.message}")
        self.status_label.setStyleSheet(
            "background:#fff7ed;color:#9a3412;border:1px solid #fed7aa;"
            "padding:10px;border-radius:9px"
        )
        self.summary_label.setText("Waiting for a valid closed circuit")
        self.equations.clear()
        self.playback.set_playing(False)

    def _time_index_changed(self, index: int) -> None:
        if self.current_result is not None:
            self.current_time_index = index
            self.scene.set_result(self.current_result, index)
            snapshot = self.circuit.snapshot()
            self.equations.set_report(build_equation_report(snapshot, self.current_result, index))
            flows = reconstruct_wire_flows(snapshot, self.current_result, index)
            self.scene.set_wire_currents(dict(flows.currents))

    def undo(self) -> None:
        if self.scene.command_stack.undo():
            self.scene.rebuild()
            self._circuit_changed(self.circuit.revision)

    def redo(self) -> None:
        if self.scene.command_stack.redo():
            self.scene.rebuild()
            self._circuit_changed(self.circuit.revision)

    def reset_circuit(self) -> None:
        self._current_path = None
        self._replace_circuit(Circuit.new(self.source_voltage.value()))

    def _replace_circuit(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self.current_result = None
        self.scene.replace_circuit(circuit)
        self.inspector.clear_component()
        self.analysis.clear()
        self.equations.clear()
        self.source_voltage.blockSignals(True)
        self.source_voltage.setValue(circuit.source.voltage)
        self.source_voltage.blockSignals(False)
        self.controller.request(circuit.revision, circuit.snapshot())

    def save_file(self) -> None:
        path = self._current_path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save circuit", "circuit.circuitcanvas", "CircuitCanvas (*.circuitcanvas)"
            )
            if not filename:
                return
            path = Path(filename)
        save_circuit(path, self.circuit)
        self._current_path = path

    def open_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open circuit", "", "CircuitCanvas (*.circuitcanvas *.json)"
        )
        if not filename:
            return
        try:
            circuit = load_circuit(filename)
        except CircuitFileError as exc:
            QMessageBox.warning(self, "Could not open circuit", str(exc))
            return
        self._current_path = Path(filename)
        self._replace_circuit(circuit)

    def export_png(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export circuit image", "circuit.png", "PNG image (*.png)"
        )
        if filename:
            export_scene_png(filename, self.scene)

    def export_csv(self) -> None:
        selected = self.scene.selected_component_id()
        if self.current_result is None or selected is None:
            QMessageBox.information(
                self,
                "Select a component",
                "Select a component with a valid simulation result before exporting data.",
            )
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export transient data", f"{selected}.csv", "CSV data (*.csv)"
        )
        if filename:
            export_branch_csv(filename, self.current_result, selected)
