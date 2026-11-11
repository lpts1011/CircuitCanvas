"""Main CircuitCanvas desktop window."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.serialization import CircuitFileError, load_circuit, save_circuit
from circuitcanvas.examples import EXAMPLES, Example, load_example
from circuitcanvas.solver.equations import EquationLine, build_equation_report
from circuitcanvas.solver.results import BranchResult, SimulationResult
from circuitcanvas.solver.validation import Diagnostic
from circuitcanvas.solver.wire_flow import reconstruct_wire_flows

from .analysis_panel import AnalysisPanel
from .circuit_scene import CircuitScene, CircuitView
from .details_panel import DetailsPanel
from .equation_panel import EquationPanel
from .export import export_all_branches_csv, export_branch_csv, export_scene_png
from .formatting import format_si
from .help import ABOUT_HTML, QUICK_START_HTML, HelpDialog, shortcuts_html
from .icons import icon
from .inspector import ComponentInspector
from .messages import describe, describe_bypassed
from .palette import ComponentPalette
from .playback import PlaybackController
from .simulation_controller import SimulationController
from .theme import KIND_NAMES
from .time_bar import TimeBar


class MainWindow(QMainWindow):
    """Canvas in the middle, components on the left, details on the right, graphs below."""

    def __init__(self, *, debounce_ms: int = 150) -> None:
        super().__init__()
        self.setMinimumSize(1000, 640)
        self._fit_to_screen(1440, 900)
        self.circuit = Circuit.starter_loop(12.0)
        self.current_result: SimulationResult | None = None
        self.current_time_index = 0
        self._current_path: Path | None = None
        self._source_edit_session = 0
        self._untitled_name = "Untitled"
        self._help_dialog: HelpDialog | None = None
        self._initial_fit_done = False

        self.scene = CircuitScene(self.circuit)
        self.view = CircuitView(self.scene)
        self.analysis = AnalysisPanel()
        self.component_palette = ComponentPalette()
        self.inspector = ComponentInspector()
        self.details = DetailsPanel(self.inspector)
        self.source_voltage = self.details.source_voltage
        self.status_label = self.details.status_label
        self.equations = EquationPanel()
        self.time_bar = TimeBar()
        self.controller = SimulationController(debounce_ms=debounce_ms, parent=self)
        self.playback = PlaybackController(self)

        self._build_actions()
        self._build_toolbar()
        self._build_menus()
        self._build_layout()
        self._connect_signals()
        # Shows hints on hover and confirmations such as "Saved …".
        self.statusBar().setSizeGripEnabled(False)
        self._update_title()
        self.details.set_status("info", "Working out the circuit…")
        self.details.clear_readings(0)
        self.controller.request(self.circuit.revision, self.circuit.snapshot())

    def _fit_to_screen(self, width: int, height: int) -> None:
        """Open at the preferred size, but never larger than the screen's free area."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(width, height)
            return
        available = screen.availableGeometry()
        size = QSize(min(width, available.width() - 24), min(height, available.height() - 24))
        self.resize(size)
        self.move(
            available.x() + (available.width() - self.width()) // 2,
            available.y() + (available.height() - self.height()) // 2,
        )

    # ----- Actions, toolbar, menus ------------------------------------------------------

    def _action(
        self,
        text: str,
        slot: Callable[[], object],
        tip: str,
        shortcuts: Sequence[QKeySequence | QKeySequence.StandardKey | str] = (),
        *,
        button_text: str | None = None,
        icon_name: str | None = None,
    ) -> QAction:
        """Create an action; ``text`` is the menu label, ``button_text`` the toolbar label."""
        action = QAction(text, self)
        if button_text is not None:
            action.setIconText(button_text)
        if icon_name is not None:
            action.setIcon(icon(icon_name))
        # Some standard keys have no binding on some platforms (e.g. Save As on Windows).
        keys: list[QKeySequence] = []
        for shortcut in shortcuts:
            key = QKeySequence(shortcut)
            if not key.isEmpty() and key not in keys:
                keys.append(key)
        action.setShortcuts(keys)
        if keys:
            hint = keys[0].toString(QKeySequence.SequenceFormat.NativeText)
            tip = f"{tip} ({hint})"
        action.setToolTip(tip)
        action.setStatusTip(tip)
        action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        standard = QKeySequence.StandardKey
        self.new_action = self._action(
            "New", self.reset_circuit, "Start a new circuit", [standard.New], icon_name="new"
        )
        self.open_action = self._action(
            "Open…",
            self.open_file,
            "Open a saved circuit",
            [standard.Open],
            button_text="Open",
            icon_name="open",
        )
        self.save_action = self._action(
            "Save", self.save_file, "Save the circuit", [standard.Save], icon_name="save"
        )
        self.save_as_action = self._action(
            "Save As…",
            self.save_file_as,
            "Save the circuit to a new file",
            [standard.SaveAs, "Ctrl+Shift+S"],
            button_text="Save As",
        )
        self.undo_action = self._action(
            "Undo", self.undo, "Undo the last edit", [standard.Undo], icon_name="undo"
        )
        self.redo_action = self._action(
            "Redo", self.redo, "Redo the last undone edit", [standard.Redo], icon_name="redo"
        )
        self.rotate_action = self._action(
            "Rotate",
            self.scene.rotate_selected,
            "Rotate the selected component 90°",
            ["R"],
            icon_name="rotate",
        )
        self.delete_action = self._action(
            "Delete",
            self._delete_selected,
            "Delete the selected components, wires, junctions, or bends",
            [QKeySequence(Qt.Key.Key_Delete), QKeySequence(Qt.Key.Key_Backspace)],
            icon_name="trash",
        )
        self.deselect_action = self._action(
            "Deselect", self._escape, "Stop drawing a wire, or deselect everything", ["Esc"]
        )
        self.play_action = self._action(
            "Play or Pause", self.time_bar.play_button.toggle, "Play or pause", ["Space"]
        )
        self.fit_action = self._action(
            "Fit View", self.view.fit_circuit, "Show the whole circuit", ["Ctrl+0"], icon_name="fit"
        )
        self.zoom_in_action = self._action(
            "Zoom In",
            self.view.zoom_in,
            "Zoom in",
            [standard.ZoomIn, "Ctrl+="],
            icon_name="zoom-in",
        )
        self.zoom_out_action = self._action(
            "Zoom Out", self.view.zoom_out, "Zoom out", [standard.ZoomOut], icon_name="zoom-out"
        )
        self.export_png_action = self._action(
            "Export Picture (PNG)…",
            self.export_png,
            "Save a picture of the circuit",
            button_text="Export PNG",
        )
        self.export_csv_action = self._action(
            "Export Data (CSV)…",
            self.export_csv,
            "Save the time-series data as a spreadsheet: the selected component, "
            "or every component when nothing is selected",
            button_text="Export CSV",
        )
        self.quit_action = self._action(
            "Quit CircuitCanvas", self.close, "Quit CircuitCanvas", [standard.Quit]
        )
        self.quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        self.quick_start_action = self._action(
            "Quick Start Guide",
            self.show_quick_start,
            "How to build and read a circuit",
            [standard.HelpContents, "F1"],
            button_text="Help",
            icon_name="help",
        )
        self.shortcuts_action = self._action(
            "Keyboard Shortcuts", self.show_shortcuts, "Every shortcut and mouse gesture"
        )
        self.about_action = self._action(
            "About CircuitCanvas", self.show_about, "Version and license"
        )
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        # Shortcuts work anywhere in the window, whether or not a menu shows the action.
        self.addActions(self._all_actions())

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.addToolBar(toolbar)
        toolbar.addActions([self.new_action, self.open_action, self.save_action])
        toolbar.addSeparator()
        toolbar.addActions([self.undo_action, self.redo_action])
        toolbar.addSeparator()
        self.time_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self.time_bar)
        toolbar.addSeparator()
        toolbar.addAction(self.quick_start_action)
        help_button = toolbar.widgetForAction(self.quick_start_action)
        if help_button is not None:
            help_button.setProperty("toolButtonStyle", Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addActions([self.new_action, self.open_action])
        self.examples_menu = file_menu.addMenu("Open Example")
        for example in EXAMPLES:
            action = self.examples_menu.addAction(example.title)
            action.setToolTip(example.description)
            action.setStatusTip(example.description)
            action.triggered.connect(
                lambda checked=False, chosen=example: self.open_example(chosen)
            )
        self.examples_menu.setToolTipsVisible(True)
        file_menu.addSeparator()
        file_menu.addActions([self.save_action, self.save_as_action])
        file_menu.addSeparator()
        file_menu.addActions([self.export_png_action, self.export_csv_action])
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addActions([self.undo_action, self.redo_action])
        edit_menu.addSeparator()
        edit_menu.addActions([self.rotate_action, self.delete_action, self.deselect_action])

        view_menu = menu_bar.addMenu("&View")
        view_menu.addActions([self.zoom_in_action, self.zoom_out_action, self.fit_action])
        view_menu.addSeparator()
        view_menu.addAction(self.play_action)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addActions([self.quick_start_action, self.shortcuts_action])
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

    def _all_actions(self) -> list[QAction]:
        return [
            self.new_action,
            self.open_action,
            self.save_action,
            self.save_as_action,
            self.undo_action,
            self.redo_action,
            self.rotate_action,
            self.delete_action,
            self.deselect_action,
            self.play_action,
            self.zoom_in_action,
            self.zoom_out_action,
            self.fit_action,
            self.quick_start_action,
            self.quit_action,
        ]

    def _show_help(self, title: str, html: str) -> HelpDialog:
        if self._help_dialog is not None:
            self._help_dialog.close()
        self._help_dialog = HelpDialog(title, html, self)
        self._help_dialog.show()
        return self._help_dialog

    def show_quick_start(self) -> HelpDialog:
        return self._show_help("Quick Start Guide", QUICK_START_HTML)

    def show_shortcuts(self) -> HelpDialog:
        return self._show_help("Keyboard Shortcuts", shortcuts_html(self._all_actions()))

    def show_about(self) -> HelpDialog:
        return self._show_help("About CircuitCanvas", ABOUT_HTML)

    # ----- Layout -------------------------------------------------------------------------

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.component_palette)

        self.center_split = QSplitter(Qt.Orientation.Vertical)
        self.center_split.setHandleWidth(1)
        self.center_split.setChildrenCollapsible(False)
        self.center_split.addWidget(self.view)
        self.analysis.setMinimumHeight(230)
        self.center_split.addWidget(self.analysis)
        self.center_split.setStretchFactor(0, 3)
        self.center_split.setStretchFactor(1, 2)
        self.center_split.setSizes([500, 320])

        side = QWidget()
        side.setObjectName("sidePanel")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setMinimumWidth(300)
        side.setMaximumWidth(400)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.setDocumentMode(True)
        self.sidebar_tabs.addTab(self.details, "Details")
        self.sidebar_tabs.addTab(self.equations, "Kirchhoff's laws")
        self.sidebar_tabs.setTabToolTip(0, "The circuit, or the component you selected")
        self.sidebar_tabs.setTabToolTip(
            1, "Kirchhoff's laws for this circuit, with the solved numbers filled in"
        )
        side_layout.addWidget(self.sidebar_tabs)

        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.setHandleWidth(1)
        self.main_split.setChildrenCollapsible(False)
        self.main_split.addWidget(self.center_split)
        self.main_split.addWidget(side)
        self.main_split.setStretchFactor(0, 1)
        self.main_split.setSizes([1040, 320])
        root_layout.addWidget(self.main_split, 1)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.component_palette.component_clicked.connect(self.add_component)
        self.scene.circuit_changed.connect(self._circuit_changed)
        self.scene.selection_changed.connect(self._selection_changed)
        self.scene.component_activated.connect(self.edit_component)
        self.scene.source_activated.connect(self._edit_source_voltage)
        self.scene.hint_requested.connect(lambda text: self.statusBar().showMessage(text, 6000))
        self.view.edit_requested.connect(self.edit_component)
        self.view.parallel_requested.connect(self._duplicate_parallel)
        self.inspector.value_changed.connect(self._update_value)
        self.inspector.value_adjusted.connect(self._adjust_value)
        self.inspector.delete_requested.connect(self._delete_component)
        self.inspector.rotate_requested.connect(self.scene.rotate_component)
        self.inspector.parallel_requested.connect(self._duplicate_parallel)
        self.details.back_requested.connect(self.scene.clearSelection)
        self.source_voltage.valueChanged.connect(self._source_changed)
        self.source_voltage.editingFinished.connect(self._end_source_edit)
        self.controller.result_ready.connect(self._apply_result)
        self.controller.diagnostics_ready.connect(self._apply_diagnostics)
        self.equations.equation_selected.connect(self._equation_selected)
        self.sidebar_tabs.currentChanged.connect(self._sidebar_tab_changed)
        self.time_bar.play_toggled.connect(self.playback.set_playing)
        self.time_bar.speed_changed.connect(self.playback.set_speed)
        self.time_bar.time_index_changed.connect(self._scrubbed)
        self.analysis.cursor_index_changed.connect(self._scrubbed)
        self.analysis.auto_span_requested.connect(self._use_auto_span)
        self.analysis.manual_span_requested.connect(self._use_manual_span)
        self.playback.playing_changed.connect(self.time_bar.set_playing)
        self.playback.animation_tick.connect(self.scene.advance_arrows)
        self.playback.time_index_changed.connect(self._show_time_index)

    # ----- Editing ----------------------------------------------------------------------

    def add_component(self, kind: str) -> str:
        """Add a component with one click, somewhere it has room, and keep it in view."""
        if self.circuit.wires:
            component_id = self.scene.add_component_in_series(kind)
            self.view.show_all_if_hidden()
            return component_id
        return self.scene.insert_component_for_test(kind)

    def _circuit_changed(self, revision: int) -> None:
        self.circuit = self.scene.circuit
        self._update_title()
        self.controller.request(revision, self.circuit.snapshot())

    def _selection_changed(self, component_id: str) -> None:
        component = self.circuit.components.get(component_id)
        if component is None:
            self.inspector.clear_component()
            self.details.show_overview()
        else:
            self.inspector.set_component(component)
            self.details.show_component(component)
            self.equations.reveal_component(component_id)
        self._refresh_graph()
        self._update_readings()

    def edit_component(self, component_id: str) -> None:
        """Select a component and put the cursor in its value field."""
        if component_id not in self.scene.component_items:
            return
        self.scene.select_only(component_id)
        self.sidebar_tabs.setCurrentWidget(self.details)
        self.inspector.focus_value()

    def _escape(self) -> None:
        if self.scene.drawing_wire:
            self.scene.cancel_wire()
        else:
            self.scene.clearSelection()

    def _edit_source_voltage(self) -> None:
        self.scene.clearSelection()
        self.sidebar_tabs.setCurrentWidget(self.details)
        self.source_voltage.setFocus(Qt.FocusReason.OtherFocusReason)
        self.source_voltage.selectAll()

    def _equations_visible(self) -> bool:
        return self.sidebar_tabs.currentWidget() is self.equations

    def _equation_selected(self, line: EquationLine | None) -> None:
        # Outline an equation's elements only while the user is reading equations.
        self.scene.highlight_equation(line if self._equations_visible() else None)

    def _sidebar_tab_changed(self, _index: int) -> None:
        if self._equations_visible():
            self._refresh_equations()
        self._equation_selected(self.equations.current_line())

    def _update_value(self, component_id: str, value: float) -> None:
        self.scene.command_stack.update_value(component_id, value)
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _adjust_value(self, component_id: str, value: float, session: int) -> None:
        """Apply a slider move; one continuous drag becomes one undo step."""
        self.scene.command_stack.update_value(
            component_id, value, merge_key=("value", component_id, session)
        )
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _delete_component(self, component_id: str) -> None:
        self.scene.command_stack.delete(component_id)
        self.inspector.clear_component()
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _delete_selected(self) -> None:
        self.scene.delete_selected()

    def _duplicate_parallel(self, component_id: str) -> None:
        if self.circuit.wires:
            self.scene.duplicate_parallel(component_id)
            self.view.show_all_if_hidden()
            return
        component = self.circuit.components[component_id]
        self.scene.insert_component_for_test(component.kind, parallel_to=component_id)

    def _source_changed(self, voltage: float) -> None:
        # Typing "17" fires 1 then 17; arrow clicks fire repeatedly. Merge them
        # into one undo step until the field finishes editing.
        self.scene.command_stack.set_source_voltage(
            voltage, merge_key=("source", self._source_edit_session)
        )
        self.scene.rebuild()
        self._circuit_changed(self.circuit.revision)

    def _end_source_edit(self) -> None:
        self._source_edit_session += 1

    def _sync_source_control(self) -> None:
        """Show the circuit's battery voltage and time-span mode after undo, redo, or open."""
        self.source_voltage.blockSignals(True)
        self.source_voltage.setValue(self.circuit.source.voltage)
        self.source_voltage.blockSignals(False)
        settings = self.circuit.settings
        # In auto mode the real span arrives with the next result.
        span = self.analysis.time_span if settings.auto_duration else settings.duration
        self.analysis.show_time_span(span, auto=settings.auto_duration)

    def _use_auto_span(self) -> None:
        settings = self.circuit.settings
        if settings.auto_duration:
            return
        self.scene.command_stack.set_simulation_settings(replace(settings, auto_duration=True))
        self._circuit_changed(self.circuit.revision)

    def _use_manual_span(self, seconds: float) -> None:
        settings = self.circuit.settings
        if not settings.auto_duration and math.isclose(settings.duration, seconds):
            return
        self.scene.command_stack.set_simulation_settings(
            replace(settings, duration=seconds, auto_duration=False)
        )
        self._circuit_changed(self.circuit.revision)

    # ----- Results ----------------------------------------------------------------------

    def _apply_result(self, revision: int, result: SimulationResult) -> None:
        if revision != self.circuit.revision:
            return
        self.current_result = result
        index = len(result.time) - 1
        self.playback.set_timeline(samples=len(result.time), duration=float(result.time[-1]))
        self.time_bar.set_timeline(result.time)
        self.analysis.show_time_span(
            float(result.time[-1]), auto=self.circuit.settings.auto_duration
        )
        self.scene.set_problem_components(())
        solved = (
            "✓ Circuit solved. Press <b>Play</b>, or drag the time slider at the top, "
            "to watch it change after the battery is connected."
        )
        bypassed = tuple(
            component.id
            for component in self.circuit.snapshot().components
            if component.node_a == component.node_b
        )
        if bypassed:
            # Solved, but a zero reading with no explanation looks like a bug.
            note = describe_bypassed(bypassed)
            self.view.show_banner("info", note)
            self.details.set_status("info", f"{solved}<br><br>ℹ {note}")
        else:
            self.view.hide_banner()
            self.details.set_status("ok", solved)
        self._refresh_graph()
        self._show_time_index(index)
        self._refresh_equations()

    def _apply_diagnostics(self, revision: int, diagnostics: tuple[Diagnostic, ...]) -> None:
        if revision != self.circuit.revision:
            return
        problem = describe(diagnostics[0], has_components=bool(self.circuit.components))
        self.current_result = None
        self.playback.set_playing(False)
        self.time_bar.clear()
        self.equations.clear()
        self.scene.clear_results()
        self.scene.set_problem_components(problem.component_ids)
        if problem.show_on_canvas:
            self.view.show_banner(problem.kind, problem.text)
            self.view.reveal(problem.component_ids)
        else:
            self.view.hide_banner()
        mark = "⚠ " if problem.kind == "problem" else ""
        self.details.set_status(problem.kind, mark + problem.text)
        self.details.clear_readings(
            len(self.circuit.components), "No readings until the circuit is complete"
        )
        self.analysis.show_placeholder(
            "Graphs appear here once the circuit is complete."
            if self.circuit.components
            else "Add a component to see how it behaves over time."
        )

    def _scrubbed(self, index: int) -> None:
        """The user picked a moment on the time slider or a graph."""
        self.playback.seek(index)
        self._show_time_index(index)

    def _show_time_index(self, index: int) -> None:
        result = self.current_result
        if result is None:
            return
        index = max(0, min(index, len(result.time) - 1))
        self.current_time_index = index
        self.time_bar.set_index(index)
        self.analysis.set_cursor_index(index)
        self.scene.set_result(result, index)
        flows = reconstruct_wire_flows(self.circuit.snapshot(), result, index)
        self.scene.set_wire_currents(dict(flows.currents))
        if self._equations_visible():
            self._refresh_equations()
        self._update_readings()

    def _refresh_equations(self) -> None:
        if self.current_result is not None:
            self.equations.set_report(
                build_equation_report(
                    self.circuit.snapshot(), self.current_result, self.current_time_index
                )
            )

    def _battery_series(self, result: SimulationResult) -> BranchResult:
        """The battery as a branch: positive current and power while it delivers energy."""
        voltage = np.full_like(result.time, self.circuit.source.voltage)
        voltage[0] = 0.0
        current = -np.asarray(result.source_current)
        power = -np.asarray(result.source_power)
        return BranchResult(voltage, current, power, np.zeros_like(result.time))

    def _refresh_graph(self) -> None:
        result = self.current_result
        if result is None:
            return
        selected = self.scene.selected_component_id()
        if selected is not None and selected in result.branches:
            kind = KIND_NAMES[self.circuit.components[selected].kind.value].lower()
            self.analysis.set_branch(
                selected,
                result.time,
                result.branches[selected],
                title=f"{selected} ({kind}) over time",
            )
        else:
            self.analysis.set_branch(
                "Battery",
                result.time,
                self._battery_series(result),
                title="Battery over time · select a component to see its own graphs",
            )
        self.analysis.set_cursor_index(self.current_time_index)

    def _moment_text(self) -> str:
        result = self.current_result
        if result is None:
            return ""
        index = self.current_time_index
        moment = f"At t = {format_si(float(result.time[index]), 's', digits=3)}"
        return moment + (" (end of the time span)" if index == len(result.time) - 1 else "")

    def _update_readings(self) -> None:
        result = self.current_result
        if result is None:
            return
        index = max(0, min(self.current_time_index, len(result.time) - 1))
        when = self._moment_text()
        selected = self.scene.selected_component_id()
        if selected is not None and selected in result.branches:
            branch = result.branches[selected]
            self.details.set_component_readings(
                when,
                format_si(float(branch.voltage[index]), "V"),
                format_si(float(branch.current[index]), "A"),
                format_si(float(branch.power[index]), "W"),
                format_si(float(branch.energy[index]), "J"),
            )
        energy = sum(float(branch.energy[index]) for branch in result.branches.values())
        self.details.set_circuit_readings(
            when,
            format_si(-float(result.source_current[index]), "A"),
            format_si(-float(result.source_power[index]), "W"),
            format_si(energy, "J"),
            len(self.circuit.components),
        )

    def undo(self) -> None:
        if self.scene.command_stack.undo():
            self._end_source_edit()
            self._sync_source_control()
            self.scene.rebuild()
            self._circuit_changed(self.circuit.revision)

    def redo(self) -> None:
        if self.scene.command_stack.redo():
            self._end_source_edit()
            self._sync_source_control()
            self.scene.rebuild()
            self._circuit_changed(self.circuit.revision)

    # ----- Documents: new, open, save, close -------------------------------------

    @property
    def has_unsaved_changes(self) -> bool:
        return not self.scene.command_stack.is_clean

    def _update_title(self) -> None:
        name = self._current_path.name if self._current_path is not None else self._untitled_name
        self.setWindowTitle(f"{name}[*] — CircuitCanvas")
        self.setWindowModified(self.has_unsaved_changes)

    def _ask_save_changes(self) -> QMessageBox.StandardButton:
        """Ask whether to keep unsaved edits. Tests replace this to avoid a modal dialog."""
        name = self._current_path.name if self._current_path is not None else "this circuit"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Do you want to save the changes to {name}?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def _confirm_discard_changes(self) -> bool:
        """Return True when it is safe to replace or close the current circuit."""
        if not self.has_unsaved_changes:
            return True
        answer = self._ask_save_changes()
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file()
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard_changes():
            self.playback.set_playing(False)
            event.accept()
        else:
            event.ignore()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._initial_fit_done:
            self._initial_fit_done = True
            # Wait for the splitters to settle so the fit uses the final canvas size.
            QTimer.singleShot(0, self.view, self.view.fit_circuit)

    def reset_circuit(self) -> None:
        if not self._confirm_discard_changes():
            return
        self._current_path = None
        self._untitled_name = "Untitled"
        self._replace_circuit(Circuit.starter_loop(self.source_voltage.value()))

    def _replace_circuit(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self.current_result = None
        self.scene.replace_circuit(circuit)
        self.inspector.clear_component()
        self.details.show_overview()
        self.analysis.clear()
        self.time_bar.clear()
        self.view.hide_banner()
        self.equations.clear()
        self._end_source_edit()
        self._sync_source_control()
        self.view.fit_circuit()
        self._update_title()
        self.controller.request(circuit.revision, circuit.snapshot())

    def save_file(self) -> bool:
        """Save to the current file, asking for a name the first time. Returns success."""
        if self._current_path is None:
            return self.save_file_as()
        return self._write_circuit(self._current_path)

    def save_file_as(self) -> bool:
        suggested = (
            str(self._current_path.with_suffix(".circuitcanvas"))
            if self._current_path is not None
            else "circuit.circuitcanvas"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save circuit", suggested, "CircuitCanvas (*.circuitcanvas)"
        )
        if not filename:
            return False
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".circuitcanvas")
        return self._write_circuit(path)

    def _write_circuit(self, path: Path) -> bool:
        try:
            save_circuit(path, self.circuit)
        except OSError as exc:
            QMessageBox.warning(
                self, "Could not save circuit", f"CircuitCanvas could not write {path}:\n{exc}"
            )
            return False
        self._current_path = path
        self.scene.command_stack.mark_clean()
        self._update_title()
        self.statusBar().showMessage(f"Saved {path.name}", 4000)
        return True

    def open_file(self) -> None:
        if not self._confirm_discard_changes():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open circuit", "", "CircuitCanvas (*.circuitcanvas *.json)"
        )
        if filename:
            self.open_path(Path(filename))

    def open_example(self, example: Example) -> bool:
        """Open a bundled example as an untitled copy, so Save never overwrites it."""
        if not self._confirm_discard_changes():
            return False
        try:
            circuit = load_example(example)
        except CircuitFileError as exc:
            QMessageBox.warning(self, "Could not open example", str(exc))
            return False
        self._current_path = None
        self._untitled_name = f"{example.title} (example)"
        self._replace_circuit(circuit)
        self.statusBar().showMessage(example.description, 8000)
        return True

    def open_document(self, path: Path) -> bool:
        """Open a file chosen outside the app (Finder, command line), asking to save first."""
        if not self._confirm_discard_changes():
            return False
        return self.open_path(path)

    def open_path(self, path: Path) -> bool:
        try:
            circuit = load_circuit(path)
        except CircuitFileError as exc:
            QMessageBox.warning(self, "Could not open circuit", str(exc))
            return False
        self._current_path = path
        self._replace_circuit(circuit)
        return True

    # ----- Exports ----------------------------------------------------------------

    def export_png(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export circuit image", "circuit.png", "PNG image (*.png)"
        )
        if not filename:
            return
        try:
            export_scene_png(filename, self.scene)
        except OSError as exc:
            QMessageBox.warning(self, "Could not export image", str(exc))
            return
        self.statusBar().showMessage(f"Exported {Path(filename).name}", 4000)

    def export_csv(self) -> None:
        """Export the selected component's data, or every component when none is selected."""
        result = self.current_result
        if result is None:
            QMessageBox.information(
                self,
                "Nothing to export yet",
                "The circuit has no result yet. Follow the message above the circuit "
                "to complete it, then export again.",
            )
            return
        selected = self.scene.selected_component_id()
        default_name = f"{selected}.csv" if selected is not None else "circuit-data.csv"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export transient data", default_name, "CSV data (*.csv)"
        )
        if not filename:
            return
        try:
            if selected is not None:
                export_branch_csv(filename, result, selected)
            else:
                export_all_branches_csv(filename, result)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not export data", str(exc))
            return
        self.statusBar().showMessage(f"Exported {Path(filename).name}", 4000)
