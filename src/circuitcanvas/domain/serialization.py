"""Versioned JSON persistence for editable circuits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .circuit import Circuit, SimulationSettings
from .components import ComponentKind, VoltageSource, make_component

SCHEMA_VERSION = 1


class CircuitFileError(ValueError):
    """A saved file is unsupported or malformed."""


def circuit_to_dict(circuit: Circuit) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "id": circuit.source.id,
            "node_a": circuit.source.node_a,
            "node_b": circuit.source.node_b,
            "voltage": circuit.source.voltage,
        },
        "components": [
            {
                "id": component.id,
                "kind": component.kind.value,
                "node_a": component.node_a,
                "node_b": component.node_b,
                "value": component.value,
                "rotation": component.rotation,
            }
            for component in circuit.components.values()
        ],
        "nodes": sorted(circuit.nodes),
        "positions": {key: list(value) for key, value in circuit.positions.items()},
        "settings": {
            "duration": circuit.settings.duration,
            "samples": circuit.settings.samples,
            "method": circuit.settings.method,
        },
        "open_edge": circuit.open_edge,
    }


def circuit_from_dict(payload: Mapping[str, Any]) -> Circuit:
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise CircuitFileError(
            f"Circuit file uses schema version {version}; this app supports version {SCHEMA_VERSION}."
        )
    try:
        source_data = payload["source"]
        settings_data = payload["settings"]
        source = VoltageSource(
            str(source_data["id"]),
            str(source_data["node_a"]),
            str(source_data["node_b"]),
            float(source_data["voltage"]),
        )
        circuit = Circuit(
            source=source,
            nodes={str(node) for node in payload["nodes"]},
            settings=SimulationSettings(
                duration=float(settings_data["duration"]),
                samples=int(settings_data["samples"]),
                method=str(settings_data["method"]),
            ),
            open_edge=(str(payload["open_edge"]) if payload.get("open_edge") else None),
        )
        for data in payload["components"]:
            component = make_component(
                ComponentKind(str(data["kind"])),
                str(data["id"]),
                str(data["node_a"]),
                str(data["node_b"]),
                float(data["value"]),
            )
            circuit.add_component(component)
            prefix = component.id[:1]
            suffix = component.id[1:]
            if suffix.isdigit():
                circuit._id_counters[prefix] = max(
                    circuit._id_counters.get(prefix, 0), int(suffix)
                )
        circuit.positions = {
            str(key): (float(value[0]), float(value[1]))
            for key, value in payload.get("positions", {}).items()
        }
        circuit.revision = 0
        return circuit
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, CircuitFileError):
            raise
        raise CircuitFileError(f"Malformed circuit file: {exc}") from exc


def save_circuit(path: str | Path, circuit: Circuit) -> None:
    Path(path).write_text(
        json.dumps(circuit_to_dict(circuit), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_circuit(path: str | Path) -> Circuit:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CircuitFileError(f"Could not read circuit file: {exc}") from exc
    if not isinstance(payload, dict):
        raise CircuitFileError("Circuit file root must be a JSON object")
    return circuit_from_dict(payload)
