# Free Wiring and Kirchhoff Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add arbitrary terminal-to-terminal wiring, editable orthogonal routes, generated Kirchhoff equations, and current-direction animation driven by the solved circuit.

**Architecture:** Store physical terminals, junctions, and wires as an explicit graph, then derive solver nodes with union-find for every immutable snapshot. Generate KCL/KVL reports and ideal-wire segment flows from the same snapshot and simulation result so the drawing, equations, and animation cannot diverge.

**Tech Stack:** Python 3.12+, PySide6 6.8–6.10, NumPy, SciPy, PyQtGraph, pytest, pytest-qt, Ruff, mypy, PyInstaller

## Global Constraints

- Preserve Python 3.12+ and `PySide6>=6.8,<6.11` compatibility.
- Keep all domain, connectivity, equation, and flow code independent of PySide6.
- Treat the explicit electrical graph as authoritative; screen proximity alone never connects objects.
- Keep MNA as the numerical solver and use one shared sign convention for equations, labels, plots, and arrows.
- Save new circuits with schema version 2 and migrate schema version 1 without changing electrical behavior.
- Never animate guessed current when validation or numerical residual checks fail.
- Maintain strict mypy, Ruff, existing exports, background revision safety, and macOS packaging.

---

## File structure

New focused modules:

- `src/circuitcanvas/domain/wiring.py`: terminal, junction, wire, and connectivity value objects.
- `src/circuitcanvas/domain/netlist.py`: union-find connectivity derivation and snapshot endpoint replacement.
- `src/circuitcanvas/solver/equations.py`: KCL, KVL, component-law, and descriptor equation reports.
- `src/circuitcanvas/solver/wire_flow.py`: minimum-norm ideal-wire segment flow reconstruction.
- `src/circuitcanvas/ui/wire_items.py`: terminal, junction, wire, route-handle, and arrow graphics.
- `src/circuitcanvas/ui/equation_panel.py`: ordinary/differential equation browser and residual display.
- `src/circuitcanvas/ui/playback.py`: time playback state and 60 FPS animation timer.

Existing modules retain their current roles. `circuit_scene.py` coordinates graphics and commands; it does not perform electrical math.

---

### Task 1: Wiring value objects and derived connectivity

**Files:**
- Create: `src/circuitcanvas/domain/wiring.py`
- Create: `src/circuitcanvas/domain/netlist.py`
- Modify: `src/circuitcanvas/domain/circuit.py`
- Modify: `src/circuitcanvas/domain/__init__.py`
- Test: `tests/unit/test_wiring.py`

**Interfaces:**
- Produces: `TerminalRef(owner_id: str, terminal: str)`, `Junction`, `Wire`, `Connectivity`, `derive_connectivity(circuit)`, and wiring fields on `CircuitSnapshot`.
- Consumes: existing two-terminal component `with_endpoints()` methods and `VoltageSource`.

- [ ] **Step 1: Write failing connectivity tests**

```python
def test_connected_terminals_share_a_derived_node() -> None:
    circuit = Circuit.new()
    circuit.add_component(Resistor("R1", "unused-a", "unused-b", 100.0))
    circuit.wires["W1"] = Wire(
        "W1", TerminalRef("V1", "a"), TerminalRef("R1", "a")
    )
    snapshot = circuit.snapshot()
    assert snapshot.source.node_a == snapshot.components[0].node_a
    assert snapshot.source.node_b != snapshot.components[0].node_b


def test_deleting_bridge_wire_splits_a_net() -> None:
    circuit = wired_three_terminal_fixture()
    before = derive_connectivity(circuit)
    del circuit.wires["W2"]
    after = derive_connectivity(circuit)
    assert before.node_for(TerminalRef("R1", "b")) == before.node_for(TerminalRef("R2", "a"))
    assert after.node_for(TerminalRef("R1", "b")) != after.node_for(TerminalRef("R2", "a"))
```

- [ ] **Step 2: Run the tests and verify missing wiring types fail**

Run: `python -m pytest tests/unit/test_wiring.py -v`

Expected: collection fails because `circuitcanvas.domain.wiring` does not exist.

- [ ] **Step 3: Implement immutable wiring types**

```python
@dataclass(frozen=True, slots=True, order=True)
class TerminalRef:
    owner_id: str
    terminal: Literal["a", "b"]


@dataclass(frozen=True, slots=True, order=True)
class JunctionRef:
    junction_id: str


type EndpointRef = TerminalRef | JunctionRef
type Point = tuple[float, float]


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
```

- [ ] **Step 4: Implement union-find connectivity and snapshot derivation**

`derive_connectivity()` must include every source/component terminal as a singleton, union the endpoints of every wire, assign deterministic node IDs by sorted member keys, and expose `node_for(ref)`. Update `Circuit.snapshot()` to replace component and source endpoints from this connectivity whenever free wiring is present, while retaining the old endpoint behavior for legacy command-only tests.

```python
@dataclass(frozen=True, slots=True)
class Connectivity:
    terminal_nodes: Mapping[TerminalRef, str]
    junction_nodes: Mapping[JunctionRef, str]

    def node_for(self, ref: EndpointRef) -> str:
        if isinstance(ref, TerminalRef):
            return self.terminal_nodes[ref]
        return self.junction_nodes[ref]
```

- [ ] **Step 5: Run focused and existing domain tests**

Run: `python -m pytest tests/unit/test_wiring.py tests/unit/test_domain.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/circuitcanvas/domain tests/unit/test_wiring.py
git commit -m "feat: model free wiring connectivity"
```

---

### Task 2: Atomic free-wiring commands and history

**Files:**
- Modify: `src/circuitcanvas/commands/circuit_commands.py`
- Modify: `src/circuitcanvas/domain/circuit.py`
- Test: `tests/unit/test_commands.py`

**Interfaces:**
- Consumes: `TerminalRef`, `JunctionRef`, `Junction`, and `Wire` from Task 1.
- Produces: `add_loose_component`, `connect`, `split_wire`, `move_component`, `rotate_component`, `move_junction`, `set_wire_route`, and undoable stack methods with the same names.

- [ ] **Step 1: Add failing command tests**

```python
def test_connect_split_move_and_undo() -> None:
    circuit = Circuit.new()
    stack = CircuitCommandStack(circuit)
    r1 = stack.add_loose_component(ComponentKind.RESISTOR, 100.0, (300.0, 180.0))
    wire = stack.connect(TerminalRef("V1", "a"), TerminalRef(r1, "a"))
    junction = stack.split_wire(wire, (210.0, 180.0))
    stack.move_component(r1, (420.0, 260.0))
    assert circuit.positions[r1] == (420.0, 260.0)
    assert isinstance(circuit.wires[wire].end, JunctionRef)
    assert stack.undo()
    assert circuit.positions[r1] == (300.0, 180.0)
    assert circuit.junctions[junction].position == (210.0, 180.0)
```

- [ ] **Step 2: Verify the new stack methods fail**

Run: `python -m pytest tests/unit/test_commands.py -v`

Expected: FAIL with missing `add_loose_component`.

- [ ] **Step 3: Extend captured state and implement commands**

Capture and restore `junctions`, `wires`, `positions`, `rotations`, and all ID counters. `split_wire` replaces one wire with two wires meeting at a new `JunctionRef`. `delete_component` retains attached wires as dangling junction endpoints so they can be reconnected.

```python
def connect(circuit: Circuit, start: EndpointRef, end: EndpointRef) -> str:
    circuit.assert_endpoint(start)
    circuit.assert_endpoint(end)
    wire_id = circuit.next_wire_id()
    circuit.wires[wire_id] = Wire(wire_id, start, end)
    circuit.touch()
    return wire_id
```

- [ ] **Step 4: Run command and wiring tests**

Run: `python -m pytest tests/unit/test_commands.py tests/unit/test_wiring.py -v`

Expected: all tests pass, including existing series/parallel commands.

- [ ] **Step 5: Commit**

```bash
git add src/circuitcanvas/commands/circuit_commands.py src/circuitcanvas/domain/circuit.py tests/unit/test_commands.py
git commit -m "feat: add undoable free wiring commands"
```

---

### Task 3: Schema version 2 and legacy migration

**Files:**
- Modify: `src/circuitcanvas/domain/serialization.py`
- Modify: `examples/*.circuitcanvas`
- Test: `tests/unit/test_serialization.py`

**Interfaces:**
- Consumes: Task 1 wiring dataclasses.
- Produces: `SCHEMA_VERSION = 2`, version 2 JSON, and `_migrate_v1(payload) -> dict[str, Any]`.

- [ ] **Step 1: Write version 2 round-trip and version 1 migration tests**

```python
def test_schema_two_round_trip_preserves_routes_and_rotation() -> None:
    circuit = free_wired_fixture()
    restored = circuit_from_dict(circuit_to_dict(circuit))
    assert restored.wires == circuit.wires
    assert restored.junctions == circuit.junctions
    assert restored.rotations == circuit.rotations
    assert restored.snapshot().components == circuit.snapshot().components


def test_schema_one_migration_preserves_solver_endpoints() -> None:
    restored = circuit_from_dict(LEGACY_PARALLEL_PAYLOAD)
    assert circuit_to_dict(restored)["schema_version"] == 2
    components = {component.id: component for component in restored.snapshot().components}
    assert components["R1"].endpoints == components["R2"].endpoints
    assert restored.snapshot().source.endpoints == components["R1"].endpoints
```

- [ ] **Step 2: Verify tests fail on schema version 1 implementation**

Run: `python -m pytest tests/unit/test_serialization.py -v`

Expected: FAIL because wiring fields and schema 2 are absent.

- [ ] **Step 3: Implement explicit endpoint JSON and migration**

Serialize endpoint references as `{"type": "terminal", "owner": "R1", "terminal": "a"}` or `{"type": "junction", "id": "J1"}`. Migration creates one junction per old electrical node and one wire from every terminal to its node junction; route points may be empty because they are visual only.

- [ ] **Step 4: Run serialization and example tests**

Run: `python -m pytest tests/unit/test_serialization.py tests/integration/test_examples.py -v`

Expected: all tests pass and every example loads as schema 2 in memory.

- [ ] **Step 5: Commit**

```bash
git add src/circuitcanvas/domain/serialization.py tests/unit/test_serialization.py examples
git commit -m "feat: persist free wiring schema"
```

---

### Task 4: Kirchhoff equation generation

**Files:**
- Create: `src/circuitcanvas/solver/equations.py`
- Modify: `src/circuitcanvas/solver/__init__.py`
- Test: `tests/solver/test_equations.py`

**Interfaces:**
- Consumes: `CircuitSnapshot`, `SimulationResult`, and `MNASystem`.
- Produces: `EquationLine`, `EquationGroup`, `EquationReport`, and `build_equation_report(snapshot, result, time_index)`.

- [ ] **Step 1: Write failing KCL, KVL, and differential-form tests**

Use a 17 V fixture with `R1=100`, `R2=100` in series and `R3=200` across the outer nodes.

```python
def test_parallel_series_fixture_has_independent_kcl_and_kvl() -> None:
    snapshot = parallel_series_fixture().snapshot()
    result = simulate(snapshot)
    report = build_equation_report(snapshot, result, len(result.time) - 1)
    assert len(report.kcl) == len(snapshot.nodes) - 1
    assert len(report.kvl) == 2
    assert max(abs(line.residual) for line in (*report.kcl, *report.kvl)) < 1e-9


def test_differential_report_expands_reactive_laws() -> None:
    snapshot = rlc_fixture().snapshot()
    report = build_equation_report(snapshot, simulate(snapshot), 20)
    assert "C·dv_C1/dt" in report.differential_text
    assert "L·di_L1/dt" in report.differential_text
    assert "C x_dot(t) + G x(t) = b(t)" in report.descriptor_text
```

- [ ] **Step 2: Verify the equation module is missing**

Run: `python -m pytest tests/solver/test_equations.py -v`

Expected: collection fails for missing `circuitcanvas.solver.equations`.

- [ ] **Step 3: Implement immutable equation report types**

```python
@dataclass(frozen=True, slots=True)
class EquationLine:
    id: str
    kind: Literal["kcl", "kvl", "law"]
    symbolic: str
    substituted: str
    result: str
    residual: float
    component_ids: tuple[str, ...]
    node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EquationReport:
    kcl: tuple[EquationLine, ...]
    kvl: tuple[EquationLine, ...]
    laws: tuple[EquationLine, ...]
    differential_text: str
    descriptor_text: str
```

- [ ] **Step 4: Generate KCL and an independent multigraph cycle basis**

Treat electrical nodes as graph vertices and components plus the source as signed edges. Build a spanning forest; each non-tree edge plus the unique tree path produces one fundamental KVL cycle. Parallel components must produce a valid two-edge cycle. Evaluate KCL from signed branch currents and KVL from signed branch voltages at the active sample.

- [ ] **Step 5: Add component laws and descriptor matrix text**

Use the exact MNA assembly to format `G`, `C`, unknown names, and `b`. Show explicit scalar ODE text only for reducible fixtures; otherwise label the system `Differential-algebraic MNA system`.

- [ ] **Step 6: Run equation and solver conservation tests**

Run: `python -m pytest tests/solver/test_equations.py tests/solver/test_conservation.py tests/solver/test_mna.py -v`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/circuitcanvas/solver/equations.py src/circuitcanvas/solver/__init__.py tests/solver/test_equations.py
git commit -m "feat: generate Kirchhoff equation reports"
```

---

### Task 5: Ideal-wire segment current reconstruction

**Files:**
- Create: `src/circuitcanvas/solver/wire_flow.py`
- Modify: `src/circuitcanvas/solver/results.py`
- Test: `tests/solver/test_wire_flow.py`

**Interfaces:**
- Consumes: snapshot wiring, branch currents, and source current.
- Produces: `WireFlowResult(currents, net_residuals)` and `reconstruct_wire_flows(snapshot, result, time_index)`.

- [ ] **Step 1: Write failing split/recombine and sign-reversal tests**

```python
def test_wire_flows_obey_kcl_at_every_junction() -> None:
    snapshot = parallel_series_fixture().snapshot()
    result = simulate(snapshot)
    flows = reconstruct_wire_flows(snapshot, result, len(result.time) - 1)
    assert max(flows.net_residuals.values(), default=0.0) < 1e-9
    assert source_split_currents(flows) == pytest.approx((0.085, 0.085), rel=1e-4)


def test_negative_terminal_current_reverses_wire_flow() -> None:
    flows = reconstruct_wire_flows(reversing_rlc_snapshot, reversing_result, reverse_index)
    assert flows.currents["W_return"] < 0.0
```

- [ ] **Step 2: Verify missing reconstruction fails**

Run: `python -m pytest tests/solver/test_wire_flow.py -v`

Expected: collection fails for missing `wire_flow`.

- [ ] **Step 3: Implement incidence-matrix minimum-norm solve**

For each conductor net, orient wire edges from `start` to `end`, construct incidence matrix `B`, assemble terminal injection vector `q` from component/source currents, and solve `B f = -q` with `scipy.linalg.lstsq(..., lapack_driver="gelsy")`. Record `max(abs(B @ f + q))` per net. Return a read-only mapping from wire ID to signed current.

- [ ] **Step 4: Run flow and conservation tests**

Run: `python -m pytest tests/solver/test_wire_flow.py tests/solver/test_conservation.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/circuitcanvas/solver/wire_flow.py src/circuitcanvas/solver/results.py tests/solver/test_wire_flow.py
git commit -m "feat: reconstruct Kirchhoff-safe wire currents"
```

---

### Task 6: Free component placement, terminals, wires, and route editing

**Files:**
- Create: `src/circuitcanvas/ui/wire_items.py`
- Modify: `src/circuitcanvas/ui/component_items.py`
- Rewrite: `src/circuitcanvas/ui/circuit_scene.py`
- Modify: `src/circuitcanvas/ui/palette.py`
- Test: `tests/gui/test_canvas.py`

**Interfaces:**
- Consumes: Tasks 1–2 domain types and command stack.
- Produces: `TerminalItem`, `JunctionItem`, `WireItem`, free-moving `ComponentItem`, and scene methods `begin_wire`, `complete_wire`, `split_wire_at`, `rotate_selected`, and `insert_component_at`.

- [ ] **Step 1: Replace smart-snap-only GUI tests with free-wiring tests**

```python
def test_palette_drop_keeps_requested_position_and_exposes_two_terminals(qtbot) -> None:
    scene = CircuitScene(Circuit.new())
    component_id = scene.insert_component_at("resistor", QPointF(410, 280))
    item = scene.component_items[component_id]
    assert item.pos() == QPointF(410, 280)
    assert set(item.terminals) == {"a", "b"}


def test_wire_drop_on_existing_wire_creates_visible_junction(qtbot) -> None:
    scene = wired_scene_fixture()
    original = scene.wire_items["W1"]
    junction_id = scene.split_wire_at("W1", original.path().pointAtPercent(0.5))
    assert junction_id in scene.junction_items
    assert len(scene.circuit.wires) == 2


def test_crossing_paths_are_not_connected_without_a_junction(qtbot) -> None:
    scene = crossing_wire_scene_fixture()
    connectivity = derive_connectivity(scene.circuit)
    assert connectivity.node_for(TerminalRef("R1", "a")) != connectivity.node_for(
        TerminalRef("R2", "a")
    )
```

- [ ] **Step 2: Verify old scene cannot satisfy free placement tests**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_canvas.py -v`

Expected: FAIL because `insert_component_at` and terminal items are absent.

- [ ] **Step 3: Implement graphics primitives**

`TerminalItem` emits a drag-start signal and paints orange/blue/green connection states. `WireItem` builds an orthogonal `QPainterPath`, has a wide transparent hit shape, exposes route handles only while selected, and never determines electrical connectivity from coordinates. `JunctionItem` displays a filled dot for degree three or greater.

- [ ] **Step 4: Make components movable and rotatable**

Set `ItemIsMovable`, `ItemIsSelectable`, and `ItemSendsGeometryChanges`. Terminal scene positions update from component rotation. On drag release, commit one `move_component` command; during drag, attached wire paths preview without changing topology.

- [ ] **Step 5: Rewrite scene rebuild and pointer state machine**

Render from saved positions, rotations, junctions, and wires. Wire mode follows `idle -> drawing -> complete/cancel`; dropping on a wire invokes `split_wire`; dropping on empty creates a dangling junction. Keep test helpers as thin wrappers over real commands.

Add Select, Wire, Junction, Rotate, and Delete toolbar actions with shortcuts. Crossing paths remain separate until a real junction command changes the domain graph.

- [ ] **Step 6: Run GUI and export tests**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_canvas.py tests/unit/test_export.py -v`

Expected: all tests pass and PNG export contains the free layout.

- [ ] **Step 7: Commit**

```bash
git add src/circuitcanvas/ui tests/gui/test_canvas.py tests/unit/test_export.py
git commit -m "feat: build free wiring circuit canvas"
```

---

### Task 7: Kirchhoff equation panel and selection highlighting

**Files:**
- Create: `src/circuitcanvas/ui/equation_panel.py`
- Modify: `src/circuitcanvas/ui/main_window.py`
- Modify: `src/circuitcanvas/ui/circuit_scene.py`
- Test: `tests/gui/test_equation_panel.py`
- Modify: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: `EquationReport` and active simulation time index.
- Produces: `EquationPanel.set_report(report)`, `EquationPanel.set_mode(mode)`, `equation_selected` signal, and scene highlighting by node/component IDs.

- [ ] **Step 1: Write failing panel mode and highlight tests**

```python
def test_panel_switches_between_ordinary_and_differential(qtbot) -> None:
    panel = EquationPanel()
    qtbot.addWidget(panel)
    panel.set_report(sample_equation_report())
    assert "KCL" in panel.visible_text()
    panel.differential_button.click()
    assert "C x_dot(t) + G x(t) = b(t)" in panel.visible_text()


def test_selecting_equation_highlights_its_circuit_objects(qtbot) -> None:
    window = wired_main_window(qtbot)
    window.equations.select_equation("KVL1")
    assert window.scene.highlighted_components == {"V1", "R1", "R2", "R3"}
```

- [ ] **Step 2: Verify the panel is missing**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_equation_panel.py -v`

Expected: collection fails for missing `EquationPanel`.

- [ ] **Step 3: Implement the ordinary/differential panel**

Use a `QButtonGroup` toggle, `QTreeWidget` for KCL/KVL/laws, and a read-only `QPlainTextEdit` for symbolic, substituted, result, and residual lines. A green check requires `abs(residual) <= 1e-9`; otherwise use red text.

- [ ] **Step 4: Integrate report updates and bidirectional highlighting**

Replace the fixed sidebar with a resizable tab widget containing Components, Inspector, and Kirchhoff Equations. Build a new report in `_apply_result` and `_time_index_changed`. Equation selection passes IDs to the scene; component selection tells the panel to reveal matching equations. Diagnostics clear numeric substitutions but retain structural equation groups when possible.

- [ ] **Step 5: Run equation-panel and main-window tests**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_equation_panel.py tests/gui/test_main_window.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/circuitcanvas/ui/equation_panel.py src/circuitcanvas/ui/main_window.py src/circuitcanvas/ui/circuit_scene.py tests/gui
git commit -m "feat: show interactive Kirchhoff equations"
```

---

### Task 8: Blue current arrows and transient playback

**Files:**
- Create: `src/circuitcanvas/ui/playback.py`
- Modify: `src/circuitcanvas/ui/wire_items.py`
- Modify: `src/circuitcanvas/ui/circuit_scene.py`
- Modify: `src/circuitcanvas/ui/analysis_panel.py`
- Modify: `src/circuitcanvas/ui/main_window.py`
- Test: `tests/gui/test_current_animation.py`

**Interfaces:**
- Consumes: `WireFlowResult` at the active time sample.
- Produces: `PlaybackController`, `WireItem.set_current(current)`, arrow phase updates, play/pause, speed, and time-index signals.

- [ ] **Step 1: Write failing direction, zero-current, and stale-result tests**

```python
def test_wire_arrow_direction_follows_signed_current(qtbot) -> None:
    item = WireItem(sample_wire())
    item.set_current(0.25)
    forward = item.arrow_positions()
    item.advance_phase(0.1)
    assert item.arrow_positions()[0] > forward[0]
    item.set_current(-0.25)
    reverse = item.arrow_positions()
    item.advance_phase(0.1)
    assert item.arrow_positions()[0] < reverse[0]


def test_zero_or_stale_current_hides_arrows(qtbot) -> None:
    item = WireItem(sample_wire())
    item.set_current(1e-15)
    assert not item.arrows_visible
    item.set_stale(True)
    assert not item.arrows_visible
```

- [ ] **Step 2: Verify animation APIs fail**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_current_animation.py -v`

Expected: FAIL because current animation methods are absent.

- [ ] **Step 3: Paint blue arrow particles along each wire path**

Use normalized phase in `[0, 1)`, path length, and `QPainterPath.pointAtPercent`. Draw small filled blue triangular arrows tangent to the path. Map speed with `clamp(0.15 + 0.45 * log10(1 + abs(i)/1e-6), 0.15, 2.5)` and use a `1e-12 A` stop threshold.

- [ ] **Step 4: Implement one shared 60 FPS playback timer**

`PlaybackController` owns a `QTimer` with 16 ms interval, advances the plot time index according to playback speed, and emits animation delta separately from time-index changes. No wire owns a timer.

- [ ] **Step 5: Reconstruct and apply flows at every time update**

The main window calls `reconstruct_wire_flows`; if any net residual exceeds `1e-9 A`, it marks those wires stale and shows a Kirchhoff warning. Valid flows call `scene.set_wire_currents(flows.currents)`.

- [ ] **Step 6: Run animation, analysis, and controller tests**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_current_animation.py tests/gui/test_analysis_panel.py tests/integration/test_controller.py -v`

Expected: all tests pass without launching additional simulations per animation frame.

- [ ] **Step 7: Commit**

```bash
git add src/circuitcanvas/ui tests/gui/test_current_animation.py
git commit -m "feat: animate Kirchhoff-safe wire currents"
```

---

### Task 9: Topology validation and required integration circuit

**Files:**
- Modify: `src/circuitcanvas/solver/validation.py`
- Create: `tests/integration/test_free_wiring_kirchhoff.py`
- Modify: `tests/solver/test_validation.py`
- Add: `examples/parallel_series_17v.circuitcanvas`

**Interfaces:**
- Consumes: derived connectivity, wiring objects, equation reports, and wire flows.
- Produces: diagnostics for dangling terminals/wires, floating nets, battery shorts, inconsistent references, and excessive Kirchhoff residuals.

- [ ] **Step 1: Write failing invalid-topology and 17 V acceptance tests**

```python
def test_dangling_terminal_blocks_simulation() -> None:
    diagnostics = validate(loose_resistor_fixture().snapshot())
    assert diagnostics[0].code == "dangling-terminal"


def test_r3_parallel_with_r1_plus_r2_obeys_kirchhoff() -> None:
    snapshot = parallel_series_17v_fixture().snapshot()
    result = simulate(snapshot)
    report = build_equation_report(snapshot, result, -1)
    flows = reconstruct_wire_flows(snapshot, result, -1)
    assert result.branches["R1"].current[-1] == pytest.approx(0.085, rel=1e-4)
    assert result.branches["R2"].current[-1] == pytest.approx(0.085, rel=1e-4)
    assert result.branches["R3"].current[-1] == pytest.approx(0.085, rel=1e-4)
    assert abs(result.source_current[-1]) == pytest.approx(0.17, rel=1e-4)
    assert max(abs(eq.residual) for eq in (*report.kcl, *report.kvl)) < 1e-9
    assert max(flows.net_residuals.values()) < 1e-9
```

- [ ] **Step 2: Verify validation and fixture tests fail**

Run: `python -m pytest tests/solver/test_validation.py tests/integration/test_free_wiring_kirchhoff.py -v`

Expected: FAIL because free-wiring diagnostics and fixture are missing.

- [ ] **Step 3: Add structural validation before graph reachability**

Check that every component/source terminal has at least one incident wire, every wire endpoint exists, and no derived node contains both battery terminals without a component path. Return affected component and wire IDs in diagnostics.

- [ ] **Step 4: Add and save the 17 V example**

Construct the example only through public free-wiring commands and save it as schema 2. Do not hand-author solver node IDs.

- [ ] **Step 5: Run the acceptance tests**

Run: `python -m pytest tests/solver/test_validation.py tests/integration/test_free_wiring_kirchhoff.py tests/integration/test_examples.py -v`

Expected: all tests pass with the exact currents above.

- [ ] **Step 6: Commit**

```bash
git add src/circuitcanvas/solver/validation.py tests examples/parallel_series_17v.circuitcanvas
git commit -m "test: verify free-wired Kirchhoff circuits"
```

---

### Task 10: Documentation, portfolio screenshot, and release verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/mathematics.md`
- Replace: `docs/images/circuitcanvas-main.png`
- Modify: `circuitcanvas.spec` only if new modules are not discovered automatically

**Interfaces:**
- Consumes: the completed application.
- Produces: user instructions, mathematical explanation, architecture description, and current screenshot.

- [ ] **Step 1: Update documentation with exact interactions and conventions**

Document terminal dragging, wire taps, explicit junctions, route handles, rotation, Ordinary/Differential modes, KCL/KVL residuals, current-arrow speed/direction, and the minimum-norm ideal-wire convention. Include the 17 V `R3 || (R1 + R2)` example.

- [ ] **Step 2: Capture a representative screenshot**

Open `examples/parallel_series_17v.circuitcanvas`, show the ordinary Kirchhoff panel and blue arrows, and replace `docs/images/circuitcanvas-main.png` at a readable desktop resolution.

- [ ] **Step 3: Run the full quality gate**

Before the standard quality commands, add a performance regression that builds 100 components and 200 wire segments, rebuilds the scene, and asserts completion within 2 seconds on the test machine. The animation test must confirm one shared timer updates all 200 wires.

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src
QT_QPA_PLATFORM=offscreen python -m pytest
python -m build
python -m PyInstaller --clean --noconfirm circuitcanvas.spec
```

Expected: Ruff format and lint pass; mypy reports success; all tests pass; sdist, wheel, and `dist/CircuitCanvas.app` build successfully.

- [ ] **Step 4: Launch-probe the packaged app**

Run `dist/CircuitCanvas.app/Contents/MacOS/CircuitCanvas` with `QT_QPA_PLATFORM=offscreen`, confirm it remains alive for two seconds, then terminate it cleanly. Expected: no Python traceback or Qt plugin failure.

- [ ] **Step 5: Inspect changes and verify release scope**

Run: `git diff --check && git status -sb && git log --oneline --decorate -12`

Expected: no whitespace errors, only intended files changed, and every implementation task has a focused commit.

- [ ] **Step 6: Commit documentation**

```bash
git add README.md docs circuitcanvas.spec
git commit -m "docs: explain free wiring and Kirchhoff analysis"
```

- [ ] **Step 7: Push and verify GitHub Actions**

Push the feature branch, merge it to `main` after local verification, push `main`, and confirm the latest GitHub Actions run for `lpts1011/CircuitCanvas` succeeds.
