"""Choose a simulation time span that shows a circuit's whole transient response."""

from __future__ import annotations

import math

import numpy as np
from scipy.linalg import LinAlgError, eigvals  # type: ignore[import-untyped]

from .mna import MNASystem

#: Multiples of the slowest time constant shown; e^-5 ≈ 0.7 % of the step remains.
SETTLING_TIME_CONSTANTS = 5.0
#: Periods shown for a lossless oscillation, which never settles.
UNDAMPED_PERIODS = 5.0
MIN_SPAN_S = 1e-9
MAX_SPAN_S = 1e5

_NICE_MANTISSAS = (1.0, 2.0, 2.5, 5.0, 10.0)


def natural_frequencies(system: MNASystem) -> np.ndarray:
    """Finite natural frequencies λ of ``C x' + G x = 0`` (modes ``x = v·e^{λt}``)."""
    if system.c.size == 0 or not np.any(system.c):
        return np.array([], dtype=complex)
    try:
        alpha_beta = eigvals(system.g, -system.c, homogeneous_eigvals=True)
    except (LinAlgError, ValueError):
        return np.array([], dtype=complex)
    alpha, beta = alpha_beta
    scale = max(1.0, float(np.max(np.abs(alpha))))
    finite = np.abs(beta) > 1e-12 * scale
    return np.asarray(alpha[finite] / beta[finite], dtype=complex)


def nice_ceil(value: float) -> float:
    """Round up to 1, 2, 2.5 or 5 × 10^n so plot axes get tidy tick labels."""
    exponent = math.floor(math.log10(value))
    base = 10.0**exponent
    for mantissa in _NICE_MANTISSAS:
        candidate = mantissa * base
        if candidate >= value * (1 - 1e-9):
            return candidate
    return 10.0 * base


def estimate_time_span(system: MNASystem) -> float | None:
    """Return a span covering the slowest dynamics, or None for a circuit without any.

    A purely resistive circuit reaches its final state instantly, so it has no
    natural time scale and the caller keeps its configured span.
    """
    frequencies = natural_frequencies(system)
    if frequencies.size == 0:
        return None
    magnitudes = np.abs(frequencies)
    reference = max(1.0, float(np.max(magnitudes)))
    decay = -frequencies.real
    decaying = decay > 1e-9 * reference
    oscillating = np.abs(frequencies.imag) > 1e-9 * reference

    span = 0.0
    if np.any(decaying):
        span = SETTLING_TIME_CONSTANTS / float(np.min(decay[decaying]))
    undamped = oscillating & ~decaying
    if np.any(undamped):
        period = 2.0 * math.pi / float(np.min(np.abs(frequencies.imag[undamped])))
        span = max(span, UNDAMPED_PERIODS * period)
    if span <= 0.0 or not math.isfinite(span):
        return None
    return nice_ceil(min(MAX_SPAN_S, max(MIN_SPAN_S, span)))
