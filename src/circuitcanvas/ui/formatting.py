"""Human-readable SI formatting for values shown on screen (no Qt dependency)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal

_PREFIXES = (
    (1e9, "G"),
    (1e6, "M"),
    (1e3, "k"),
    (1.0, ""),
    (1e-3, "m"),
    (1e-6, "μ"),
    (1e-9, "n"),
    (1e-12, "p"),
)

BASE_UNITS = {
    "resistor": "Ω",
    "capacitor": "F",
    "inductor": "H",
}


def format_si(value: float, unit: str, *, digits: int = 4, zero_below: float = 1e-12) -> str:
    """Format ``value`` with an engineering prefix, e.g. ``0.0047e-6, "F"`` -> ``"4.7 nF"``.

    Values smaller in magnitude than ``zero_below`` are shown as zero so that
    floating-point residue such as ``3e-17 V`` does not look like a measurement.
    """
    if not math.isfinite(value):
        return f"{value} {unit}"
    if abs(value) < zero_below:
        return f"0 {unit}"
    # Round first so 999.96 becomes "1 k" instead of "1000".
    rounded = float(f"{value:.{digits}g}")
    magnitude = abs(rounded)
    factor, prefix = next(
        ((factor, prefix) for factor, prefix in _PREFIXES if magnitude >= factor),
        _PREFIXES[-1],
    )
    return f"{rounded / factor:.{digits}g} {prefix}{unit}"


def format_component_value(kind: str, value: float) -> str:
    return format_si(value, BASE_UNITS[kind], zero_below=0.0)


# Decimal exponents, so "10u" is exactly 1e-05 rather than 9.999999999999999e-06.
_INPUT_PREFIXES = {
    "": 0,
    "p": -12,
    "n": -9,
    "u": -6,
    "μ": -6,
    "m": -3,
    "k": 3,
    "K": 3,
    "M": 6,
    "meg": 6,
    "Meg": 6,
    "MEG": 6,
    "G": 9,
}
# Longest first so "ohms" is stripped before "ohm".
_UNIT_ALIASES = {
    "Ω": ("ohms", "ohm", "Ω"),
}
_NUMBER = re.compile(r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*)")
# Resistor-code style such as 4k7 (= 4.7k) or 2M2.
_RKM = re.compile(r"(\d+)([pnuμmkKMG])(\d+)\s*(.*)")


@dataclass(frozen=True, slots=True)
class ParsedQuantity:
    value: float
    #: True when the text named a prefix or unit; otherwise the caller decides the scale.
    scaled: bool


def parse_quantity(text: str, unit: str) -> ParsedQuantity:
    """Read engineering input such as ``4.7k``, ``10 uF``, ``4k7``, ``2.2 MΩ`` or ``1e-6``.

    Prefixes are case-sensitive where it matters: ``m`` is milli and ``M`` mega.
    Raises ValueError for text that is not a finite number with an optional
    prefix and unit.
    """
    cleaned = text.strip().replace("µ", "μ").replace("Ω", "Ω")
    match = _RKM.fullmatch(cleaned)
    if match is not None:
        number = Decimal(f"{match[1]}.{match[3]}")
        suffix = match[2] + match[4]
    else:
        match = _NUMBER.fullmatch(cleaned)
        if match is None:
            raise ValueError(f"Not a number: {text!r}")
        number = Decimal(match[1])
        suffix = match[2]
    suffix = suffix.replace(" ", "")
    has_unit = False
    for alias in _UNIT_ALIASES.get(unit, (unit,)):
        if len(suffix) >= len(alias) and suffix.lower().endswith(alias.lower()):
            suffix = suffix[: len(suffix) - len(alias)]
            has_unit = True
            break
    if suffix not in _INPUT_PREFIXES:
        raise ValueError(f"Unknown unit prefix in {text!r}")
    value = float(number.scaleb(_INPUT_PREFIXES[suffix]))
    if not math.isfinite(value):
        raise ValueError(f"Not a finite number: {text!r}")
    return ParsedQuantity(value, bool(suffix) or has_unit)
