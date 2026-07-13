import json

import pytest

from circuitcanvas.commands.circuit_commands import CircuitCommandStack, add_parallel, insert_series
from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.serialization import (
    CircuitFileError,
    circuit_from_dict,
    circuit_to_dict,
    load_circuit,
    save_circuit,
)
from circuitcanvas.domain.wiring import JunctionRef, TerminalRef


def test_circuit_round_trip_preserves_topology_values_and_layout(tmp_path) -> None:
    circuit = Circuit.new(9.0)
    r1 = insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 330.0)
    c1 = add_parallel(circuit, r1, ComponentKind.CAPACITOR, 47e-6)
    circuit.positions[r1] = (120.5, -30.0)
    circuit.positions[c1] = (120.5, 70.0)
    circuit.settings = SimulationSettings(duration=0.2, samples=600, method="backward-euler")
    path = tmp_path / "example.circuitcanvas"

    save_circuit(path, circuit)
    restored = load_circuit(path)

    assert restored.source.voltage == 9.0
    assert restored.components[r1].value == 330.0
    assert restored.components[c1].endpoints == restored.components[r1].endpoints
    assert restored.positions[c1] == (120.5, 70.0)
    assert restored.settings == circuit.settings


def test_schema_version_error_is_explicit() -> None:
    with pytest.raises(CircuitFileError, match="version 99.*version 2"):
        circuit_from_dict({"schema_version": 99})


def test_serialized_payload_does_not_include_computed_results() -> None:
    payload = circuit_to_dict(Circuit.new())

    assert payload["schema_version"] == 2
    assert "results" not in json.dumps(payload).lower()


def test_schema_two_round_trip_preserves_wires_routes_and_rotation() -> None:
    circuit = Circuit.new(17.0)
    stack = CircuitCommandStack(circuit)
    resistor = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (330.0, 220.0))
    wire = stack.connect(
        TerminalRef("V1", "a"),
        TerminalRef(resistor, "a"),
        ((180.0, 120.0), (180.0, 220.0)),
    )
    junction = stack.split_wire(wire, (180.0, 220.0))
    stack.rotate_component(resistor)

    restored = circuit_from_dict(circuit_to_dict(circuit))

    assert restored.wires == circuit.wires
    assert restored.junctions == circuit.junctions
    assert restored.rotations == circuit.rotations
    assert isinstance(restored.wires[wire].end, JunctionRef)
    assert junction in restored.junctions


def test_starter_loop_round_trip_preserves_its_closed_construction_wiring() -> None:
    circuit = Circuit.starter_loop(12.0)

    restored = circuit_from_dict(circuit_to_dict(circuit))

    assert restored.wires == circuit.wires
    assert restored.junctions == circuit.junctions
    assert restored.open_edge is None
    assert restored.snapshot().source.node_a == restored.snapshot().source.node_b


def test_schema_one_migration_preserves_parallel_topology() -> None:
    payload = {
        "schema_version": 1,
        "source": {"id": "V1", "node_a": "n_pos", "node_b": "n_neg", "voltage": 9.0},
        "components": [
            {"id": "R1", "kind": "resistor", "node_a": "n_pos", "node_b": "n_neg", "value": 100.0},
            {"id": "R2", "kind": "resistor", "node_a": "n_pos", "node_b": "n_neg", "value": 200.0},
        ],
        "nodes": ["n_neg", "n_pos"],
        "positions": {"R1": [260.0, 180.0], "R2": [260.0, 300.0]},
        "settings": {"duration": 0.1, "samples": 100, "method": "trapezoidal"},
        "open_edge": None,
    }

    restored = circuit_from_dict(payload)
    snapshot = restored.snapshot()
    components = {component.id: component for component in snapshot.components}

    assert components["R1"].endpoints == components["R2"].endpoints
    assert snapshot.source.endpoints == components["R1"].endpoints
    assert circuit_to_dict(restored)["schema_version"] == 2
