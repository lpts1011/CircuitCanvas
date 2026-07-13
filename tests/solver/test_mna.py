import numpy as np
import pytest

from circuitcanvas.commands.circuit_commands import insert_series
from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.solver.mna import assemble


def test_resistor_mna_solution_obeys_ohms_law() -> None:
    circuit = Circuit.new(12.0)
    insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)
    system = assemble(circuit.snapshot())

    solution = np.linalg.solve(system.g, system.source_vector)

    assert solution[system.node_indices["n_pos"]] == pytest.approx(12.0)
    assert solution[system.source_index] == pytest.approx(-0.12)
    assert np.linalg.norm(system.g @ solution - system.source_vector) < 1e-10


def test_capacitor_and_inductor_stamp_dynamic_matrix() -> None:
    circuit = Circuit.new(5.0)
    c1 = insert_series(circuit, circuit.open_edge, ComponentKind.CAPACITOR, 2e-6)
    l1 = insert_series(circuit, c1, ComponentKind.INDUCTOR, 3e-3)

    system = assemble(circuit.snapshot())

    assert np.count_nonzero(system.c) >= 3
    assert system.component_aux_indices[l1] >= 0
