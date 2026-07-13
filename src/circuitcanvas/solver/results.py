"""Immutable arrays returned by a transient simulation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class BranchResult:
    voltage: FloatArray
    current: FloatArray
    power: FloatArray
    energy: FloatArray


@dataclass(frozen=True, slots=True)
class SimulationResult:
    time: FloatArray
    state: FloatArray
    node_voltages: Mapping[str, FloatArray]
    branches: Mapping[str, BranchResult]
    source_current: FloatArray
    source_power: FloatArray
    kcl_residual: FloatArray
    metrics: Mapping[str, float]

    @classmethod
    def create(
        cls,
        *,
        time: FloatArray,
        state: FloatArray,
        node_voltages: dict[str, FloatArray],
        branches: dict[str, BranchResult],
        source_current: FloatArray,
        source_power: FloatArray,
        kcl_residual: FloatArray,
        metrics: dict[str, float],
    ) -> SimulationResult:
        for array in [time, state, source_current, source_power, kcl_residual]:
            array.setflags(write=False)
        return cls(
            time,
            state,
            MappingProxyType(node_voltages),
            MappingProxyType(branches),
            source_current,
            source_power,
            kcl_residual,
            MappingProxyType(metrics),
        )

