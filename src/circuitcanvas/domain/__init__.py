"""Electrical domain objects without GUI dependencies."""

from .circuit import Circuit, CircuitSnapshot, SimulationSettings
from .components import Capacitor, ComponentKind, Inductor, Resistor, VoltageSource
from .wiring import Junction, JunctionRef, TerminalRef, Wire

__all__ = [
    "Capacitor",
    "Circuit",
    "CircuitSnapshot",
    "ComponentKind",
    "Inductor",
    "Resistor",
    "SimulationSettings",
    "VoltageSource",
    "Junction",
    "JunctionRef",
    "TerminalRef",
    "Wire",
]
