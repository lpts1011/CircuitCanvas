"""Versioned JSON persistence for editable circuits."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .circuit import Circuit, SimulationSettings
from .components import ComponentKind, VoltageSource, make_component
from .wiring import EndpointRef, Junction, JunctionRef, TerminalRef, Wire

SCHEMA_VERSION = 2


class CircuitFileError(ValueError):
    """A saved file is unsupported or malformed."""


def _endpoint_to_dict(endpoint: EndpointRef) -> dict[str, str]:
    if isinstance(endpoint, TerminalRef):
        return {
            "type": "terminal",
            "owner": endpoint.owner_id,
            "terminal": endpoint.terminal,
        }
    return {"type": "junction", "id": endpoint.junction_id}


def _endpoint_from_dict(payload: Mapping[str, Any]) -> EndpointRef:
    if payload.get("type") == "terminal":
        terminal = str(payload["terminal"])
        if terminal not in {"a", "b"}:
            raise ValueError(f"Unknown terminal: {terminal}")
        return TerminalRef(str(payload["owner"]), terminal)  # type: ignore[arg-type]
    if payload.get("type") == "junction":
        return JunctionRef(str(payload["id"]))
    raise ValueError(f"Unknown endpoint type: {payload.get('type')}")


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
        "rotations": dict(circuit.rotations),
        "junctions": [
            {"id": junction.id, "position": list(junction.position)}
            for junction in circuit.junctions.values()
        ],
        "wires": [
            {
                "id": wire.id,
                "start": _endpoint_to_dict(wire.start),
                "end": _endpoint_to_dict(wire.end),
                "route": [list(point) for point in wire.route],
            }
            for wire in circuit.wires.values()
        ],
        "settings": {
            "duration": circuit.settings.duration,
            "samples": circuit.settings.samples,
            "method": circuit.settings.method,
        },
        "open_edge": circuit.open_edge,
    }


def circuit_from_dict(payload: Mapping[str, Any]) -> Circuit:
    version = payload.get("schema_version")
    if version not in {1, SCHEMA_VERSION}:
        raise CircuitFileError(
            f"Circuit file uses schema version {version}; "
            f"this app supports version {SCHEMA_VERSION}."
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
                circuit._id_counters[prefix] = max(circuit._id_counters.get(prefix, 0), int(suffix))
        circuit.positions = {
            str(key): (float(value[0]), float(value[1]))
            for key, value in payload.get("positions", {}).items()
        }
        circuit.rotations = {
            str(key): int(value) % 360 for key, value in payload.get("rotations", {}).items()
        }
        if version == SCHEMA_VERSION:
            for data in payload.get("junctions", []):
                position = data["position"]
                junction = Junction(str(data["id"]), (float(position[0]), float(position[1])))
                circuit.junctions[junction.id] = junction
            for data in payload.get("wires", []):
                route = tuple((float(point[0]), float(point[1])) for point in data.get("route", []))
                wire = Wire(
                    str(data["id"]),
                    _endpoint_from_dict(data["start"]),
                    _endpoint_from_dict(data["end"]),
                    route,
                )
                circuit.wires[wire.id] = wire
        else:
            _synthesize_legacy_wiring(circuit)
        circuit._wire_counter = max(
            (int(wire_id[1:]) for wire_id in circuit.wires if wire_id[1:].isdigit()),
            default=0,
        )
        circuit._junction_counter = max(
            (
                int(junction_id[1:])
                for junction_id in circuit.junctions
                if junction_id[1:].isdigit()
            ),
            default=len(circuit.junctions),
        )
        circuit.revision = 0
        return circuit
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, CircuitFileError):
            raise
        raise CircuitFileError(f"Malformed circuit file: {exc}") from exc


def _synthesize_legacy_wiring(circuit: Circuit) -> None:
    node_junctions: dict[str, JunctionRef] = {}
    for index, node in enumerate(sorted(circuit.nodes), start=1):
        junction_id = f"J{index}"
        circuit.junctions[junction_id] = Junction(junction_id, (120.0 + index * 36.0, 420.0))
        node_junctions[node] = JunctionRef(junction_id)

    terminal_nodes: list[tuple[TerminalRef, str]] = [
        (TerminalRef(circuit.source.id, "a"), circuit.source.node_a),
        (TerminalRef(circuit.source.id, "b"), circuit.source.node_b),
    ]
    for component in circuit.components.values():
        terminal_nodes.extend(
            (
                (TerminalRef(component.id, "a"), component.node_a),
                (TerminalRef(component.id, "b"), component.node_b),
            )
        )
    for terminal, node in terminal_nodes:
        wire_id = circuit.next_wire_id()
        circuit.wires[wire_id] = Wire(wire_id, terminal, node_junctions[node])


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
