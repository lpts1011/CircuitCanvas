# Starter Loop and Octilinear Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open CircuitCanvas with an electrically real construction loop, support atomic series insertion on any wire, and constrain every visible wire segment and movable wire point to horizontal, vertical, or 45-degree geometry.

**Architecture:** A Qt-independent routing module supplies projection, path construction, and polyline projection primitives. The domain owns starter-loop topology and atomic wire replacement; the scene converts pointer positions into constrained routes and projects route handles/junctions onto their pre-drag wire paths. The main window uses the starter circuit while the existing solver-facing `Circuit.new()` remains unchanged.

**Tech Stack:** Python 3.12+, PySide6 6.8–6.10, NumPy, SciPy, pytest, pytest-qt, Ruff, mypy, PyInstaller

## Global Constraints

- Preserve Python 3.12+ and `PySide6>=6.8,<6.11` compatibility.
- Keep routing mathematics independent of PySide6 so it is directly unit-testable.
- Never draw a segment unless it is horizontal, vertical, or absolute-slope-one within `1e-6` tolerance.
- Keep visible and electrical connectivity identical; the starter loop is a real ideal-wire short until a component replaces a span.
- Make series insertion one undoable command with no transient partially modified graph.
- Preserve schema-2 load compatibility and existing free-wiring/Kirchhoff behavior.
- Maintain strict mypy, Ruff, background revision safety, packaging, and GitHub CI.

---

### Task 1: Qt-independent octilinear geometry

**Files:**
- Create: `src/circuitcanvas/ui/routing.py`
- Create: `tests/unit/test_routing.py`

**Interfaces:**
- Produces: `Point`, `is_octilinear(start, end, tolerance=1e-6)`, `project_to_octilinear(origin, point)`, `octilinear_route(start, end)`, `project_to_polyline(point, polyline)`, and `normalized_octilinear_polyline(points)`.
- Consumes: only Python `math` and tuple coordinates.

- [ ] **Step 1: Write failing direction and projection tests**

```python
def test_allowed_directions_and_free_point_projection() -> None:
    assert is_octilinear((0.0, 0.0), (20.0, 0.0))
    assert is_octilinear((0.0, 0.0), (0.0, -20.0))
    assert is_octilinear((0.0, 0.0), (20.0, 20.0))
    assert is_octilinear((0.0, 0.0), (-20.0, 20.0))
    assert not is_octilinear((0.0, 0.0), (20.0, 7.0))
    assert project_to_octilinear((0.0, 0.0), (20.0, 7.0)) == (20.0, 0.0)


def test_arbitrary_endpoints_get_only_octilinear_segments() -> None:
    start = (10.0, 10.0)
    end = (90.0, 45.0)
    points = (start, *octilinear_route(start, end), end)
    assert all(is_octilinear(left, right) for left, right in zip(points, points[1:]))
```

- [ ] **Step 2: Run tests and verify the missing module fails**

Run: `python -m pytest tests/unit/test_routing.py -v`

Expected: collection error for missing `circuitcanvas.ui.routing`.

- [ ] **Step 3: Implement deterministic projections and routes**

```python
type Point = tuple[float, float]


def is_octilinear(start: Point, end: Point, tolerance: float = 1e-6) -> bool:
    dx, dy = end[0] - start[0], end[1] - start[1]
    return abs(dx) <= tolerance or abs(dy) <= tolerance or abs(abs(dx) - abs(dy)) <= tolerance


def octilinear_route(start: Point, end: Point) -> tuple[Point, ...]:
    if is_octilinear(start, end):
        return ()
    dx, dy = end[0] - start[0], end[1] - start[1]
    diagonal = min(abs(dx), abs(dy))
    bend = (
        start[0] + (diagonal if dx >= 0 else -diagonal),
        start[1] + (diagonal if dy >= 0 else -diagonal),
    )
    return (bend,)
```

Implement projection to the nearest of the horizontal, vertical, rising-diagonal, and falling-diagonal axes. Implement clamped point-to-segment projection for `project_to_polyline`. Normalize arbitrary point sequences by removing duplicates and inserting `octilinear_route()` bends between invalid adjacent points.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/unit/test_routing.py -v`

Expected: all routing tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/circuitcanvas/ui/routing.py tests/unit/test_routing.py
git commit -m "feat: add octilinear wire geometry"
```

---

### Task 2: Starter loop and atomic component insertion

**Files:**
- Modify: `src/circuitcanvas/domain/circuit.py`
- Modify: `src/circuitcanvas/commands/circuit_commands.py`
- Modify: `tests/unit/test_commands.py`
- Modify: `tests/unit/test_wiring.py`

**Interfaces:**
- Consumes: `Junction`, `JunctionRef`, `TerminalRef`, `Wire`, and existing snapshot history.
- Produces: `Circuit.starter_loop(voltage: float = 12.0) -> Circuit` and `CircuitCommandStack.insert_component_on_wire(wire_id, kind, value, position, rotation, start_route, end_route) -> str`.

- [ ] **Step 1: Write failing starter-loop test**

```python
def test_starter_loop_connects_battery_terminals_through_real_wires() -> None:
    circuit = Circuit.starter_loop(12.0)
    connectivity = derive_connectivity(circuit)
    assert len(circuit.junctions) == 2
    assert len(circuit.wires) == 3
    assert connectivity.node_for(TerminalRef("V1", "a")) == connectivity.node_for(
        TerminalRef("V1", "b")
    )
```

- [ ] **Step 2: Run the test and verify `starter_loop` is missing**

Run: `python -m pytest tests/unit/test_wiring.py::test_starter_loop_connects_battery_terminals_through_real_wires -v`

Expected: FAIL with missing `Circuit.starter_loop`.

- [ ] **Step 3: Implement the starter topology**

```python
@classmethod
def starter_loop(cls, voltage: float = 12.0) -> Circuit:
    circuit = cls.new(voltage)
    circuit.open_edge = None
    circuit.junctions = {
        "J1": Junction("J1", (980.0, 290.0)),
        "J2": Junction("J2", (980.0, 430.0)),
    }
    circuit.wires = {
        "W1": Wire("W1", TerminalRef("V1", "a"), JunctionRef("J1")),
        "W2": Wire("W2", JunctionRef("J1"), JunctionRef("J2")),
        "W3": Wire("W3", JunctionRef("J2"), TerminalRef("V1", "b")),
    }
    circuit._wire_counter = 3
    circuit._junction_counter = 2
    return circuit
```

- [ ] **Step 4: Write failing atomic insertion/undo test**

```python
def test_insert_component_on_wire_removes_conductive_bypass_and_undoes_atomically() -> None:
    circuit = Circuit.starter_loop(12.0)
    stack = CircuitCommandStack(circuit)
    component_id = stack.insert_component_on_wire(
        "W1", ComponentKind.RESISTOR, 100.0, (520.0, 290.0), 0, (), ()
    )
    assert "W1" not in circuit.wires
    assert len(circuit.wires) == 4
    assert component_id in circuit.components
    assert validate(circuit.snapshot()) == ()
    assert stack.undo()
    assert circuit.components == {}
    assert "W1" in circuit.wires
```

- [ ] **Step 5: Run the insertion test and verify the method is missing**

Run: `python -m pytest tests/unit/test_commands.py::test_insert_component_on_wire_removes_conductive_bypass_and_undoes_atomically -v`

Expected: FAIL with missing `insert_component_on_wire`.

- [ ] **Step 6: Implement the command in one captured history operation**

Within `_execute`, validate `wire_id`, create the component with loose placeholder nodes, store its position/rotation, delete the selected wire, and add two wires:

```python
Wire(start_wire_id, original.start, TerminalRef(component_id, "a"), start_route)
Wire(end_wire_id, TerminalRef(component_id, "b"), original.end, end_route)
```

Return the component ID only after the complete graph mutation succeeds.

- [ ] **Step 7: Run domain and command tests**

Run: `python -m pytest tests/unit/test_wiring.py tests/unit/test_commands.py -v`

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/circuitcanvas/domain/circuit.py src/circuitcanvas/commands/circuit_commands.py tests/unit/test_wiring.py tests/unit/test_commands.py
git commit -m "feat: add editable starter circuit loop"
```

---

### Task 3: Octilinear rendering and constrained nodes

**Files:**
- Modify: `src/circuitcanvas/ui/wire_items.py`
- Modify: `src/circuitcanvas/ui/circuit_scene.py`
- Modify: `tests/gui/test_canvas.py`
- Modify: `tests/gui/test_current_animation.py`

**Interfaces:**
- Consumes: Task 1 routing functions and Task 2 command API.
- Produces: `CircuitScene.insert_component_on_wire(kind, wire_id, position)`, constrained preview/release behavior, projected route handles, and projected junction moves.

- [ ] **Step 1: Write failing painter-path direction test**

```python
def test_wire_item_path_contains_only_horizontal_vertical_or_45_degree_segments() -> None:
    wire = Wire("W1", TerminalRef("A", "a"), TerminalRef("B", "a"), ((31.0, 17.0),))
    item = WireItem(wire, QPointF(0.0, 0.0), QPointF(100.0, 60.0))
    points = item.polyline_points()
    assert all(
        is_octilinear((left.x(), left.y()), (right.x(), right.y()))
        for left, right in zip(points, points[1:])
    )
```

- [ ] **Step 2: Run the path test and verify unrestricted geometry fails**

Run: `python -m pytest tests/gui/test_current_animation.py::test_wire_item_path_contains_only_horizontal_vertical_or_45_degree_segments -v`

Expected: FAIL because `polyline_points` is missing or an arbitrary segment is present.

- [ ] **Step 3: Build `WireItem` from normalized octilinear points**

Replace the hidden orthogonal fallback with `normalized_octilinear_polyline((start, *wire.route, end))`. Store the normalized points, expose them through `polyline_points()`, and create the painter path by direct `lineTo` calls only.

- [ ] **Step 4: Write failing route-handle and junction projection tests**

```python
def test_route_handle_move_is_projected_back_to_its_wire(qtbot) -> None:
    scene = starter_scene_with_bent_wire()
    scene._route_moved("W1", 0, 410.0, 337.0)
    moved = scene.circuit.wires["W1"].route[0]
    assert moved == pytest.approx((410.0, 290.0))


def test_junction_move_is_projected_onto_an_incident_wire(qtbot) -> None:
    scene = CircuitScene(Circuit.starter_loop())
    scene._junction_moved("J1", 850.0, 360.0)
    assert scene.circuit.junctions["J1"].position == pytest.approx((850.0, 290.0))
```

- [ ] **Step 5: Run projection tests and verify free movement fails**

Run: `python -m pytest tests/gui/test_canvas.py -k "projected" -v`

Expected: FAIL because raw pointer positions are committed.

- [ ] **Step 6: Project edits against the pre-drag wire polyline**

Add scene helpers that derive stored endpoint coordinates without reading the already-moved graphics item. For a route handle, project onto its wire's old `WireItem.polyline_points()`. For a junction, collect all incident old wire polylines and choose the closest projected point. Commit only the projection; retain the old position when no incident segment exists.

- [ ] **Step 7: Constrain wire creation and double-click handles**

Use `project_to_octilinear` for the drag preview and empty-space endpoint. Use `octilinear_route` for exact terminal/junction targets. Project double-click coordinates with `project_to_polyline` before adding a handle.

- [ ] **Step 8: Add scene-level series insertion**

Determine the wire segment nearest the drop, choose rotation `90` for a vertical segment and `0` otherwise, compute terminal positions, build octilinear routes to the original wire endpoints, and call `insert_component_on_wire`.

- [ ] **Step 9: Run GUI tests**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_canvas.py tests/gui/test_current_animation.py -v`

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/circuitcanvas/ui/routing.py src/circuitcanvas/ui/wire_items.py src/circuitcanvas/ui/circuit_scene.py tests/gui/test_canvas.py tests/gui/test_current_animation.py
git commit -m "feat: constrain circuit wires to octilinear paths"
```

---

### Task 4: Starter-window workflow and series/parallel placement

**Files:**
- Modify: `src/circuitcanvas/ui/main_window.py`
- Modify: `src/circuitcanvas/ui/circuit_scene.py`
- Modify: `src/circuitcanvas/ui/palette.py`
- Modify: `tests/gui/test_main_window.py`
- Modify: `tests/solver/test_validation.py`

**Interfaces:**
- Consumes: `Circuit.starter_loop`, `CircuitScene.insert_component_on_wire`, and existing diagnostics.
- Produces: starter loop on launch/reset, palette quick insertion, drop-on-wire insertion, and an instructional starter-short status.

- [ ] **Step 1: Write failing launch/reset tests**

```python
def test_main_window_starts_and_resets_to_construction_loop(qtbot) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    assert len(window.circuit.wires) == 3
    window.scene.insert_component_on_wire("resistor", "W1", QPointF(520.0, 290.0))
    window.reset_circuit()
    assert window.circuit.components == {}
    assert len(window.circuit.wires) == 3
```

- [ ] **Step 2: Run and verify the window still uses `Circuit.new`**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_main_window.py::test_main_window_starts_and_resets_to_construction_loop -v`

Expected: FAIL with zero explicit starter wires.

- [ ] **Step 3: Switch launch/reset and palette click to starter workflow**

Use `Circuit.starter_loop()` in `MainWindow.__init__` and `reset_circuit`. When a palette card is clicked and the scene uses explicit wiring, choose the longest wire segment and insert the component at its midpoint. Preserve the legacy helper only for loaded legacy circuits.

- [ ] **Step 4: Route component drops through the hit-tested wire**

In `CircuitView.dropEvent`, map the pointer to scene coordinates and inspect `scene.itemAt`. When it is a `WireItem`, call `scene.insert_component_on_wire`; otherwise call `scene.insert_component_at`.

- [ ] **Step 5: Add the expected short diagnostic copy**

When validation returns `source-short` for a component-free starter loop, display: `Starter loop is a short circuit · place a component on a wire`. Retain the normal source-short diagnostic for user-created shorts after components exist.

- [ ] **Step 6: Run main-window, validation, and integration tests**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_main_window.py tests/solver/test_validation.py tests/integration -v`

Expected: all tests pass, including the 17 V parallel-series Kirchhoff fixture.

- [ ] **Step 7: Commit**

```bash
git add src/circuitcanvas/ui/main_window.py src/circuitcanvas/ui/circuit_scene.py src/circuitcanvas/ui/palette.py tests/gui/test_main_window.py tests/solver/test_validation.py
git commit -m "feat: start with an editable closed circuit"
```

---

### Task 5: Documentation, visual QA, and delivery verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/images/circuitcanvas-main.png`
- Modify: `pyproject.toml`
- Modify: `src/circuitcanvas/__init__.py`
- Modify: `circuitcanvas.spec`

**Interfaces:**
- Consumes: completed UI behavior.
- Produces: CircuitCanvas 0.3 documentation, screenshot, packages, and verified GitHub main.

- [ ] **Step 1: Update user instructions and version**

Document that the initial loop is a construction short, drop-on-wire performs series insertion, loose placement supports manual parallel wiring, Shift-drag continues from a junction, and every wire segment is H/V/45. Update package and app version from `0.2.0` to `0.3.0`.

- [ ] **Step 2: Generate and visually inspect a fresh screenshot**

Load the 17 V parallel-series example in an offscreen styled window, render it to `docs/images/circuitcanvas-main.png`, and inspect the original-resolution PNG. Verify no forbidden-angle segment, clipped equation text, or stale current arrow is visible.

- [ ] **Step 3: Run the complete quality gate**

Run:

```bash
ruff format --check .
ruff check .
mypy src
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m build
pyinstaller --clean --noconfirm circuitcanvas.spec
```

Expected: zero failures and successful source, wheel, and macOS app builds.

- [ ] **Step 4: Launch-probe the packaged app**

Start `dist/CircuitCanvas.app/Contents/MacOS/CircuitCanvas` with `QT_QPA_PLATFORM=offscreen`, confirm it remains running for three seconds, and terminate it cleanly.

- [ ] **Step 5: Review the complete feature diff**

Compare against `docs/superpowers/specs/2026-07-14-starter-loop-octilinear-wiring-design.md`. Fix every critical or important issue with a red-green test cycle and rerun the complete quality gate.

- [ ] **Step 6: Commit, merge, and publish**

Commit documentation/build metadata, fast-forward the feature branch to `main`, push `origin/main`, wait for GitHub Actions, and require a successful CI conclusion before reporting completion.
