"""Interactive smart-snap circuit canvas."""

from __future__ import annotations

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
from circuitcanvas.solver.results import SimulationResult

from .component_items import BatteryItem, ComponentItem, DropTargetItem
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
        self._wire_start: TerminalRef | None = None
        self._wire_preview: QGraphicsLineItem | None = None
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

    def _component_moved(self, component_id: str, x: float, y: float) -> None:
        self.command_stack.move_component(component_id, (x, y))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def _junction_moved(self, junction_id: str, x: float, y: float) -> None:
        self.command_stack.move_junction(junction_id, (x, y))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def _route_moved(self, wire_id: str, route_index: int, x: float, y: float) -> None:
        route = list(self.circuit.wires[wire_id].route)
        route[route_index] = (x, y)
        self.command_stack.set_wire_route(wire_id, tuple(route))
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)

    def selected_component_id(self) -> str | None:
        for item in self.selectedItems():
            if isinstance(item, ComponentItem):
                return item.component.id
        return None

    def _selection_updated(self) -> None:
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

    def connect_for_test(self, start: EndpointRef, end: EndpointRef) -> str:
        wire_id = self.command_stack.connect(start, end)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        return wire_id

    def split_wire_at(self, wire_id: str, position: QPointF) -> str:
        junction_id = self.command_stack.split_wire(wire_id, (position.x(), position.y()))
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

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, TerminalItem) and isinstance(item.ref, TerminalRef):
            self._wire_start = item.ref
            self._wire_preview = self.addLine(
                item.scenePos().x(),
                item.scenePos().y(),
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
            self._wire_preview.setLine(
                start.x(), start.y(), event.scenePos().x(), event.scenePos().y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._wire_start is None:
            super().mouseReleaseEvent(event)
            return
        start = self._wire_start
        target = self.itemAt(event.scenePos(), QTransform())
        if self._wire_preview is not None:
            self.removeItem(self._wire_preview)
        self._wire_start = None
        self._wire_preview = None
        if isinstance(target, TerminalItem) and target.ref != start:
            self.command_stack.connect(start, target.ref)
        elif isinstance(target, WireItem):
            junction_id = self.command_stack.split_wire(
                target.wire.id, (event.scenePos().x(), event.scenePos().y())
            )
            self.command_stack.connect(start, JunctionRef(junction_id))
        else:
            self.rebuild()
            event.accept()
            return
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, WireItem):
            route = (*item.wire.route, (event.scenePos().x(), event.scenePos().y()))
            self.command_stack.set_wire_route(item.wire.id, route)
            self.rebuild()
            self.circuit_changed.emit(self.circuit.revision)
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
        scene.insert_component_at(kind, scene_pos)
        event.acceptProposedAction()
