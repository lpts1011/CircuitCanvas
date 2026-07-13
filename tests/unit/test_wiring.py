from circuitcanvas.domain.circuit import Circuit
from circuitcanvas.domain.components import Resistor
from circuitcanvas.domain.netlist import derive_connectivity
from circuitcanvas.domain.wiring import Junction, JunctionRef, TerminalRef, Wire


def test_connected_terminals_share_a_derived_node() -> None:
    circuit = Circuit.new()
    circuit.add_component(Resistor("R1", "unused-a", "unused-b", 100.0))
    circuit.wires["W1"] = Wire("W1", TerminalRef("V1", "a"), TerminalRef("R1", "a"))

    snapshot = circuit.snapshot()

    assert snapshot.source.node_a == snapshot.components[0].node_a
    assert snapshot.source.node_b != snapshot.components[0].node_b
    assert snapshot.wires[0].id == "W1"


def test_deleting_bridge_wire_splits_a_net() -> None:
    circuit = Circuit.new()
    circuit.add_component(Resistor("R1", "x", "y", 100.0))
    circuit.add_component(Resistor("R2", "p", "q", 200.0))
    circuit.junctions["J1"] = Junction("J1", (300.0, 200.0))
    circuit.wires["W1"] = Wire("W1", TerminalRef("R1", "b"), JunctionRef("J1"))
    circuit.wires["W2"] = Wire("W2", JunctionRef("J1"), TerminalRef("R2", "a"))

    before = derive_connectivity(circuit)
    del circuit.wires["W2"]
    after = derive_connectivity(circuit)

    assert before.node_for(TerminalRef("R1", "b")) == before.node_for(TerminalRef("R2", "a"))
    assert after.node_for(TerminalRef("R1", "b")) != after.node_for(TerminalRef("R2", "a"))


def test_crossing_wire_routes_do_not_create_connectivity() -> None:
    circuit = Circuit.new()
    circuit.add_component(Resistor("R1", "x", "y", 100.0))
    circuit.add_component(Resistor("R2", "p", "q", 100.0))
    circuit.wires["W1"] = Wire(
        "W1", TerminalRef("V1", "a"), TerminalRef("R1", "a"), ((300.0, 200.0),)
    )
    circuit.wires["W2"] = Wire(
        "W2", TerminalRef("V1", "b"), TerminalRef("R2", "a"), ((300.0, 200.0),)
    )

    connectivity = derive_connectivity(circuit)

    assert connectivity.node_for(TerminalRef("R1", "a")) != connectivity.node_for(
        TerminalRef("R2", "a")
    )
