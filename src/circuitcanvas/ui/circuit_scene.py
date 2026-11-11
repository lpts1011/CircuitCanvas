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
    QPainterPath,
    QPen,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
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
from circuitcanvas.domain.layout import component_rotation, terminal_offset
from circuitcanvas.domain.netlist import derive_connectivity
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
    #: A short tip for the status bar, e.g. after a wire was released in empty space.
    hint_requested = Signal(str)

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
        self._wire_preview: QGraphicsPathItem | None = None
        self._wire_marker: QGraphicsEllipseItem | None = None
        self._wire_target: tuple[str, EndpointRef | str, QPointF] | None = None
        self._wire_gesture = 0
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
        self.cancel_wire()
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
        for junction_id, junction_item in self.junction_items.items():
            junction_item.set_dangling(len(self._wires_touching(JunctionRef(junction_id))) <= 1)

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
        dx, dy = end[0] - start[0], end[1] - start[1]
        # Terminal "a" faces the start of the wire, so each new wire runs straight
        # from its end to the component instead of doubling back underneath it.
        if abs(dx) < 1.0 and abs(dy) >= 1.0:
            rotation = 90 if dy > 0 else 270
        else:
            rotation = 0 if dx >= 0 else 180
        return before[-1], rotation, before[1:-1], after[1:-1]

    # ----- Finding room for a new component ------------------------------------------
    #
    #: Length of a component card along its wire, terminal to terminal.
    CARD_LENGTH = 168.0
    #: Half the card's size across the wire: lying flat, and standing upright.
    CARD_HALF_ACROSS = (49.0, 66.0)
    #: Bare wire kept visible between a new component and its neighbours or a corner.
    LEAD = 30.0

    def _card_rects(self, *, exclude: str | None = None) -> list[QRectF]:
        """The space taken by every component card and the battery."""
        rects = [
            item.sceneBoundingRect()
            for component_id, item in self.component_items.items()
            if component_id != exclude
        ]
        if self.battery_item is not None:
            rects.append(self.battery_item.sceneBoundingRect())
        return rects

    def _free_stretches(self) -> list[tuple[float, bool, str, QPointF]]:
        """Every clear straight run of wire: (length, is horizontal, wire, midpoint).

        A run is clear when a component placed anywhere on it would not touch
        another component, the battery, or a corner of the wire.
        """
        rects = self._card_rects()
        stretches: list[tuple[float, bool, str, QPointF]] = []
        for wire_id, item in self.wire_items.items():
            points = item.polyline_points()
            for start, end in zip(points, points[1:], strict=False):
                horizontal = abs(start.y() - end.y()) < 0.5
                vertical = abs(start.x() - end.x()) < 0.5
                if horizontal == vertical:
                    continue  # A diagonal (or zero-length) piece: components go on straight runs.
                if horizontal:
                    low, high = sorted((start.x(), end.x()))
                    level, half = start.y(), self.CARD_HALF_ACROSS[0]
                    blocked = [
                        (rect.left() - self.LEAD, rect.right() + self.LEAD)
                        for rect in rects
                        if rect.top() - half < level < rect.bottom() + half
                    ]
                else:
                    low, high = sorted((start.y(), end.y()))
                    level, half = start.x(), self.CARD_HALF_ACROSS[1]
                    blocked = [
                        (rect.top() - self.LEAD, rect.bottom() + self.LEAD)
                        for rect in rects
                        if rect.left() - half < level < rect.right() + half
                    ]
                cursor = low + self.LEAD
                limit = high - self.LEAD
                for block_low, block_high in sorted(blocked):
                    if block_low > cursor:
                        self._add_stretch(
                            stretches, wire_id, horizontal, level, cursor, min(block_low, limit)
                        )
                    cursor = max(cursor, block_high)
                self._add_stretch(stretches, wire_id, horizontal, level, cursor, limit)
        return stretches

    @staticmethod
    def _add_stretch(
        stretches: list[tuple[float, bool, str, QPointF]],
        wire_id: str,
        horizontal: bool,
        level: float,
        low: float,
        high: float,
    ) -> None:
        if high <= low:
            return
        middle = (low + high) / 2.0
        point = QPointF(middle, level) if horizontal else QPointF(level, middle)
        stretches.append((high - low, horizontal, wire_id, point))

    def _longest_wire_piece(self) -> tuple[str, QPointF]:
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

    def best_wire_insertion(self) -> tuple[str, QPointF]:
        """Where a clicked component goes: the middle of the longest clear run of wire.

        When nothing is clear (a crowded circuit) this falls back to the middle of
        the longest piece of wire; :meth:`add_component_in_series` makes room first.
        """
        fitting = [
            stretch for stretch in self._free_stretches() if stretch[0] >= self.CARD_LENGTH - 1e-6
        ]
        if fitting:
            # The longest run; a flat one wins a tie because it reads more easily.
            _, _, wire_id, point = max(fitting, key=lambda stretch: (stretch[0], stretch[1]))
            return wire_id, point
        return self._longest_wire_piece()

    def _make_room(self, merge_key: tuple[str, int]) -> bool:
        """Widen the circuit so one more component fits on a horizontal wire."""
        flat = [stretch for stretch in self._free_stretches() if stretch[1]]
        if not flat or self.battery_item is None:
            return False
        length, _, _, point = max(flat, key=lambda stretch: stretch[0])
        missing = self.CARD_LENGTH - length + 1.0
        if missing <= 0:
            return False
        # The battery never moves, so the side away from it slides outwards.
        distance = missing if point.x() > self.battery_item.scenePos().x() else -missing
        self.command_stack.shift_layout(point.x(), distance, merge_key=merge_key)
        self.rebuild()
        return True

    def add_component_in_series(self, kind: ComponentKind | str) -> str:
        """Add a component with one click: on a clear run of wire, never on top of another.

        A crowded circuit is widened first; that and the new component undo together.
        """
        self._wire_gesture += 1
        merge_key = ("add", self._wire_gesture)
        has_room = any(stretch[0] >= self.CARD_LENGTH - 1e-6 for stretch in self._free_stretches())
        if not has_room:
            self._make_room(merge_key)
        wire_id, position = self.best_wire_insertion()
        return self.insert_component_on_wire(kind, wire_id, position, merge_key=merge_key)

    def insert_component_on_wire(
        self,
        kind: ComponentKind | str,
        wire_id: str,
        position: QPointF,
        *,
        merge_key: tuple[str, int] | None = None,
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
            merge_key=merge_key,
        )
        self.rebuild()
        self.select_only(component_id)
        self.circuit_changed.emit(self.circuit.revision)
        return component_id

    #: How far apart stacked parallel components sit: flat ones, and upright ones.
    PARALLEL_STEP = (140.0, 190.0)

    def _terminal_point(
        self, position: tuple[float, float], rotation: int, terminal: str
    ) -> tuple[float, float]:
        dx, dy = terminal_offset(rotation, terminal)
        return (position[0] + dx, position[1] + dy)

    def _card_rect_at(self, position: tuple[float, float], rotation: int) -> QRectF:
        """The space a component card would take at ``position``."""
        if rotation % 180 == 90:
            return QRectF(position[0] - 66.0, position[1] - 84.0, 132.0, 168.0)
        return QRectF(position[0] - 84.0, position[1] - 49.0, 168.0, 98.0)

    def _spot_is_clear(
        self,
        anchor_id: str,
        position: tuple[float, float],
        rotation: int,
    ) -> bool:
        """Would a parallel copy at ``position`` sit on empty canvas, leads included?"""
        card = self._card_rect_at(position, rotation).adjusted(-10, -10, 10, 10)
        if any(card.intersects(rect) for rect in self._card_rects()):
            return False
        # A card lying on a wire would look as if it were part of that wire.
        for item in self.wire_items.values():
            points = item.polyline_points()
            for start, end in zip(points, points[1:], strict=False):
                span = QRectF(start, end).normalized().adjusted(-1, -1, 1, 1)
                if card.intersects(span):
                    return False
        # The two leads run straight from the neighbour's ends; nothing may be in the way.
        anchor_position = self.circuit.positions[anchor_id]
        others = self._card_rects(exclude=anchor_id)
        for terminal in ("a", "b"):
            start_point = self._terminal_point(anchor_position, rotation, terminal)
            end_point = self._terminal_point(position, rotation, terminal)
            lead = QRectF(QPointF(*start_point), QPointF(*end_point)).normalized()
            lead = lead.adjusted(-2, -2, 2, 2)
            if any(lead.intersects(rect) for rect in others):
                return False
        return True

    def _parallel_stack(self, component_id: str) -> list[str]:
        """This component and any parallel partners already lined up beside it."""
        connectivity = derive_connectivity(self.circuit)

        def ends(candidate: str) -> frozenset[str]:
            return frozenset(
                connectivity.node_for(TerminalRef(candidate, terminal)) for terminal in ("a", "b")
            )

        rotation = component_rotation(self.circuit, component_id)
        along = 1 if rotation % 180 == 90 else 0
        position = self.circuit.positions[component_id]
        target_ends = ends(component_id)
        if len(target_ends) != 2:
            return [component_id]
        return [
            candidate
            for candidate in self.circuit.components
            if candidate == component_id
            or (
                ends(candidate) == target_ends
                and component_rotation(self.circuit, candidate) == rotation
                and candidate in self.circuit.positions
                and abs(self.circuit.positions[candidate][along] - position[along]) < 1.0
            )
        ]

    def duplicate_parallel(self, component_id: str) -> str:
        """Add a copy in parallel, stacked next to the original on empty canvas."""
        component = self.circuit.components[component_id]
        rotation = component_rotation(self.circuit, component_id)
        upright = rotation % 180 == 90
        across = 0 if upright else 1  # Copies stack sideways for upright components.
        step = self.PARALLEL_STEP[1 if upright else 0]
        stack = self._parallel_stack(component_id)

        def spot(direction: int, steps: int) -> tuple[str, tuple[float, float]]:
            anchor = max(stack, key=lambda item: direction * self.circuit.positions[item][across])
            position = list(self.circuit.positions[anchor])
            position[across] += direction * step * steps
            return anchor, (position[0], position[1])

        anchor_id, new_position = spot(1, 1)
        for steps in range(1, 6):
            found = False
            for direction in (1, -1):
                candidate_anchor, candidate = spot(direction, steps)
                if self._spot_is_clear(candidate_anchor, candidate, rotation):
                    anchor_id, new_position, found = candidate_anchor, candidate, True
                    break
            if found:
                break

        anchor_position = self.circuit.positions[anchor_id]
        new_id = self.command_stack.add_parallel_wired(
            anchor_id,
            component.kind,
            component.value,
            new_position,
            rotation,
            octilinear_route(
                self._terminal_point(anchor_position, rotation, "a"),
                self._terminal_point(new_position, rotation, "a"),
            ),
            octilinear_route(
                self._terminal_point(anchor_position, rotation, "b"),
                self._terminal_point(new_position, rotation, "b"),
            ),
        )
        self.rebuild()
        self.select_only(new_id)
        self.circuit_changed.emit(self.circuit.revision)
        return new_id

    def connect_for_test(self, start: EndpointRef, end: EndpointRef) -> str:
        route = self.wire_route(start, self._endpoint_position(start), self._endpoint_position(end))
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

    # ----- Drawing wires -----------------------------------------------------------------
    #
    # Distances are in screen pixels, so the feel is the same at any zoom.
    #: Press this close to a dot to start a wire from it.
    GRAB_RADIUS = 14.0
    #: While dragging, the wire end jumps to a dot this close and the dot turns green.
    MAGNET_RADIUS = 28.0
    #: Otherwise it lands on a wire this close, which then gets a junction there.
    WIRE_MAGNET_RADIUS = 16.0

    def _scene_distance(self, pixels: float) -> float:
        views = self.views()
        zoom = views[0].transform().m11() if views else 1.0
        return pixels / max(zoom, 1e-6)

    def _connectable_items(self) -> list[tuple[EndpointRef, QGraphicsItem]]:
        items: list[tuple[EndpointRef, QGraphicsItem]] = [
            (terminal.ref, terminal) for terminal in self._terminal_items()
        ]
        items.extend(
            (JunctionRef(junction_id), item) for junction_id, item in self.junction_items.items()
        )
        return items

    def endpoint_near(
        self,
        position: QPointF,
        radius: float,
        *,
        exclude: EndpointRef | None = None,
        terminals_only: bool = False,
    ) -> EndpointRef | None:
        """The closest terminal (or junction) dot within ``radius`` scene units."""
        best: tuple[float, EndpointRef] | None = None
        for ref, item in self._connectable_items():
            if ref == exclude or (terminals_only and isinstance(ref, JunctionRef)):
                continue
            centre = item.scenePos()
            distance = math.dist((position.x(), position.y()), (centre.x(), centre.y()))
            if distance <= radius and (best is None or distance < best[0]):
                best = (distance, ref)
        return best[1] if best is not None else None

    def _terminal_direction(self, endpoint: EndpointRef) -> tuple[float, float] | None:
        """The way a terminal points out of its component, e.g. (-1, 0) for a left end."""
        if not isinstance(endpoint, TerminalRef):
            return None
        if endpoint.owner_id == self.circuit.source.id:
            owner: QGraphicsItem | None = self.battery_item
        else:
            owner = self.component_items.get(endpoint.owner_id)
        if owner is None:
            return None
        tip = self._endpoint_position(endpoint)
        centre = owner.scenePos()
        dx, dy = tip.x() - centre.x(), tip.y() - centre.y()
        length = math.hypot(dx, dy)
        return (dx / length, dy / length) if length > 1e-9 else None

    #: How far a wire runs straight out of a terminal before turning back past it.
    WIRE_STUB = 24.0

    def wire_route(
        self, start: EndpointRef, start_position: QPointF, end_position: QPointF
    ) -> tuple[tuple[float, float], ...]:
        """A clean right-angled route from a terminal to ``end_position``.

        The wire leaves a terminal along its component's axis. When the end lies
        ahead, one bend is enough; when it lies behind, the wire first runs a short
        stub outward, so it never travels along or across its own component.
        """
        sx, sy = start_position.x(), start_position.y()
        ex, ey = end_position.x(), end_position.y()
        direction = self._terminal_direction(start)
        if direction is None:
            if abs(ex - sx) < 1.0 or abs(ey - sy) < 1.0:
                return ()
            return ((ex, sy),) if abs(ex - sx) >= abs(ey - sy) else ((sx, ey),)
        ox, oy = direction
        stub = self.WIRE_STUB
        if abs(ox) >= abs(oy):
            outward = math.copysign(1.0, ox)
            if (ex - sx) * outward > 0:
                return () if abs(ey - sy) < 1.0 else ((ex, sy),)
            turn_x = sx + outward * stub
            return ((turn_x, sy), (turn_x, ey)) if abs(ey - sy) >= 1.0 else ()
        outward = math.copysign(1.0, oy)
        if (ey - sy) * outward > 0:
            return () if abs(ex - sx) < 1.0 else ((sx, ey),)
        turn_y = sy + outward * stub
        return ((sx, turn_y), (ex, turn_y)) if abs(ex - sx) >= 1.0 else ()

    def _wires_touching(self, endpoint: EndpointRef) -> set[str]:
        return {
            wire_id
            for wire_id, wire in self.circuit.wires.items()
            if endpoint in (wire.start, wire.end)
        }

    def begin_wire(self, start: EndpointRef) -> None:
        self.cancel_wire()
        self._wire_start = start
        self._wire_target = None
        pen = QPen(QColor("#94a3b8"), 3, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        self._wire_preview = self.addPath(QPainterPath(), pen)
        self._wire_preview.setZValue(20)
        self._wire_marker = self.addEllipse(
            QRectF(-7, -7, 14, 14), QPen(QColor("#ffffff"), 2), QColor("#16a34a")
        )
        self._wire_marker.setZValue(21)
        self._wire_marker.hide()
        for ref, item in self._connectable_items():
            if isinstance(item, (TerminalItem, JunctionItem)):
                item.set_wire_state(candidate=ref != start, targeted=False)

    def update_wire_drag(self, pointer: QPointF) -> None:
        """Move the end of the wire being drawn, snapping to the nearest target."""
        start = self._wire_start
        if start is None or self._wire_preview is None or self._wire_marker is None:
            return
        start_position = self._endpoint_position(start)
        self._wire_target = None
        end = pointer
        endpoint = self.endpoint_near(
            pointer, self._scene_distance(self.MAGNET_RADIUS), exclude=start
        )
        if endpoint is not None:
            end = self._endpoint_position(endpoint)
            self._wire_target = ("endpoint", endpoint, end)
        else:
            excluded = self._wires_touching(start)
            radius = self._scene_distance(self.WIRE_MAGNET_RADIUS)
            best: tuple[float, str, QPointF] | None = None
            for wire_id, wire_item in self.wire_items.items():
                if wire_id in excluded:
                    continue
                polyline = tuple((p.x(), p.y()) for p in wire_item.polyline_points())
                projected = project_to_polyline((pointer.x(), pointer.y()), polyline)
                distance = math.dist((pointer.x(), pointer.y()), projected)
                if distance <= radius and (best is None or distance < best[0]):
                    best = (distance, wire_id, QPointF(*projected))
            if best is not None:
                end = best[2]
                self._wire_target = ("wire", best[1], end)

        for ref, item in self._connectable_items():
            if isinstance(item, (TerminalItem, JunctionItem)):
                item.set_wire_state(
                    candidate=ref != start, targeted=endpoint is not None and ref == endpoint
                )
        on_wire = self._wire_target is not None and self._wire_target[0] == "wire"
        self._wire_marker.setVisible(on_wire)
        if on_wire:
            self._wire_marker.setPos(end)

        path = QPainterPath(start_position)
        for x, y in self.wire_route(start, start_position, end):
            path.lineTo(x, y)
        path.lineTo(end)
        self._wire_preview.setPath(path)
        connected = self._wire_target is not None
        self._wire_preview.setPen(
            QPen(
                QColor("#16a34a" if connected else "#94a3b8"),
                3,
                Qt.PenStyle.SolidLine if connected else Qt.PenStyle.DashLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )

    def finish_wire(self, pointer: QPointF) -> bool:
        """Release the wire being drawn. Returns True if a wire was created."""
        start = self._wire_start
        if start is None:
            return False
        self.update_wire_drag(pointer)
        target = self._wire_target
        self.cancel_wire()
        if target is None:
            self.hint_requested.emit(
                "No wire was added. Release on a dot or a wire to connect: "
                "it turns green when the wire will snap to it."
            )
            return False
        start_position = self._endpoint_position(start)
        self._wire_gesture += 1
        merge_key = ("wire", self._wire_gesture)
        kind, identifier, end_position = target
        route = self.wire_route(start, start_position, end_position)
        loose_end = (
            start.junction_id
            if isinstance(start, JunctionRef) and len(self._wires_touching(start)) == 1
            else None
        )
        if kind == "endpoint":
            assert isinstance(identifier, (TerminalRef, JunctionRef))
            self.command_stack.connect(start, identifier, route, merge_key=merge_key)
        else:
            assert isinstance(identifier, str)
            item = self.wire_items[identifier]
            polyline = tuple((p.x(), p.y()) for p in item.polyline_points())
            before, after = split_polyline(polyline, (end_position.x(), end_position.y()))
            junction_id = self.command_stack.split_wire(
                identifier, before[-1], before[1:-1], after[1:-1], merge_key=merge_key
            )
            self.command_stack.connect(start, JunctionRef(junction_id), route, merge_key=merge_key)
        if loose_end is not None:
            # The wire simply got longer: no dot is left where its loose end was.
            self.command_stack.dissolve_junction(loose_end, merge_key=merge_key)
        self.rebuild()
        self.circuit_changed.emit(self.circuit.revision)
        return True

    def cancel_wire(self) -> None:
        """Stop drawing a wire without changing the circuit (Esc)."""
        for preview in (self._wire_preview, self._wire_marker):
            if preview is not None and preview.scene() is self:
                self.removeItem(preview)
        self._wire_preview = None
        self._wire_marker = None
        self._wire_start = None
        self._wire_target = None
        for _ref, item in self._connectable_items():
            if isinstance(item, (TerminalItem, JunctionItem)):
                item.set_wire_state(candidate=False, targeted=False)

    @property
    def drawing_wire(self) -> bool:
        return self._wire_start is not None

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        position = event.scenePos()
        item = self.itemAt(position, QTransform())
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        start: EndpointRef | None = None
        if isinstance(item, TerminalItem):
            start = item.ref
        elif isinstance(item, JunctionItem):
            # A loose wire end continues its wire; a real junction needs Shift (a plain
            # drag slides it along its wire).
            start = JunctionRef(item.junction_id) if shift or item.dangling else None
        elif not isinstance(item, RouteHandleItem):
            # Pressing just beside a terminal still starts a wire from it.
            start = self.endpoint_near(
                position, self._scene_distance(self.GRAB_RADIUS), terminals_only=True
            )
        if start is not None:
            self.begin_wire(start)
            self.update_wire_drag(position)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._wire_start is not None:
            self.update_wire_drag(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._wire_start is None:
            super().mouseReleaseEvent(event)
            return
        if self._endpoint_position(self._wire_start) == event.scenePos() or (
            self.endpoint_near(event.scenePos(), self._scene_distance(self.GRAB_RADIUS))
            == self._wire_start
        ):
            # A click on a dot, not a drag: nothing to connect.
            self.cancel_wire()
            event.accept()
            return
        self.finish_wire(event.scenePos())
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

    def show_all_if_hidden(self) -> None:
        """Show the whole circuit again if part of it is off screen.

        Used after the app itself places something (a clicked component, a parallel
        copy), which may land outside the view or widen the circuit.
        """
        scene = self.scene()
        if scene is None:
            return
        bounds = scene.itemsBoundingRect()
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        if not visible.contains(bounds):
            self.fit_circuit()

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
