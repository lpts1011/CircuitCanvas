"""Linear Modified Nodal Analysis matrix assembly."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from circuitcanvas.domain.circuit import CircuitSnapshot
from circuitcanvas.domain.components import Capacitor, Inductor, Resistor

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class MNASystem:
    g: FloatArray
    c: FloatArray
    source_vector: FloatArray
    node_indices: dict[str, int]
    source_index: int
    component_aux_indices: dict[str, int]
    unknowns: tuple[str, ...]


def _stamp_pair(matrix: FloatArray, indices: dict[str, int], a: str, b: str, value: float) -> None:
    ia = indices.get(a)
    ib = indices.get(b)
    if ia is not None:
        matrix[ia, ia] += value
    if ib is not None:
        matrix[ib, ib] += value
    if ia is not None and ib is not None:
        matrix[ia, ib] -= value
        matrix[ib, ia] -= value


def _stamp_incidence(
    matrix: FloatArray, indices: dict[str, int], a: str, b: str, auxiliary: int
) -> None:
    ia = indices.get(a)
    ib = indices.get(b)
    if ia is not None:
        matrix[ia, auxiliary] += 1.0
        matrix[auxiliary, ia] += 1.0
    if ib is not None:
        matrix[ib, auxiliary] -= 1.0
        matrix[auxiliary, ib] -= 1.0


def assemble(snapshot: CircuitSnapshot) -> MNASystem:
    ground = snapshot.source.node_b
    node_names = sorted(node for node in snapshot.nodes if node != ground)
    node_indices = {node: index for index, node in enumerate(node_names)}
    inductors = [component for component in snapshot.components if isinstance(component, Inductor)]
    source_index = len(node_names)
    size = len(node_names) + 1 + len(inductors)
    g = np.zeros((size, size), dtype=float)
    c = np.zeros_like(g)
    source_vector = np.zeros(size, dtype=float)
    component_aux_indices: dict[str, int] = {}

    _stamp_incidence(
        g,
        node_indices,
        snapshot.source.node_a,
        snapshot.source.node_b,
        source_index,
    )
    source_vector[source_index] = snapshot.source.voltage

    next_aux = source_index + 1
    for component in snapshot.components:
        if isinstance(component, Resistor):
            _stamp_pair(
                g,
                node_indices,
                component.node_a,
                component.node_b,
                1.0 / component.resistance,
            )
        elif isinstance(component, Capacitor):
            _stamp_pair(
                c,
                node_indices,
                component.node_a,
                component.node_b,
                component.capacitance,
            )
        else:
            _stamp_incidence(g, node_indices, component.node_a, component.node_b, next_aux)
            c[next_aux, next_aux] -= component.inductance
            component_aux_indices[component.id] = next_aux
            next_aux += 1

    unknowns = (
        tuple(node_names)
        + (f"I({snapshot.source.id})",)
        + tuple(f"I({component.id})" for component in inductors)
    )
    return MNASystem(
        g,
        c,
        source_vector,
        node_indices,
        source_index,
        component_aux_indices,
        unknowns,
    )
