"""Fast, actionable validation before numerical simulation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from circuitcanvas.domain.circuit import CircuitSnapshot
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    component_ids: tuple[str, ...] = ()
    severity: str = "error"


def validate(snapshot: CircuitSnapshot) -> tuple[Diagnostic, ...]:
    if snapshot.wires:
        if snapshot.source.node_a == snapshot.source.node_b:
            return (
                Diagnostic(
                    "source-short",
                    "An ideal wire directly shorts the battery terminals.",
                    (snapshot.source.id,),
                ),
            )
        connected_terminals = {
            endpoint
            for wire in snapshot.wires
            for endpoint in (wire.start, wire.end)
            if isinstance(endpoint, TerminalRef)
        }
        dangling_components = tuple(
            component.id
            for component in snapshot.components
            if TerminalRef(component.id, "a") not in connected_terminals
            or TerminalRef(component.id, "b") not in connected_terminals
        )
        if dangling_components:
            return (
                Diagnostic(
                    "dangling-terminal",
                    "A component terminal is not connected. Draw a wire from each orange terminal.",
                    dangling_components,
                ),
            )
        junction_degree: dict[str, int] = {}
        for wire in snapshot.wires:
            for endpoint in (wire.start, wire.end):
                if isinstance(endpoint, JunctionRef):
                    junction_degree[endpoint.junction_id] = (
                        junction_degree.get(endpoint.junction_id, 0) + 1
                    )
        dangling_junctions = tuple(
            junction_id for junction_id, degree in junction_degree.items() if degree < 2
        )
        if dangling_junctions:
            return (
                Diagnostic(
                    "dangling-wire",
                    "A wire ends at an unconnected junction.",
                ),
            )
    if not snapshot.components:
        return (
            Diagnostic(
                "open-circuit",
                "The loop is open. Drop a component onto the highlighted opening.",
            ),
        )

    adjacency: dict[str, set[str]] = defaultdict(set)
    for component in snapshot.components:
        adjacency[component.node_a].add(component.node_b)
        adjacency[component.node_b].add(component.node_a)

    reachable: set[str] = set()
    queue = deque([snapshot.source.node_a])
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        queue.extend(adjacency[node] - reachable)

    if snapshot.source.node_b not in reachable:
        return (
            Diagnostic(
                "open-circuit",
                "No complete component path connects the battery terminals.",
                tuple(component.id for component in snapshot.components),
            ),
        )

    floating = tuple(
        component.id
        for component in snapshot.components
        if component.node_a not in reachable and component.node_b not in reachable
    )
    if floating:
        return (
            Diagnostic(
                "floating-subcircuit",
                "A disconnected component group is floating and cannot be simulated.",
                floating,
            ),
        )
    return ()
