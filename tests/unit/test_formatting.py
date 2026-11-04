import math

import pytest

from circuitcanvas.ui.formatting import format_component_value, format_si


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (10_000.0, "Ω", "10 kΩ"),
        (2.2e6, "Ω", "2.2 MΩ"),
        (100.0, "Ω", "100 Ω"),
        (4.7e-9, "F", "4.7 nF"),
        (47e-6, "F", "47 μF"),
        (22e-3, "H", "22 mH"),
        (11.881, "V", "11.88 V"),
        (0.0011881, "A", "1.188 mA"),
        (-0.0011881, "A", "-1.188 mA"),
        (999.96, "Ω", "1 kΩ"),
        (6.969e-11, "A", "69.69 pA"),
        (3e-17, "V", "0 V"),
        (-0.0, "V", "0 V"),
        (12.0, "V", "12 V"),
    ],
)
def test_format_si_uses_engineering_prefixes(value: float, unit: str, expected: str) -> None:
    assert format_si(value, unit) == expected


def test_format_si_handles_non_finite_values() -> None:
    assert format_si(math.inf, "A") == "inf A"


def test_component_values_use_their_base_unit() -> None:
    assert format_component_value("resistor", 4700.0) == "4.7 kΩ"
    assert format_component_value("capacitor", 1e-3) == "1 mF"
    assert format_component_value("inductor", 1.5) == "1.5 H"
