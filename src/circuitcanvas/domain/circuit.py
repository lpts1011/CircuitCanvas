"""Circuit ownership, settings, and immutable solver snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .components import Component, VoltageSource
from .wiring import Junction, Wire


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    duration: float = 0.1
    samples: int = 1000
    method: str = "trapezoidal"

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError("Simulation duration must be positive")
        if self.samples < 2:
            raise ValueError("Simulation samples must be at least 2")
        if self.method not in {"trapezoidal", "backward-euler"}:
            raise ValueError("Unknown transient integration method")


@dataclass(frozen=True, slots=True)
class CircuitSnapshot:
    source: VoltageSource
    components: tuple[Component, ...]
    nodes: tuple[str, ...]
    settings: SimulationSettings
    revision: int
    positions: tuple[tuple[str, float, float], ...] = ()
    junctions: tuple[Junction, ...] = ()
    wires: tuple[Wire, ...] = ()
    rotations: tuple[tuple[str, int], ...] = ()


@dataclass(slots=True)
class Circuit:
    source: VoltageSource
    components: dict[str, Component] = field(default_factory=dict)
    nodes: set[str] = field(default_factory=lambda: {"n_pos", "n_neg"})
    settings: SimulationSettings = field(default_factory=SimulationSettings)
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    rotations: dict[str, int] = field(default_factory=dict)
    junctions: dict[str, Junction] = field(default_factory=dict)
    wires: dict[str, Wire] = field(default_factory=dict)
    revision: int = 0
    open_edge: str | None = "w_main"
    _id_counters: dict[str, int] = field(default_factory=dict)

    @classmethod
    def new(cls, voltage: float = 12.0) -> Circuit:
        return cls(source=VoltageSource("V1", "n_pos", "n_neg", voltage))

    @property
    def entry_nodes(self) -> tuple[str, str]:
        return self.source.endpoints

    def add_component(self, component: Component) -> None:
        if component.id in self.components:
            raise ValueError(f"Duplicate component ID: {component.id}")
        self.components[component.id] = component
        self.nodes.update(component.endpoints)
        self.revision += 1

    def replace_component(self, component: Component) -> None:
        if component.id not in self.components:
            raise KeyError(component.id)
        self.components[component.id] = component
        self.nodes.update(component.endpoints)
        self.revision += 1

    def remove_component(self, component_id: str) -> Component:
        component = self.components.pop(component_id)
        self.positions.pop(component_id, None)
        self.revision += 1
        return component

    def next_id(self, prefix: str) -> str:
        count = self._id_counters.get(prefix, 0) + 1
        while f"{prefix}{count}" in self.components:
            count += 1
        self._id_counters[prefix] = count
        return f"{prefix}{count}"

    def next_node_id(self) -> str:
        index = 1
        while f"n{index}" in self.nodes:
            index += 1
        node = f"n{index}"
        self.nodes.add(node)
        return node

    def edge_after(self, component_id: str) -> str:
        if component_id not in self.components:
            raise KeyError(component_id)
        return component_id

    def snapshot(self) -> CircuitSnapshot:
        source = self.source
        components = tuple(self.components.values())
        nodes = tuple(sorted(self.nodes))
        if self.wires or self.junctions:
            from .netlist import derive_connectivity
            from .wiring import TerminalRef

            connectivity = derive_connectivity(self)
            source = replace(
                self.source,
                node_a=connectivity.node_for(TerminalRef(self.source.id, "a")),
                node_b=connectivity.node_for(TerminalRef(self.source.id, "b")),
            )
            components = tuple(
                component.with_endpoints(
                    connectivity.node_for(TerminalRef(component.id, "a")),
                    connectivity.node_for(TerminalRef(component.id, "b")),
                )
                for component in self.components.values()
            )
            nodes = tuple(
                sorted(
                    set(connectivity.terminal_nodes.values())
                    | set(connectivity.junction_nodes.values())
                )
            )
        return CircuitSnapshot(
            source=source,
            components=components,
            nodes=nodes,
            settings=self.settings,
            revision=self.revision,
            positions=tuple((key, *value) for key, value in sorted(self.positions.items())),
            junctions=tuple(self.junctions[key] for key in sorted(self.junctions)),
            wires=tuple(self.wires[key] for key in sorted(self.wires)),
            rotations=tuple(sorted(self.rotations.items())),
        )
