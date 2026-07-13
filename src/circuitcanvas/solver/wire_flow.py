"""Reconstruct deterministic ideal-wire currents for visual animation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import lstsq  # type: ignore[import-untyped]

from circuitcanvas.domain.circuit import CircuitSnapshot
from circuitcanvas.domain.wiring import EndpointRef, TerminalRef, Wire

from .results import SimulationResult


@dataclass(frozen=True, slots=True)
class WireFlowResult:
    currents: Mapping[str, float]
    net_residuals: Mapping[str, float]


def _terminal_injections(
    snapshot: CircuitSnapshot, result: SimulationResult, index: int
) -> dict[TerminalRef, float]:
    source_current = float(result.source_current[index])
    injections = {
        TerminalRef(snapshot.source.id, "a"): -source_current,
        TerminalRef(snapshot.source.id, "b"): source_current,
    }
    for component in snapshot.components:
        current = float(result.branches[component.id].current[index])
        injections[TerminalRef(component.id, "a")] = -current
        injections[TerminalRef(component.id, "b")] = current
    return injections


def reconstruct_wire_flows(
    snapshot: CircuitSnapshot, result: SimulationResult, time_index: int
) -> WireFlowResult:
    if not snapshot.wires:
        return WireFlowResult(MappingProxyType({}), MappingProxyType({}))
    index = time_index % len(result.time)
    refs = {endpoint for wire in snapshot.wires for endpoint in (wire.start, wire.end)}
    parent = {ref: ref for ref in refs}

    def find(ref: EndpointRef) -> EndpointRef:
        if parent[ref] != ref:
            parent[ref] = find(parent[ref])
        return parent[ref]

    def union(left: EndpointRef, right: EndpointRef) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for wire in snapshot.wires:
        union(wire.start, wire.end)

    grouped_refs: dict[EndpointRef, list[EndpointRef]] = {}
    grouped_wires: dict[EndpointRef, list[Wire]] = {}
    for ref in refs:
        grouped_refs.setdefault(find(ref), []).append(ref)
    for wire in snapshot.wires:
        grouped_wires.setdefault(find(wire.start), []).append(wire)

    injections = _terminal_injections(snapshot, result, index)
    currents: dict[str, float] = {}
    residuals: dict[str, float] = {}
    for group_number, root in enumerate(sorted(grouped_refs, key=lambda ref: ref.key), start=1):
        group_refs = sorted(grouped_refs[root], key=lambda ref: ref.key)
        wires = grouped_wires[root]
        ref_indices = {ref: row for row, ref in enumerate(group_refs)}
        incidence = np.zeros((len(group_refs), len(wires)), dtype=float)
        for column, wire in enumerate(wires):
            incidence[ref_indices[wire.start], column] = -1.0
            incidence[ref_indices[wire.end], column] = 1.0
        injection_values = [
            injections.get(ref, 0.0) if isinstance(ref, TerminalRef) else 0.0
            for ref in group_refs
        ]
        q: NDArray[np.float64] = np.asarray(injection_values, dtype=np.float64)
        flow, _, _, _ = lstsq(incidence, -q, lapack_driver="gelsy")
        residual = float(np.max(np.abs(incidence @ flow + q)))
        for wire, value in zip(wires, flow, strict=True):
            currents[wire.id] = float(value)
        residuals[f"net{group_number}"] = residual
    return WireFlowResult(MappingProxyType(currents), MappingProxyType(residuals))
