"""Typed two-terminal electrical components."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum


class ComponentKind(StrEnum):
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"


def _positive_finite(value: float, quantity: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{quantity} must be a positive finite value")


@dataclass(frozen=True, slots=True)
class VoltageSource:
    id: str
    node_a: str
    node_b: str
    voltage: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.voltage) or self.voltage <= 0:
            raise ValueError("Voltage must be a positive finite value")

    @property
    def endpoints(self) -> tuple[str, str]:
        return self.node_a, self.node_b


@dataclass(frozen=True, slots=True)
class Resistor:
    id: str
    node_a: str
    node_b: str
    resistance: float
    rotation: int = 0

    def __post_init__(self) -> None:
        _positive_finite(self.resistance, "Resistance")

    @property
    def kind(self) -> ComponentKind:
        return ComponentKind.RESISTOR

    @property
    def value(self) -> float:
        return self.resistance

    @property
    def endpoints(self) -> tuple[str, str]:
        return self.node_a, self.node_b

    def with_endpoints(self, node_a: str, node_b: str) -> Resistor:
        return replace(self, node_a=node_a, node_b=node_b)


@dataclass(frozen=True, slots=True)
class Capacitor:
    id: str
    node_a: str
    node_b: str
    capacitance: float
    rotation: int = 0

    def __post_init__(self) -> None:
        _positive_finite(self.capacitance, "Capacitance")

    @property
    def kind(self) -> ComponentKind:
        return ComponentKind.CAPACITOR

    @property
    def value(self) -> float:
        return self.capacitance

    @property
    def endpoints(self) -> tuple[str, str]:
        return self.node_a, self.node_b

    def with_endpoints(self, node_a: str, node_b: str) -> Capacitor:
        return replace(self, node_a=node_a, node_b=node_b)


@dataclass(frozen=True, slots=True)
class Inductor:
    id: str
    node_a: str
    node_b: str
    inductance: float
    rotation: int = 0

    def __post_init__(self) -> None:
        _positive_finite(self.inductance, "Inductance")

    @property
    def kind(self) -> ComponentKind:
        return ComponentKind.INDUCTOR

    @property
    def value(self) -> float:
        return self.inductance

    @property
    def endpoints(self) -> tuple[str, str]:
        return self.node_a, self.node_b

    def with_endpoints(self, node_a: str, node_b: str) -> Inductor:
        return replace(self, node_a=node_a, node_b=node_b)


type Component = Resistor | Capacitor | Inductor


def make_component(
    kind: ComponentKind, component_id: str, node_a: str, node_b: str, value: float
) -> Component:
    if kind is ComponentKind.RESISTOR:
        return Resistor(component_id, node_a, node_b, value)
    if kind is ComponentKind.CAPACITOR:
        return Capacitor(component_id, node_a, node_b, value)
    return Inductor(component_id, node_a, node_b, value)


def replace_value(component: Component, value: float) -> Component:
    if isinstance(component, Resistor):
        return replace(component, resistance=value)
    if isinstance(component, Capacitor):
        return replace(component, capacitance=value)
    return replace(component, inductance=value)
