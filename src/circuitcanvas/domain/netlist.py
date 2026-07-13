"""Derive stable electrical nodes from the explicit physical wiring graph."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from .wiring import EndpointRef, JunctionRef, TerminalRef

if TYPE_CHECKING:
    from .circuit import Circuit


@dataclass(frozen=True, slots=True)
class Connectivity:
    terminal_nodes: Mapping[TerminalRef, str]
    junction_nodes: Mapping[JunctionRef, str]

    def node_for(self, ref: EndpointRef) -> str:
        if isinstance(ref, TerminalRef):
            return self.terminal_nodes[ref]
        return self.junction_nodes[ref]


def _all_refs(circuit: Circuit) -> list[EndpointRef]:
    refs: list[EndpointRef] = [
        TerminalRef(circuit.source.id, "a"),
        TerminalRef(circuit.source.id, "b"),
    ]
    for component_id in sorted(circuit.components):
        refs.extend((TerminalRef(component_id, "a"), TerminalRef(component_id, "b")))
    refs.extend(JunctionRef(junction_id) for junction_id in sorted(circuit.junctions))
    return refs


def derive_connectivity(circuit: Circuit) -> Connectivity:
    refs = _all_refs(circuit)
    parent = {ref: ref for ref in refs}

    def find(ref: EndpointRef) -> EndpointRef:
        root = ref
        while parent[root] != root:
            root = parent[root]
        while parent[ref] != ref:
            next_ref = parent[ref]
            parent[ref] = root
            ref = next_ref
        return root

    def union(left: EndpointRef, right: EndpointRef) -> None:
        if left not in parent or right not in parent:
            missing = left if left not in parent else right
            raise KeyError(f"Unknown wiring endpoint: {missing}")
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            first, second = sorted((left_root, right_root), key=lambda item: item.key)
            parent[second] = first

    for wire in circuit.wires.values():
        union(wire.start, wire.end)

    groups: dict[EndpointRef, list[EndpointRef]] = {}
    for ref in refs:
        groups.setdefault(find(ref), []).append(ref)

    source_a = TerminalRef(circuit.source.id, "a")
    source_b = TerminalRef(circuit.source.id, "b")
    node_by_root: dict[EndpointRef, str] = {}
    other_index = 1
    for root, members in sorted(groups.items(), key=lambda item: min(ref.key for ref in item[1])):
        if source_b in members:
            node = "n_neg"
        elif source_a in members:
            node = "n_pos"
        else:
            node = f"n{other_index}"
            other_index += 1
        node_by_root[root] = node

    terminal_nodes = {ref: node_by_root[find(ref)] for ref in refs if isinstance(ref, TerminalRef)}
    junction_nodes = {ref: node_by_root[find(ref)] for ref in refs if isinstance(ref, JunctionRef)}
    return Connectivity(MappingProxyType(terminal_nodes), MappingProxyType(junction_nodes))
