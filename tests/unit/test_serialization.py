import json

import pytest

from circuitcanvas.commands.circuit_commands import add_parallel, insert_series
from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import ComponentKind
from circuitcanvas.domain.serialization import (
    CircuitFileError,
    circuit_from_dict,
    circuit_to_dict,
    load_circuit,
    save_circuit,
)


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
    with pytest.raises(CircuitFileError, match="version 99.*version 1"):
        circuit_from_dict({"schema_version": 99})


def test_serialized_payload_does_not_include_computed_results() -> None:
    payload = circuit_to_dict(Circuit.new())

    assert payload["schema_version"] == 1
    assert "results" not in json.dumps(payload).lower()
