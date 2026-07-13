"""Human-readable Kirchhoff equations generated from solved circuit topology."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np

from circuitcanvas.domain.circuit import CircuitSnapshot
from circuitcanvas.domain.components import Capacitor, Inductor, Resistor

from .mna import assemble
from .results import SimulationResult


@dataclass(frozen=True, slots=True)
class EquationLine:
    id: str
    kind: Literal["kcl", "kvl", "law"]
    symbolic: str
    substituted: str
    result: str
    residual: float
    component_ids: tuple[str, ...]
    node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EquationReport:
    kcl: tuple[EquationLine, ...]
    kvl: tuple[EquationLine, ...]
    laws: tuple[EquationLine, ...]
    differential_text: str
    descriptor_text: str


@dataclass(frozen=True, slots=True)
class _Edge:
    id: str
    node_a: str
    node_b: str
    voltage: float
    current: float


def _signed_expression(terms: list[tuple[int, str]]) -> str:
    pieces: list[str] = []
    for index, (sign, name) in enumerate(terms):
        if index == 0:
            pieces.append(name if sign > 0 else f"-{name}")
        else:
            pieces.append((" + " if sign > 0 else " - ") + name)
    return "".join(pieces) if pieces else "0"


def _numeric_expression(terms: list[tuple[int, float]]) -> str:
    signed_values = [
        (1 if sign * value >= 0.0 else -1, f"{abs(sign * value):.6g}") for sign, value in terms
    ]
    return _signed_expression(signed_values)


def _edges(snapshot: CircuitSnapshot, result: SimulationResult, index: int) -> list[_Edge]:
    source_voltage = float(
        result.node_voltages[snapshot.source.node_a][index]
        - result.node_voltages[snapshot.source.node_b][index]
    )
    edges = [
        _Edge(
            snapshot.source.id,
            snapshot.source.node_a,
            snapshot.source.node_b,
            source_voltage,
            float(result.source_current[index]),
        )
    ]
    for component in snapshot.components:
        branch = result.branches[component.id]
        edges.append(
            _Edge(
                component.id,
                component.node_a,
                component.node_b,
                float(branch.voltage[index]),
                float(branch.current[index]),
            )
        )
    return edges


def _kcl_lines(snapshot: CircuitSnapshot, edges: list[_Edge]) -> tuple[EquationLine, ...]:
    lines: list[EquationLine] = []
    ground = snapshot.source.node_b
    for number, node in enumerate((node for node in snapshot.nodes if node != ground), start=1):
        signed_edges: list[tuple[int, _Edge]] = []
        for edge in edges:
            if edge.node_a == node:
                signed_edges.append((1, edge))
            elif edge.node_b == node:
                signed_edges.append((-1, edge))
        residual = sum(sign * edge.current for sign, edge in signed_edges)
        terms = [(sign, f"I_{edge.id}") for sign, edge in signed_edges]
        values = [(sign, edge.current) for sign, edge in signed_edges]
        lines.append(
            EquationLine(
                f"KCL{number}",
                "kcl",
                f"{_signed_expression(terms)} = 0",
                f"{_numeric_expression(values)} = 0",
                f"residual = {residual:.3g} A",
                residual,
                tuple(edge.id for _, edge in signed_edges),
                (node,),
            )
        )
    return tuple(lines)


def _tree_path(
    adjacency: dict[str, list[tuple[str, int]]], start: str, goal: str
) -> list[tuple[int, str, str]]:
    queue = deque([start])
    previous: dict[str, tuple[str, int] | None] = {start: None}
    while queue:
        node = queue.popleft()
        if node == goal:
            break
        for neighbor, edge_index in adjacency.get(node, []):
            if neighbor not in previous:
                previous[neighbor] = (node, edge_index)
                queue.append(neighbor)
    if goal not in previous:
        return []
    path: list[tuple[int, str, str]] = []
    current = goal
    while current != start:
        entry = previous[current]
        assert entry is not None
        parent, edge_index = entry
        path.append((edge_index, parent, current))
        current = parent
    path.reverse()
    return path


def _cycle_edges(edges: list[_Edge]) -> list[list[tuple[int, int]]]:
    parent: dict[str, str] = {}
    adjacency: dict[str, list[tuple[str, int]]] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    cycles: list[list[tuple[int, int]]] = []
    for index, edge in enumerate(edges):
        root_a = find(edge.node_a)
        root_b = find(edge.node_b)
        if root_a != root_b:
            parent[root_b] = root_a
            adjacency.setdefault(edge.node_a, []).append((edge.node_b, index))
            adjacency.setdefault(edge.node_b, []).append((edge.node_a, index))
            continue
        cycle: list[tuple[int, int]] = [(index, 1)]
        for tree_index, path_from, path_to in _tree_path(adjacency, edge.node_b, edge.node_a):
            tree_edge = edges[tree_index]
            sign = 1 if (tree_edge.node_a, tree_edge.node_b) == (path_from, path_to) else -1
            cycle.append((tree_index, sign))
        cycles.append(cycle)
    return cycles


def _kvl_lines(edges: list[_Edge]) -> tuple[EquationLine, ...]:
    lines: list[EquationLine] = []
    for number, cycle in enumerate(_cycle_edges(edges), start=1):
        residual = sum(sign * edges[index].voltage for index, sign in cycle)
        terms = [(sign, f"V_{edges[index].id}") for index, sign in cycle]
        values = [(sign, edges[index].voltage) for index, sign in cycle]
        component_ids = tuple(edges[index].id for index, _ in cycle)
        node_ids = tuple(
            dict.fromkeys(
                node for index, _ in cycle for node in (edges[index].node_a, edges[index].node_b)
            )
        )
        lines.append(
            EquationLine(
                f"KVL{number}",
                "kvl",
                f"{_signed_expression(terms)} = 0",
                f"{_numeric_expression(values)} = 0",
                f"residual = {residual:.3g} V",
                residual,
                component_ids,
                node_ids,
            )
        )
    return tuple(lines)


def _law_lines(
    snapshot: CircuitSnapshot, result: SimulationResult, index: int
) -> tuple[EquationLine, ...]:
    lines: list[EquationLine] = []
    dt = float(result.time[1] - result.time[0])
    previous = max(0, index - 1)
    for component in snapshot.components:
        branch = result.branches[component.id]
        voltage = float(branch.voltage[index])
        current = float(branch.current[index])
        if isinstance(component, Resistor):
            symbolic = f"V_{component.id} = {component.id}·I_{component.id}"
            residual = voltage - component.resistance * current
        elif isinstance(component, Capacitor):
            symbolic = f"I_{component.id} = {component.id}·dv_{component.id}/dt"
            derivative = float(branch.voltage[index] - branch.voltage[previous]) / dt
            residual = current - component.capacitance * derivative
        else:
            symbolic = f"V_{component.id} = {component.id}·di_{component.id}/dt"
            derivative = float(branch.current[index] - branch.current[previous]) / dt
            residual = voltage - component.inductance * derivative
        lines.append(
            EquationLine(
                f"LAW-{component.id}",
                "law",
                symbolic,
                f"V={voltage:.6g} V, I={current:.6g} A",
                f"residual = {residual:.3g}",
                residual,
                (component.id,),
                component.endpoints,
            )
        )
    return tuple(lines)


def _differential_text(snapshot: CircuitSnapshot) -> str:
    lines: list[str] = []
    for component in snapshot.components:
        if isinstance(component, Resistor):
            lines.append(f"v_{component.id}(t) = {component.id}·i_{component.id}(t)")
        elif isinstance(component, Capacitor):
            lines.append(f"i_{component.id}(t) = {component.id}·dv_{component.id}/dt")
        elif isinstance(component, Inductor):
            lines.append(f"v_{component.id}(t) = {component.id}·di_{component.id}/dt")
    return "\n".join(lines)


def _descriptor_text(snapshot: CircuitSnapshot) -> str:
    system = assemble(snapshot)
    return "\n".join(
        (
            "Differential-algebraic MNA system",
            "C x_dot(t) + G x(t) = b(t)",
            f"x = {system.unknowns}",
            "C = " + np.array2string(system.c, precision=5, suppress_small=True),
            "G = " + np.array2string(system.g, precision=5, suppress_small=True),
            "b = " + np.array2string(system.source_vector, precision=5, suppress_small=True),
        )
    )


def build_equation_report(
    snapshot: CircuitSnapshot, result: SimulationResult, time_index: int
) -> EquationReport:
    index = time_index % len(result.time)
    edges = _edges(snapshot, result, index)
    return EquationReport(
        _kcl_lines(snapshot, edges),
        _kvl_lines(edges),
        _law_lines(snapshot, result, index),
        _differential_text(snapshot),
        _descriptor_text(snapshot),
    )
