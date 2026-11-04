"""Interactive smart-snap circuit canvas."""

from __future__ import annotations

import math
from collections import defaultdict

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QNativeGestureEvent,
    QPainter,
    QPen,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QToolButton,
    QWidget,
)

from circuitcanvas.commands.circuit_commands import CircuitCommandStack
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.wiring import EndpointRef, JunctionRef, TerminalRef
from circuitcanvas.solver.equations import EquationLine
from circuitcanvas.solver.results import SimulationResult

from .component_items import BatteryItem, ComponentItem, DropTargetItem, GuideItem
from .icons import icon
from .routing import (
    normalized_octilinear_polyline,
    octilinear_route,
    project_to_octilinear,
    project_to_polyline,
    split_polyline,
)
from .theme import DANGER, INFO_TEXT, KIND_NAMES, WARNING_TEXT
from .wire_items import JunctionItem, RouteHandleItem, TerminalItem, WireItem

DEFAULT_VALUES = {
    ComponentKind.RESISTOR: 100.0,
    ComponentKind.CAPACITOR: 47e-6,
    ComponentKind.INDUCTOR: 22e-3,
}


class CircuitScene(QGraphicsScene):
    circuit_changed = Signal(int)
    selection_changed = Signal(str)
    #: Double-click on a component or the battery: "I want to edit this".
    component_activated = Signal(str)
    source_activated = Signal()

    def __init__(self, circuit: Circuit, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.circuit = circuit
        self.command_stack = CircuitCommandStack(circuit)
        self.component_items: dict[str, ComponentItem] = {}
        self.wire_items: dict[str, WireItem] = {}
        self.junction_items: dict[str, JunctionItem] = {}
        self.route_handle_items: list[RouteHandleItem] = []
        self.battery_item: BatteryItem | None = None
        self.open_target: DropTargetItem | None = None
        self.guide_item: GuideItem | None = None
        self._wire_start: EndpointRef | None = None
        self._wire_preview: QGraphicsLineItem | None = None
        self._suppress_selection_signal = False
        self.highlighted_components: set[str] = set()
        self.problem_components: set[str] = set()
        self.setSceneRect(QRectF(0, 0, 1200, 620))
        self.selectionChanged.connect(self._selection_updated)
        self.rebuild()

    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        rect_f = QRectF(rect)
        painter.fillRect(rect_f, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#e5eaf1"), 1))
        spacing = 24
        left = int(rect_f.left()) - int(rect_f.left()) % spacing
        top = int(rect_f.top()) - int(rect_f.top()) % spacing
        for x in range(left, int(rect_f.right()) + spacing, spacing):
            painter.drawLine(x, int(rect_f.top()), x, int(rect_f.bottom()))
        for y in range(top, int(rect_f.bottom()) + spacing, spacing):
            painter.drawLine(int(rect_f.left()), y, int(rect_f.right()), y)

    def rebuild(self) -> None:
        # Clearing and recreating items fires several transient selection changes;
        # report only the selection that survives the rebuild.
        self._suppress_selection_signal = True
        try:
            if self._uses_free_wiring():
                self._rebuild_free()
            else:
                self._rebuild_legacy()
            self._apply_highlight()
            self._apply_problems()
        finally:
            self._suppress_selection_signal = False
        self._selection_updated()

    def _uses_free_wiring(self) -> bool:
        return bool(
            self.circuit.wires
            or self.circuit.junctions
            or self.circuit.rotations
            or any(
                component.node_a.startswith("loose_")
                for component in self.circuit.components.values()
            )
        )

    def _rebuild_legacy(self) -> None:
        selected = self.selected_component_id()
        self.clear()
        self.component_items = {}
        self.wire_items = {}
        self.junction_items = {}
        self.route_handle_items = []
        top_rail = 200.0
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for component in self.circuit.components.values():
            groups[component.endpoints].append(component.id)
        max_parallel = max((len(ids) for ids in groups.values()), default=1)
        bottom_rail = max(340.0, top_rail + (max_parallel - 1) * 112.0 + 120.0)
        last_group_x = 260.0 + max(0, len(groups) - 1) * 210.0
        right_rail = max(980.0, last_group_x + 150.0)
        self.setSceneRect(QRectF(0, 0, right_rail + 180.0, bottom_rail + 140.0))

        self.battery_item = BatteryItem(self.circuit.source.voltage)
        battery_center = (top_rail + bottom_rail) / 2.0
        self.battery_item.setPos(90, battery_center)
        self.addItem(self.battery_item)

        wire_pen = QPen(QColor("#334155"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self.addLine(90, top_rail, 170, top_rail, wire_pen)
        self.addLine(90, bottom_rail, right_rail, bottom_rail, wire_pen)
        self.addLine(right_rail, top_rail, right_rail, bottom_rail, wire_pen)
        self.addLine(90, top_rail, 90, battery_center - 70, wire_pen)
        self.addLine(90, battery_center + 70, 90, bottom_rail, wire_pen)

        if not self.circuit.components:
            self.open_target = DropTargetItem()
            self.open_target.setPos(400, top_rail)
            self.addItem(self.open_target)
            self.addLine(170, top_rail, 306, top_rail, wire_pen)
            self.addLine(494, top_rail, right_rail, top_rail, wire_pen)
            return

        self.open_target = None
        x_positions: list[float] = []
        for group_index, siblings in enumerate(groups.values()):
            x = 260.0 + group_index * 210.0
            x_positions.append(x)
            last_y = top_rail + (len(siblings) - 1) * 112.0
            if len(siblings) > 1:
                self.addLine(x - 105, top_rail, x - 105, last_y, wire_pen)
                self.addLine(x + 105, top_rail, x + 105, last_y, wire_pen)
            for sibling_index, component_id in enumerate(siblings):
                component = self.circuit.components[component_id]
                y = top_rail + sibling_index * 112.0
                item = ComponentItem(component)
                item.setPos(x, y)
                self.addItem(item)
                self.component_items[component_id] = item
                self.circuit.positions[component_id] = (x, y)
                self.addLine(x - 84, y, x - 105, y, wire_pen)
                self.addLine(x + 84, y, x + 105, y, wire_pen)

        first_x = min(x_positions)
        last_x = max(x_positions)
        self.addLine(170, top_rail, first_x - 105, top_rail, wire_pen)
        for left_x, right_x in zip(x_positions, x_positions[1:], strict=False):
            self.addLine(left_x + 105, top_rail, right_x - 105, top_rail, wire_pen)
        self.addLine(last_x + 105, top_rail, right_rail, top_rail, wire_pen)
        if selected in self.component_items:
            self.component_items[selected].setSelected(True)

    def _rebuild_free(self) -> None:
        selected = self.selected_component_id()
        self.clear()
        self.component_items = {}
        self.wire_items = {}
        self.junction_items = {}
        self.route_handle_items = []
        self.open_target = None
        self.setSceneRect(QRectF(0, 0, 1400, 820))

        self.battery_item = BatteryItem(self.circuit.source.voltage, self.circuit.source.id)
        self.battery_item.setPos(110, 360)
        self.addItem(self.battery_item)

        for index, component in enumerate(self.circuit.components.values()):
            component_item = ComponentItem(component)
            position = self.circuit.positions.get(component.id, (360.0 + index * 210.0, 220.0))
            component_item.setPos(*position)
            component_item.setRotation(self.circuit.rotations.get(component.id, component.rotation))
            component_item.moved.connect(self._component_moved)
            self.addItem(component_item)
            self.component_items[component.id] = component_item

        for junction in self.circuit.junctions.values():
            junction_item = JunctionItem(junction.id)
            junction_item.setPos(*junction.position)
            junction_item.moved.connect(self._junction_moved)
            self.addItem(junction_item)
            self.junction_items[junction.id] = junction_item

        connected = {
            endpoint for wire in self.circuit.wires.values() for endpoint in (wire.start, wire.end)
        }
        for terminal in self._terminal_items():
            terminal.connected = terminal.ref in connected

        for wire in self.circuit.wires.values():
            wire_item = WireItem(
                wire, self._endpoint_position(wire.start), self._endpoint_position(wire.end)
            )
            self.addItem(wire_item)
            self.wire_items[wire.id] = wire_item
            for route_index, (x, y) in enumerate(wire.route):
                handle = RouteHandleItem(wire.id, route_index)
                handle.setPos(x, y)
                handle.moved.connect(self._route_moved)
                self.addItem(handle)
                self.route_handle_items.append(handle)

        self.guide_item = None
        if not self.circuit.components:
            circuit_bounds = self.itemsBoundingRect()
            self.guide_item = GuideItem()
            self.guide_item.setPos(
                circuit_bounds.center().x(),
                circuit_bounds.top() - GuideItem.HEIGHT / 2 - 36,
            )
            self.addItem(self.guide_item)

        bounds = self.itemsBoundingRect().adjusted(-120, -120, 220, 180)
        self.setSceneRect(self.sceneRect().united(bounds))
        if selected in self.component_items:
            self.component_items[selected].setSelected(True)

    def _terminal_items(self) -> list[TerminalItem]:
        items: list[TerminalItem] = []
        if self.battery_item is not None:
            items.extend(self.battery_item.terminals.values())
        for component in self.component_items.values():
            items.extend(component.terminals.values())
        return items

    def _endpoint_position(self, endpoint: EndpointRef) -> QPointF:
        if isinstance(endpoint, JunctionRef):
            return self.junction_items[endpoint.junction_id].scenePos()
        if endpoint.owner_id == self.circuit.source.id:
            assert self.battery_item is not None
            return self.battery_item.terminals[endpoint.terminal].scenePos()
        return self.component_items[endpoint.owner_id].terminals[endpoint.terminal].scenePos()

    def _stored_endpoint_position(self, endpoint: EndpointRef) -> tuple[float, float]:
        if isinstance(endpoint, JunctionRef):
            return self.circuit.junctions[endpoint.junction_id].position
        position = self._endpoint_position(endpoint)
        return (position.x(), position.y())

    def _stored_wire_polyline(self, wire_id: str) -> tuple[tuple[float, float], ...]:
        wire = self.circuit.wires[wire_id]
        return normalized_octilinear_polyline(
            (
                self._stored_endpoint_position(wire.start),
                *wire.route,
                self._stored_endpoint_position(wire.end),
            )
        )

    @staticmethod
    def _endpoint_for_item(item: object) -> EndpointRef | None:
        if isinstance(item, TerminalItem):
            return item.ref
        if isinstance(item, JunctionItem):
            return JunctionRef(item.junction_id)
        return None

    def _component_moved(self, component_id: str, x: float, y: float) -> None:
        self.set_drop_highlight(None)
        if self.circuit.positions.get(component_id) == (x, y):
            return  # A click, not a move: nothing changed.
        if self.is_unwired(component_id):
            target = self.nearest_wire(QPointF(x, y), self.SNAP_DISTANCE)
            if target is not None:
                self.splice_into_wire(component_id, target[0], target[1])
                return
        self.command_stack.move_component(component_id, (x, y))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def component_dragging(self, item: ComponentItem) -> None:
        """While a loose component is dragged, light up the wire it would join."""
        if not self.is_unwired(item.component.id):
            return
        target = self.nearest_wire(item.scenePos(), self.SNAP_DISTANCE)
        self.set_drop_highlight(target[0] if target is not None else None)

    def _junction_moved(self, junction_id: str, x: float, y: float) -> None:
        candidates = []
        junction_ref = JunctionRef(junction_id)
        for wire_id, wire in self.circuit.wires.items():
            if junction_ref in (wire.start, wire.end):
                candidates.append(project_to_polyline((x, y), self._stored_wire_polyline(wire_id)))
        previous = self.circuit.junctions[junction_id].position
        constrained = min(candidates, key=lambda point: math.dist(point, (x, y)), default=previous)
        if constrained == previous:
            self.rebuild()  # Snap the dot back onto its wire without an undo step.
            return
        self.command_stack.move_junction(junction_id, constrained)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def _route_moved(self, wire_id: str, route_index: int, x: float, y: float) -> None:
        route = list(self.circuit.wires[wire_id].route)
        moved = project_to_polyline((x, y), self._stored_wire_polyline(wire_id))
        if moved == route[route_index]:
            self.rebuild()
            return
        route[route_index] = moved
        self.command_stack.set_wire_route(wire_id, tuple(route))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def select_only(self, component_id: str) -> None:
        """Make one component the whole selection, so Delete and the Inspector agree."""
        self._suppress_selection_signal = True
        try:
            self.clearSelection()
            item = self.component_items.get(component_id)
            if item is not None:
                item.setSelected(True)
        finally:
            self._suppress_selection_signal = False
        self._selection_updated()

    def selected_component_id(self) -> str | None:
        for item in self.selectedItems():
            if isinstance(item, ComponentItem):
                return item.component.id
        return None

    def _selection_updated(self) -> None:
        """Emit the selected component ID, or an empty string when none is selected."""
        if self._suppress_selection_signal:
            return
        self.selection_changed.emit(self.selected_component_id() or "")

    def insert_component_for_test(
        self, kind: ComponentKind | str, *, parallel_to: str | None = None
    ) -> str:
        component_kind = kind if isinstance(kind, ComponentKind) else ComponentKind(kind)
        if parallel_to is not None:
            component_id = self.command_stack.add_parallel(
                parallel_to, component_kind, DEFAULT_VALUES[component_kind]
            )
        else:
            target = self.circuit.open_edge
            if target is None:
                target = next(reversed(self.circuit.components))
            component_id = self.command_stack.insert_series(
                target, component_kind, DEFAULT_VALUES[component_kind]
            )
        self.rebuild()
        self.select_only(component_id)
        self.circuit_changed.emit(self.circuit.revision)
        return component_id

    def insert_component_at(self, kind: ComponentKind | str, position: QPointF) -> str:
        component_kind = kind if isinstance(kind, ComponentKind) else ComponentKind(kind)
        component_id = self.command_stack.add_loose_component(
            component_kind, DEFAULT_VALUES[component_kind], (position.x(), position.y())
        )
        self.rebuild()
        self.select_only(component_id)
        self.circuit_changed.emit(self.circuit.revision)
        return component_id

    #: A component dropped this close to a wire (in scene units at 100 % zoom) joins it.
    SNAP_DISTANCE = 28.0

    def place_component(
        self, kind: ComponentKind | str, position: QPointF, tolerance: float | None = None
    ) -> str:
        """Drop a new component: into the nearest wire if close enough, else loose."""
        target = self.nearest_wire(position, self.SNAP_DISTANCE if tolerance is None else tolerance)
        if target is not None:
            return self.insert_component_on_wire(kind, target[0], target[1])
        return self.insert_component_at(kind, position)

    def nearest_wire(self, position: QPointF, tolerance: float) -> tuple[str, QPointF] | None:
        """The closest wire within ``tolerance`` and the closest point on it."""
        point = (position.x(), position.y())
        best: tuple[float, str, tuple[float, float]] | None = None
        for wire_id, item in self.wire_items.items():
            polyline = tuple((p.x(), p.y()) for p in item.polyline_points())
            if len(polyline) < 2:
                continue
            projected = project_to_polyline(point, polyline)
            distance = math.dist(point, projected)
            if distance <= tolerance and (best is None or distance < best[0]):
                best = (distance, wire_id, projected)
        if best is None:
            return None
        return best[1], QPointF(*best[2])

    def is_unwired(self, component_id: str) -> bool:
        terminals = {TerminalRef(component_id, "a"), TerminalRef(component_id, "b")}
        return not any(
            endpoint in terminals
            for wire in self.circuit.wires.values()
            for endpoint in (wire.start, wire.end)
        )

    def set_drop_highlight(self, wire_id: str | None) -> None:
        for candidate, item in self.wire_items.items():
            item.set_drop_target(candidate == wire_id)

    def splice_into_wire(self, component_id: str, wire_id: str, position: QPointF) -> None:
        center, rotation, before, after = self._wire_split(wire_id, position)
        self.command_stack.splice_component_into_wire(
            component_id, wire_id, center, rotation, before, after
        )
        self.rebuild()
        self.select_only(component_id)
        self.circuit_changed.emit(self.circuit.revision)

    def _wire_split(
        self, wire_id: str, position: QPointF
    ) -> tuple[
        tuple[float, float], int, tuple[tuple[float, float], ...], tuple[tuple[float, float], ...]
    ]:
        """Where a component inserted at ``position`` sits, its rotation, and both new routes."""
        polyline = self._stored_wire_polyline(wire_id)
        if len(polyline) < 2:
            raise ValueError("Cannot insert a component on a zero-length wire")
        before, after = split_polyline(polyline, (position.x(), position.y()))
        start = before[-2]
        end = after[1]
        vertical = abs(end[0] - start[0]) < 1.0 and abs(end[1] - start[1]) >= 1.0
        return before[-1], 90 if vertical else 0, before[1:-1], after[1:-1]

    def best_wire_insertion(self) -> tuple[str, QPointF]:
        candidates: list[tuple[float, str, QPointF]] = []
        for wire_id, item in self.wire_items.items():
            for start, end in zip(item.polyline_points(), item.polyline_points()[1:], strict=False):
                length = math.dist((start.x(), start.y()), (end.x(), end.y()))
                midpoint = QPointF((start.x() + end.x()) / 2.0, (start.y() + end.y()) / 2.0)
                candidates.append((length, wire_id, midpoint))
        if not candidates:
            raise ValueError("No wire is available for component insertion")
        _, wire_id, midpoint = max(candidates, key=lambda candidate: candidate[0])
        return wire_id, midpoint

    def insert_component_on_wire(
        self, kind: ComponentKind | str, wire_id: str, position: QPointF
    ) -> str:
        component_kind = kind if isinstance(kind, ComponentKind) else ComponentKind(kind)
        center, rotation, before, after = self._wire_split(wire_id, position)
        component_id = self.command_stack.insert_component_on_wire(
            wire_id,
            component_kind,
            DEFAULT_VALUES[component_kind],
            center,
            rotation,
            before,
            after,
        )
        self.rebuild()
        self.select_only(component_id)
        self.circuit_changed.emit(self.circuit.revision)
        return component_id

    @staticmethod
    def _component_terminal_positions(
        position: tuple[float, float], rotation: int
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if rotation % 180 == 90:
            return (
                (position[0], position[1] - 84.0),
                (position[0], position[1] + 84.0),
            )
        return (
            (position[0] - 84.0, position[1]),
            (position[0] + 84.0, position[1]),
        )

    def duplicate_parallel(self, component_id: str) -> str:
        component = self.circuit.components[component_id]
        position = self.circuit.positions[component_id]
        rotation = self.circuit.rotations.get(component_id, component.rotation)
        if rotation % 180 == 90:
            new_position = (position[0] + 220.0, position[1])
        else:
            new_position = (position[0], position[1] + 140.0)
        new_a, new_b = self._component_terminal_positions(new_position, rotation)
        target_a = self._stored_endpoint_position(TerminalRef(component_id, "a"))
        target_b = self._stored_endpoint_position(TerminalRef(component_id, "b"))
        new_id = self.command_stack.add_parallel_wired(
            component_id,
            component.kind,
            component.value,
            new_position,
            rotation,
            octilinear_route(target_a, new_a),
            octilinear_route(target_b, new_b),
        )
        self.rebuild()
        self.select_only(new_id)
        self.circuit_changed.emit(self.circuit.revision)
        return new_id

    def connect_for_test(self, start: EndpointRef, end: EndpointRef) -> str:
        route = self._orthogonal_route(self._endpoint_position(start), self._endpoint_position(end))
        wire_id = self.command_stack.connect(start, end, route)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        return wire_id

    @staticmethod
    def _orthogonal_route(start: QPointF, end: QPointF) -> tuple[tuple[float, float], ...]:
        return octilinear_route((start.x(), start.y()), (end.x(), end.y()))

    @staticmethod
    def _snapped_endpoint(start: QPointF, pointer: QPointF) -> QPointF:
        x, y = project_to_octilinear(
            (start.x(), start.y()),
            (pointer.x(), pointer.y()),
        )
        return QPointF(x, y)

    def add_route_handle_at(self, wire_id: str, position: QPointF) -> None:
        before, after = split_polyline(
            self._stored_wire_polyline(wire_id), (position.x(), position.y())
        )
        route = (*before[1:], *after[1:-1])
        self.command_stack.set_wire_route(wire_id, route)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def split_wire_at(self, wire_id: str, position: QPointF) -> str:
        before, after = split_polyline(
            self._stored_wire_polyline(wire_id), (position.x(), position.y())
        )
        junction_id = self.command_stack.split_wire(
            wire_id,
            before[-1],
            before[1:-1],
            after[1:-1],
        )
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        return junction_id

    def delete_selected(self) -> bool:
        """Delete every selected component, wire, junction, and bend as one undo step."""
        components: list[str] = []
        wires: list[str] = []
        junctions: list[str] = []
        bends: list[tuple[str, int]] = []
        for item in self.selectedItems():
            if isinstance(item, ComponentItem):
                components.append(item.component.id)
            elif isinstance(item, WireItem):
                wires.append(item.wire.id)
            elif isinstance(item, JunctionItem):
                junctions.append(item.junction_id)
            elif isinstance(item, RouteHandleItem):
                bends.append((item.wire_id, item.route_index))
        if not (components or wires or junctions or bends):
            return False
        self.command_stack.delete_elements(components, wires, junctions, bends)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        return True

    def rotate_selected(self) -> None:
        component_id = self.selected_component_id()
        if component_id is not None:
            self.rotate_component(component_id)

    def rotate_component(self, component_id: str) -> None:
        if component_id not in self.circuit.components:
            return
        self.command_stack.rotate_component(component_id)
        self.rebuild()
        self.select_only(component_id)
        self.circuit_changed.emit(self.circuit.revision)

    def set_wire_currents(self, currents: dict[str, float]) -> None:
        for wire_id, item in self.wire_items.items():
            if wire_id in currents:
                item.set_current(currents[wire_id])
            else:
                item.set_stale(True)

    def advance_arrows(self, seconds: float) -> None:
        for item in self.wire_items.values():
            item.advance_phase(seconds)

    def highlight_equation(self, line: EquationLine | None) -> None:
        """Outline the elements of an equation without touching the selection."""
        self.highlighted_components = set(line.component_ids) if line is not None else set()
        self._apply_highlight()

    def _apply_highlight(self) -> None:
        for component_id, item in self.component_items.items():
            item.set_highlighted(component_id in self.highlighted_components)
        if self.battery_item is not None:
            self.battery_item.set_highlighted(self.circuit.source.id in self.highlighted_components)

    def set_problem_components(self, component_ids: tuple[str, ...] | set[str]) -> None:
        """Outline the components that stop the circuit from being solved."""
        self.problem_components = set(component_ids)
        self._apply_problems()

    def _apply_problems(self) -> None:
        for component_id, item in self.component_items.items():
            item.set_problem(component_id in self.problem_components)

    def clear_results(self) -> None:
        """Forget readings from an older circuit so nothing stale is shown."""
        for item in self.component_items.values():
            item.clear_measurement()
        for wire in self.wire_items.values():
            wire.set_stale(True)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        item = self.itemAt(event.scenePos(), QTransform())
        endpoint = self._endpoint_for_item(item)
        junction_wire_drag = isinstance(item, JunctionItem) and bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        if isinstance(item, TerminalItem) or junction_wire_drag:
            assert endpoint is not None
            self._wire_start = endpoint
            start_position = self._endpoint_position(endpoint)
            self._wire_preview = self.addLine(
                start_position.x(),
                start_position.y(),
                event.scenePos().x(),
                event.scenePos().y(),
                QPen(QColor("#0ea5e9"), 3, Qt.PenStyle.DashLine),
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._wire_start is not None and self._wire_preview is not None:
            start = self._endpoint_position(self._wire_start)
            end = self._snapped_endpoint(start, event.scenePos())
            self._wire_preview.setLine(start.x(), start.y(), end.x(), end.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._wire_start is None:
            super().mouseReleaseEvent(event)
            return
        start = self._wire_start
        if self._wire_preview is not None:
            self.removeItem(self._wire_preview)
        target = self.itemAt(event.scenePos(), QTransform())
        self._wire_start = None
        self._wire_preview = None
        start_position = self._endpoint_position(start)
        target_endpoint = self._endpoint_for_item(target)
        if target_endpoint == start:
            self.rebuild()
            event.accept()
            return
        if target_endpoint is not None:
            end_position = self._endpoint_position(target_endpoint)
            route = self._orthogonal_route(start_position, end_position)
            self.command_stack.connect(start, target_endpoint, route)
        elif isinstance(target, WireItem):
            wire_points = tuple((point.x(), point.y()) for point in target.polyline_points())
            before, after = split_polyline(
                wire_points, (event.scenePos().x(), event.scenePos().y())
            )
            split_position = before[-1]
            end_position = QPointF(*split_position)
            route = self._orthogonal_route(start_position, end_position)
            junction_id = self.command_stack.split_wire(
                target.wire.id,
                split_position,
                before[1:-1],
                after[1:-1],
            )
            self.command_stack.connect(start, JunctionRef(junction_id), route)
        else:
            end_position = self._snapped_endpoint(start_position, event.scenePos())
            route = self._orthogonal_route(start_position, end_position)
            self.command_stack.connect_to_new_junction(
                start, (end_position.x(), end_position.y()), route
            )
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, WireItem):
            self.add_route_handle_at(item.wire.id, event.scenePos())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
        if isinstance(item, ComponentItem):
            self.component_activated.emit(item.component.id)
        elif isinstance(item, BatteryItem):
            self.source_activated.emit()

    def set_result(self, result: SimulationResult, time_index: int) -> None:
        index = max(0, min(time_index, len(result.time) - 1))
        for component_id, item in self.component_items.items():
            branch = result.branches.get(component_id)
            if branch is not None:
                item.set_measurement(float(branch.voltage[index]), float(branch.current[index]))

    def replace_circuit(self, circuit: Circuit) -> None:
        # IDs such as "R1" repeat across circuits; never carry a selection over.
        self._suppress_selection_signal = True
        try:
            self.clearSelection()
        finally:
            self._suppress_selection_signal = False
        self.highlighted_components = set()
        self.problem_components = set()
        self.circuit = circuit
        self.command_stack = CircuitCommandStack(circuit)
        self.rebuild()


class CircuitView(QGraphicsView):
    """Pannable, zoomable view that accepts component MIME drops.

    Plain wheel and two-finger trackpad scrolling pan the canvas. Zooming uses
    Ctrl/Cmd + wheel, a trackpad pinch, or the zoom actions, and stays between
    ``MIN_ZOOM`` and ``MAX_ZOOM`` so the circuit can never vanish.
    """

    MIN_ZOOM = 0.2
    MAX_ZOOM = 4.0
    FIT_MARGIN = 48.0

    #: Right-click "Edit value" and "Add parallel copy" on a component.
    edit_requested = Signal(str)
    parallel_requested = Signal(str)

    def __init__(self, scene: CircuitScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Scrolling and dragging still pan; the bars themselves are only clutter here.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._build_overlays()

    # ----- Overlays: problem banner and zoom buttons ---------------------------------

    def _build_overlays(self) -> None:
        self.banner = QFrame(self)
        self.banner.setObjectName("banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self.banner_label = QLabel()
        self.banner_label.setWordWrap(True)
        banner_layout.addWidget(self.banner_label)
        self.banner.hide()

        self.controls = QFrame(self)
        self.controls.setObjectName("canvasControls")
        controls_layout = QHBoxLayout(self.controls)
        controls_layout.setContentsMargins(3, 3, 3, 3)
        controls_layout.setSpacing(2)
        self.zoom_buttons: dict[str, QToolButton] = {}
        for name, tip, slot in (
            ("zoom-out", "Zoom out (⌘/Ctrl −)", self.zoom_out),
            ("zoom-in", "Zoom in (⌘/Ctrl +)", self.zoom_in),
            ("fit", "Show the whole circuit (⌘/Ctrl 0)", self.fit_circuit),
        ):
            button = QToolButton()
            button.setIcon(icon(name))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(tip)
            button.clicked.connect(slot)
            controls_layout.addWidget(button)
            self.zoom_buttons[name] = button
        self._place_overlays()

    def show_banner(self, kind: str, text: str) -> None:
        """Show a message above the circuit; ``kind`` is "problem" or "info"."""
        color = WARNING_TEXT if kind == "problem" else INFO_TEXT
        mark = "⚠" if kind == "problem" else "ℹ"
        self.banner.setProperty("kind", kind)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        self.banner_label.setText(f"<span style='color:{color}'><b>{mark}</b>&nbsp; {text}</span>")
        self.banner.show()
        self._place_overlays()

    def hide_banner(self) -> None:
        self.banner.hide()

    def _place_overlays(self) -> None:
        width = min(620, max(200, self.width() - 40))
        layout = self.banner.layout()
        height = (
            layout.heightForWidth(width)
            if layout is not None and layout.hasHeightForWidth()
            else self.banner.sizeHint().height()
        )
        self.banner.setFixedSize(width, height)
        self.banner.move((self.width() - width) // 2, 12)
        self.controls.adjustSize()
        self.controls.move(
            self.width() - self.controls.width() - 12,
            self.height() - self.controls.height() - 12,
        )
        self.banner.raise_()
        self.controls.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._place_overlays()

    def reveal(self, component_ids: set[str] | tuple[str, ...]) -> None:
        """Scroll so the given components are on screen."""
        scene = self.scene()
        if not isinstance(scene, CircuitScene):
            return
        items = [scene.component_items[i] for i in component_ids if i in scene.component_items]
        if not items:
            return
        bounds = items[0].sceneBoundingRect()
        for item in items[1:]:
            bounds = bounds.united(item.sceneBoundingRect())
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        if not visible.contains(bounds):
            # Show the whole circuit so the problem is seen in context.
            self.fit_circuit()

    # ----- Right-click menus ----------------------------------------------------------

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.build_context_menu(event.pos())
        if menu is not None:
            menu.exec(event.globalPos())
            event.accept()

    def build_context_menu(self, view_pos: QPoint) -> QMenu | None:
        """The menu for whatever is under ``view_pos`` (kept separate so tests can inspect it)."""
        scene = self.scene()
        if not isinstance(scene, CircuitScene):
            return None
        scene_pos = self.mapToScene(view_pos)
        item: QGraphicsItem | None = scene.itemAt(scene_pos, self.transform())
        while item is not None and not isinstance(
            item, (ComponentItem, BatteryItem, WireItem, JunctionItem, RouteHandleItem)
        ):
            item = item.parentItem()
        menu = QMenu(self)
        if isinstance(item, ComponentItem):
            component_id = item.component.id
            scene.select_only(component_id)
            menu.addAction(
                icon("edit"), "Edit value…", lambda: self.edit_requested.emit(component_id)
            )
            menu.addAction(icon("rotate"), "Rotate", lambda: scene.rotate_component(component_id))
            menu.addAction(
                icon("parallel"),
                "Add parallel copy",
                lambda: self.parallel_requested.emit(component_id),
            )
            menu.addSeparator()
            menu.addAction(icon("trash", DANGER), "Delete", scene.delete_selected)
        elif isinstance(item, BatteryItem):
            menu.addAction(icon("edit"), "Change voltage…", scene.source_activated.emit)
        elif isinstance(item, WireItem):
            wire_item = item
            menu.addAction(
                "Add a bend here", lambda: scene.add_route_handle_at(wire_item.wire.id, scene_pos)
            )
            menu.addSeparator()
            menu.addAction(
                icon("trash", DANGER), "Delete wire", lambda: self._delete_only(wire_item)
            )
        elif isinstance(item, JunctionItem):
            junction = item
            menu.addAction(
                icon("trash", DANGER),
                "Delete junction and its wires",
                lambda: self._delete_only(junction),
            )
        elif isinstance(item, RouteHandleItem):
            handle = item
            menu.addAction(icon("trash", DANGER), "Remove bend", lambda: self._delete_only(handle))
        else:
            for kind in ("resistor", "capacitor", "inductor"):
                menu.addAction(
                    f"Add {KIND_NAMES[kind].lower()} here",
                    lambda chosen=kind: scene.place_component(chosen, scene_pos),
                )
            menu.addSeparator()
            menu.addAction(icon("fit"), "Show the whole circuit", self.fit_circuit)
        return menu

    @staticmethod
    def _delete_only(item: QGraphicsItem) -> None:
        scene = item.scene()
        if not isinstance(scene, CircuitScene):
            return
        scene.clearSelection()
        item.setSelected(True)
        scene.delete_selected()

    @property
    def zoom_level(self) -> float:
        return self.transform().m11()

    def zoom_by(self, factor: float, *, under_mouse: bool = False) -> None:
        current = self.zoom_level
        target = min(self.MAX_ZOOM, max(self.MIN_ZOOM, current * factor))
        if math.isclose(target, current, rel_tol=1e-9):
            return
        anchor = (
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
            if under_mouse
            else QGraphicsView.ViewportAnchor.AnchorViewCenter
        )
        previous_anchor = self.transformationAnchor()
        self.setTransformationAnchor(anchor)
        self.scale(target / current, target / current)
        self.setTransformationAnchor(previous_anchor)

    def zoom_in(self) -> None:
        self.zoom_by(1.25)

    def zoom_out(self) -> None:
        self.zoom_by(1 / 1.25)

    def fit_circuit(self) -> None:
        """Show the whole circuit, never magnifying a small one beyond 100 %."""
        scene = self.scene()
        if scene is None:
            return
        bounds = scene.itemsBoundingRect()
        if bounds.isEmpty():
            return
        margin = self.FIT_MARGIN
        bounds = bounds.adjusted(-margin, -margin, margin, margin)
        self.resetTransform()
        self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        if not self.banner.isHidden():
            # Leave room for the problem banner so it never covers the circuit.
            reserve = (self.banner.height() + 16) / max(self.zoom_level, 1e-6)
            bounds = bounds.adjusted(0, -reserve, 0, 0)
            self.resetTransform()
            self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        fitted = self.zoom_level
        clamped = min(1.0, max(self.MIN_ZOOM, fitted))
        if not math.isclose(clamped, fitted, rel_tol=1e-9):
            self.resetTransform()
            self.scale(clamped, clamped)
        self.centerOn(bounds.center())

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                self.zoom_by(1.15 ** (delta / 120.0), under_mouse=True)
            event.accept()
            return
        super().wheelEvent(event)

    def viewportEvent(self, event: QEvent) -> bool:
        if self._handle_pinch(event):
            return True
        return super().viewportEvent(event)

    def event(self, event: QEvent) -> bool:
        if self._handle_pinch(event):
            return True
        return super().event(event)

    def _handle_pinch(self, event: QEvent) -> bool:
        if event.type() != QEvent.Type.NativeGesture or not isinstance(event, QNativeGestureEvent):
            return False
        if event.gestureType() != Qt.NativeGestureType.ZoomNativeGesture:
            return False
        self.zoom_by(1.0 + event.value(), under_mouse=True)
        event.accept()
        return True

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat("application/x-circuitcanvas-component"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def _snap_tolerance(self) -> float:
        """The snap distance in scene units, so it feels the same at any zoom."""
        return CircuitScene.SNAP_DISTANCE / max(self.zoom_level, 1e-6)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if not event.mimeData().hasFormat("application/x-circuitcanvas-component"):
            super().dragMoveEvent(event)
            return
        event.acceptProposedAction()
        scene = self.scene()
        if isinstance(scene, CircuitScene):
            target = scene.nearest_wire(
                self.mapToScene(event.position().toPoint()), self._snap_tolerance()
            )
            scene.set_drop_highlight(target[0] if target is not None else None)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        scene = self.scene()
        if isinstance(scene, CircuitScene):
            scene.set_drop_highlight(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat("application/x-circuitcanvas-component"):
            super().dropEvent(event)
            return
        payload = event.mimeData().data("application/x-circuitcanvas-component").data()
        kind = bytes(payload).decode()
        scene = self.scene()
        assert isinstance(scene, CircuitScene)
        scene_pos = self.mapToScene(event.position().toPoint())
        scene.set_drop_highlight(None)
        scene.place_component(kind, scene_pos, self._snap_tolerance())
        event.acceptProposedAction()
