"""Implicit time integration for linear RLC networks."""

from __future__ import annotations

import numpy as np
from scipy.linalg import LinAlgError, lu_factor, lu_solve  # type: ignore[import-untyped]

from circuitcanvas.domain.circuit import CircuitSnapshot
from circuitcanvas.domain.components import Capacitor, Resistor

from .mna import MNASystem, assemble
from .results import BranchResult, SimulationResult
from .validation import validate


class CircuitSimulationError(RuntimeError):
    """Raised when a circuit cannot produce a trustworthy simulation."""


def _node_voltage(system: MNASystem, state: np.ndarray, node: str) -> np.ndarray:
    index = system.node_indices.get(node)
    if index is None:
        return np.zeros(state.shape[0], dtype=float)
    return state[:, index]


def _solve_state(
    snapshot: CircuitSnapshot, system: MNASystem
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    settings = snapshot.settings
    time = np.linspace(0.0, settings.duration, settings.samples, dtype=float)
    dt = float(time[1] - time[0])
    state = np.zeros((settings.samples, system.g.shape[0]), dtype=float)
    residual = np.zeros(settings.samples, dtype=float)
    b_on = system.source_vector
    b_off = np.zeros_like(b_on)

    try:
        if settings.method == "backward-euler":
            lhs = system.g + system.c / dt
            history = system.c / dt
            factor = lu_factor(lhs)
            for index in range(1, settings.samples):
                state[index] = lu_solve(factor, history @ state[index - 1] + b_on)
                equation = (
                    system.g @ state[index]
                    + system.c @ ((state[index] - state[index - 1]) / dt)
                    - b_on
                )
                residual[index] = np.linalg.norm(equation, ord=np.inf)
        else:
            lhs = system.g + 2.0 * system.c / dt
            history = 2.0 * system.c / dt - system.g
            factor = lu_factor(lhs)
            for index in range(1, settings.samples):
                previous_b = b_off if index == 1 else b_on
                state[index] = lu_solve(
                    factor,
                    history @ state[index - 1] + previous_b + b_on,
                )
                equation = (
                    system.g @ ((state[index] + state[index - 1]) / 2.0)
                    + system.c @ ((state[index] - state[index - 1]) / dt)
                    - (previous_b + b_on) / 2.0
                )
                residual[index] = np.linalg.norm(equation, ord=np.inf)
    except (LinAlgError, ValueError) as exc:
        raise CircuitSimulationError(
            "The circuit equations are singular. Check for floating nodes or ideal loops."
        ) from exc

    if not np.isfinite(state).all():
        raise CircuitSimulationError(
            "The transient solution became non-finite. Reduce the time step or check values."
        )
    return time, state, residual


def simulate(snapshot: CircuitSnapshot) -> SimulationResult:
    diagnostics = validate(snapshot)
    if diagnostics:
        raise CircuitSimulationError(diagnostics[0].message)

    system = assemble(snapshot)
    time, state, residual = _solve_state(snapshot, system)
    dt = float(time[1] - time[0])
    node_voltages = {node: _node_voltage(system, state, node) for node in snapshot.nodes}
    branches: dict[str, BranchResult] = {}

    for component in snapshot.components:
        voltage = node_voltages[component.node_a] - node_voltages[component.node_b]
        if isinstance(component, Resistor):
            current = voltage / component.resistance
            energy = np.zeros_like(voltage)
        elif isinstance(component, Capacitor):
            current = np.zeros_like(voltage)
            current[1:] = component.capacitance * np.diff(voltage) / dt
            current[0] = current[1]
            energy = 0.5 * component.capacitance * voltage**2
        else:
            current = state[:, system.component_aux_indices[component.id]]
            energy = 0.5 * component.inductance * current**2
        power = voltage * current
        branches[component.id] = BranchResult(voltage, current, power, energy)

    source_current = state[:, system.source_index]
    source_voltage = np.full_like(source_current, snapshot.source.voltage)
    source_voltage[0] = 0.0
    source_power = source_voltage * source_current
    peak_current = float(np.max(np.abs(source_current)))
    total_energy = float(sum(branch.energy[-1] for branch in branches.values()))

    return SimulationResult.create(
        time=time,
        state=state,
        node_voltages=node_voltages,
        branches=branches,
        source_current=source_current,
        source_power=source_power,
        kcl_residual=residual,
        metrics={
            "peak_current_a": peak_current,
            "final_source_current_a": float(source_current[-1]),
            "final_source_power_w": float(source_power[-1]),
            "stored_energy_j": total_energy,
            "max_residual": float(np.max(residual)),
        },
    )
