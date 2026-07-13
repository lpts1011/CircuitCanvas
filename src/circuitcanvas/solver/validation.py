"""Fast, actionable validation before numerical simulation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from circuitcanvas.domain.circuit import CircuitSnapshot


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    component_ids: tuple[str, ...] = ()
    severity: str = "error"


def validate(snapshot: CircuitSnapshot) -> tuple[Diagnostic, ...]:
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
