"""Interactive smart-snap circuit canvas."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QObject, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from circuitcanvas.commands.circuit_commands import CircuitCommandStack
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.solver.results import SimulationResult

from .component_items import BatteryItem, ComponentItem, DropTargetItem

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
        self.battery_item: BatteryItem | None = None
        self.open_target: DropTargetItem | None = None
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
        selected = self.selected_component_id()
        self.clear()
        self.component_items = {}
        self.battery_item = BatteryItem(self.circuit.source.voltage)
        self.battery_item.setPos(90, 270)
        self.addItem(self.battery_item)

        wire_pen = QPen(QColor("#334155"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self.addLine(90, 200, 170, 200, wire_pen)
        self.addLine(90, 340, 980, 340, wire_pen)
        self.addLine(980, 200, 980, 340, wire_pen)

        if not self.circuit.components:
            self.open_target = DropTargetItem()
            self.open_target.setPos(400, 200)
            self.addItem(self.open_target)
            self.addLine(170, 200, 306, 200, wire_pen)
            self.addLine(494, 200, 980, 200, wire_pen)
            return

        self.open_target = None
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for component in self.circuit.components.values():
            groups[component.endpoints].append(component.id)

        x_positions: list[float] = []
        for index, (component_id, component) in enumerate(self.circuit.components.items()):
            siblings = groups[component.endpoints]
            sibling_index = siblings.index(component_id)
            x = 260.0 + index * 170.0
            y = 200.0 + sibling_index * 112.0
            x_positions.append(x)
            item = ComponentItem(component)
            item.setPos(x, y)
            self.addItem(item)
            self.component_items[component_id] = item
            self.circuit.positions[component_id] = (x, y)
            self.addLine(x - 84, y, x - 105, y, wire_pen)
            self.addLine(x + 84, y, x + 105, y, wire_pen)

        first_x = min(x_positions)
        last_x = max(x_positions)
        self.addLine(170, 200, first_x - 105, 200, wire_pen)
        self.addLine(last_x + 105, 200, 980, 200, wire_pen)
        if selected in self.component_items:
            self.component_items[selected].setSelected(True)

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
        nearest = min(
            scene.component_items.values(),
            key=lambda item: (item.scenePos() - scene_pos).manhattanLength(),
            default=None,
        )
        parallel_to = None
        if nearest is not None and abs(scene_pos.y() - nearest.scenePos().y()) > 55:
            parallel_to = nearest.component.id
        scene.insert_component_for_test(kind, parallel_to=parallel_to)
        event.acceptProposedAction()
