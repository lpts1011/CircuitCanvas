"""Human-readable SI formatting for values shown on screen (no Qt dependency)."""

from __future__ import annotations

import math

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
