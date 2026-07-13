import csv

from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.solver.transient import simulate
from circuitcanvas.ui.circuit_scene import CircuitScene
from circuitcanvas.ui.export import export_branch_csv, export_scene_png


def test_csv_has_aligned_physical_columns(tmp_path, qtbot) -> None:
    scene = CircuitScene(Circuit.new(10.0))
    component_id = scene.insert_component_for_test("resistor")
    result = simulate(scene.circuit.snapshot())
    path = tmp_path / "R1.csv"

    export_branch_csv(path, result, component_id)

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["time_s", "voltage_v", "current_a", "power_w", "energy_j"]
    assert len(rows) == len(result.time) + 1
    assert float(rows[-1][1]) == result.branches[component_id].voltage[-1]


def test_scene_png_is_non_empty(tmp_path, qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    scene.insert_component_for_test("resistor")
    path = tmp_path / "circuit.png"

    export_scene_png(path, scene)

    assert path.stat().st_size > 1000
