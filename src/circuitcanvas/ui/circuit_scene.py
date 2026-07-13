"""Interactive smart-snap circuit canvas."""

from __future__ import annotations

import math
from collections import defaultdict

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPainter,
    QPen,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QWidget,
)

from circuitcanvas.commands.circuit_commands import CircuitCommandStack
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.wiring import EndpointRef, JunctionRef, TerminalRef
from circuitcanvas.solver.equations import EquationLine
from circuitcanvas.solver.results import SimulationResult

from .component_items import BatteryItem, ComponentItem, DropTargetItem
from .routing import (
    normalized_octilinear_polyline,
    octilinear_route,
    project_to_octilinear,
    project_to_polyline,
    split_polyline,
)
from .wire_items import JunctionItem, RouteHandleItem, TerminalItem, WireItem

DEFAULT_VALUES = {
    ComponentKind.RESISTOR: 100.0,
    ComponentKind.CAPACITOR: 47e-6,
    ComponentKind.INDUCTOR: 22e-3,
}


class CircuitScene(QGraphicsScene):
    circuit_changed = Signal(int)
    selection_changed = Signal(str)

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
        self._wire_start: EndpointRef | None = None
        self._wire_preview: QGraphicsLineItem | None = None
        self._suppress_selection_signal = False
        self.highlighted_components: set[str] = set()
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
        if self._uses_free_wiring():
            self._rebuild_free()
        else:
            self._rebuild_legacy()

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
        self.command_stack.move_component(component_id, (x, y))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def _junction_moved(self, junction_id: str, x: float, y: float) -> None:
        candidates = []
        junction_ref = JunctionRef(junction_id)
        for wire_id, wire in self.circuit.wires.items():
            if junction_ref in (wire.start, wire.end):
                candidates.append(project_to_polyline((x, y), self._stored_wire_polyline(wire_id)))
        previous = self.circuit.junctions[junction_id].position
        constrained = min(candidates, key=lambda point: math.dist(point, (x, y)), default=previous)
        self.command_stack.move_junction(junction_id, constrained)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def _route_moved(self, wire_id: str, route_index: int, x: float, y: float) -> None:
        route = list(self.circuit.wires[wire_id].route)
        route[route_index] = project_to_polyline((x, y), self._stored_wire_polyline(wire_id))
        self.command_stack.set_wire_route(wire_id, tuple(route))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def selected_component_id(self) -> str | None:
        for item in self.selectedItems():
            if isinstance(item, ComponentItem):
                return item.component.id
        return None

    def _selection_updated(self) -> None:
        if self._suppress_selection_signal:
            return
        selected = self.selected_component_id()
        if selected is not None:
            self.selection_changed.emit(selected)

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
        self.component_items[component_id].setSelected(True)
        self.circuit_changed.emit(self.circuit.revision)
        return component_id

    def insert_component_at(self, kind: ComponentKind | str, position: QPointF) -> str:
        component_kind = kind if isinstance(kind, ComponentKind) else ComponentKind(kind)
        component_id = self.command_stack.add_loose_component(
            component_kind, DEFAULT_VALUES[component_kind], (position.x(), position.y())
        )
        self.rebuild()
        self.component_items[component_id].setSelected(True)
        self.circuit_changed.emit(self.circuit.revision)
        return component_id

    def place_component(self, kind: ComponentKind | str, position: QPointF) -> str:
        item = self.itemAt(position, QTransform())
        if isinstance(item, WireItem):
            return self.insert_component_on_wire(kind, item.wire.id, position)
        return self.insert_component_at(kind, position)

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
        polyline = self._stored_wire_polyline(wire_id)
        pointer = (position.x(), position.y())
        if len(polyline) < 2:
            raise ValueError("Cannot insert a component on a zero-length wire")
        before, after = split_polyline(polyline, pointer)
        center = before[-1]
        start = before[-2]
        end = after[1]
        vertical = abs(end[0] - start[0]) < 1.0 and abs(end[1] - start[1]) >= 1.0
        rotation = 90 if vertical else 0
        component_id = self.command_stack.insert_component_on_wire(
            wire_id,
            component_kind,
            DEFAULT_VALUES[component_kind],
            center,
            rotation,
            before[1:-1],
            after[1:-1],
        )
        self.rebuild()
        self.component_items[component_id].setSelected(True)
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
        self.component_items[new_id].setSelected(True)
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

    def rotate_selected(self) -> None:
        component_id = self.selected_component_id()
        if component_id is None:
            return
        self.command_stack.rotate_component(component_id)
        self.rebuild()
        self.component_items[component_id].setSelected(True)
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

    def highlight_equation(self, line: EquationLine) -> None:
        self._suppress_selection_signal = True
        try:
            self.clearSelection()
            self.highlighted_components = set(line.component_ids)
            for component_id in line.component_ids:
                item = self.component_items.get(component_id)
                if item is not None:
                    item.setSelected(True)
        finally:
            self._suppress_selection_signal = False

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

    def set_result(self, result: SimulationResult, time_index: int) -> None:
        index = max(0, min(time_index, len(result.time) - 1))
        for component_id, item in self.component_items.items():
            branch = result.branches.get(component_id)
            if branch is not None:
                item.set_measurement(float(branch.voltage[index]), float(branch.current[index]))

    def replace_circuit(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self.command_stack = CircuitCommandStack(circuit)
        self.rebuild()


class CircuitView(QGraphicsView):
    """Zoomable view that accepts component MIME drops."""

    def __init__(self, scene: CircuitScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat("application/x-circuitcanvas-component"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat("application/x-circuitcanvas-component"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat("application/x-circuitcanvas-component"):
            super().dropEvent(event)
            return
        payload = event.mimeData().data("application/x-circuitcanvas-component").data()
        kind = bytes(payload).decode()
        scene = self.scene()
        assert isinstance(scene, CircuitScene)
        scene_pos = self.mapToScene(event.position().toPoint())
        scene.place_component(kind, scene_pos)
        event.acceptProposedAction()
