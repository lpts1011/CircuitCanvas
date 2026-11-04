import math

import pytest

from circuitcanvas.domain.circuit import Circuit, SimulationSettings
from circuitcanvas.domain.components import Capacitor, ComponentKind, Inductor, Resistor


def test_new_circuit_contains_source_and_open_drop_target() -> None:
    circuit = Circuit.new(12.0)

    assert circuit.source.voltage == 12.0
    assert circuit.components == {}
    assert circuit.entry_nodes == ("n_pos", "n_neg")
    assert circuit.open_edge == "w_main"


@pytest.mark.parametrize("value", [0.0, -1.0, math.inf, math.nan])
def test_component_values_must_be_positive_and_finite(value: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        Resistor(id="R1", node_a="a", node_b="b", resistance=value)


def test_component_kind_and_value_are_exposed_consistently() -> None:
    capacitor = Capacitor("C1", "a", "b", 47e-6)
    inductor = Inductor("L1", "b", "c", 22e-3)

    assert capacitor.kind is ComponentKind.CAPACITOR
    assert capacitor.value == pytest.approx(47e-6)
    assert inductor.kind is ComponentKind.INDUCTOR
    assert inductor.endpoints == ("b", "c")


def test_snapshot_is_detached_from_later_circuit_changes() -> None:
    circuit = Circuit.new(9.0)
    circuit.add_component(Resistor("R1", "n_pos", "n_neg", 100.0))
    snapshot = circuit.snapshot()
    circuit.remove_component("R1")

    assert snapshot.components[0].id == "R1"
    assert snapshot.settings == SimulationSettings(auto_duration=True)
    assert circuit.components == {}
