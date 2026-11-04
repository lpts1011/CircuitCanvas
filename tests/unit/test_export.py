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


def test_all_component_csv_has_one_column_group_per_component(tmp_path, qtbot) -> None:
    from circuitcanvas.ui.export import export_all_branches_csv

    scene = CircuitScene(Circuit.starter_loop(10.0))
    scene.insert_component_on_wire("resistor", *scene.best_wire_insertion())
    scene.insert_component_on_wire("capacitor", *scene.best_wire_insertion())
    result = simulate(scene.circuit.snapshot())
    path = tmp_path / "circuit-data.csv"

    export_all_branches_csv(path, result)

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:3] == ["time_s", "source_current_a", "source_power_w"]
    assert "C1_voltage_v" in rows[0] and "R1_energy_j" in rows[0]
    assert len(rows) == len(result.time) + 1
    column = rows[0].index("C1_voltage_v")
    assert float(rows[-1][column]) == result.branches["C1"].voltage[-1]
