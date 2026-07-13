"""Physical wiring objects kept separate from electrical solver nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type Point = tuple[float, float]


@dataclass(frozen=True, slots=True, order=True)
class TerminalRef:
    owner_id: str
    terminal: Literal["a", "b"]

    @property
    def key(self) -> str:
        return f"terminal:{self.owner_id}:{self.terminal}"


@dataclass(frozen=True, slots=True, order=True)
class JunctionRef:
    junction_id: str

    @property
    def key(self) -> str:
        return f"junction:{self.junction_id}"


type EndpointRef = TerminalRef | JunctionRef


@dataclass(frozen=True, slots=True)
class Junction:
    id: str
    position: Point


@dataclass(frozen=True, slots=True)
class Wire:
    id: str
    start: EndpointRef
    end: EndpointRef
    route: tuple[Point, ...] = ()
