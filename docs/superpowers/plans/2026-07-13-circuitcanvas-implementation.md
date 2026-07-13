# CircuitCanvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portfolio-quality PySide6 desktop application in which users add any practical number of R, C, and L components to a battery-powered series-parallel circuit and immediately inspect physically consistent transient voltage, current, power, and energy results.

**Architecture:** Keep the electrical domain model and Modified Nodal Analysis solver independent of Qt. Represent canvas edits as atomic domain commands, simulate immutable circuit snapshots in a revision-aware background worker, and adapt result objects into graphics annotations, plots, tables, summaries, and exports.

**Tech Stack:** Python 3.12+, PySide6, NumPy, SciPy, PyQtGraph, pytest, pytest-qt, Ruff, mypy, PyInstaller

## Global Constraints

- Python 3.12 or newer; source code uses the `src/` package layout.
- The supported devices are one ideal DC voltage source and any practical number of two-terminal resistors, capacitors, and inductors.
- Version 1 exposes repeated series insertion and parallel-branch creation, not arbitrary freehand wiring.
- Capacitor voltage and inductor current start at zero; the battery is a step source at `t=0`.
- The default transient uses implicit trapezoidal integration, 0.1 seconds, and 1,000 samples; backward Euler is also available.
- All calculations run outside the GUI thread and stale revision results are discarded.
- Invalid circuits show specific diagnostics and never display a new fabricated result.
- The project remains portable between macOS and Windows.

---

## Planned file map

```text
CircuitCanvas/
├── .github/workflows/ci.yml              # GitHub test and lint automation
├── .gitignore                            # Python, Qt, build, and local artifacts
├── LICENSE                               # MIT license
├── README.md                             # Installation, demo, maths, architecture
├── pyproject.toml                        # Package metadata, dependencies, tools
├── src/circuitcanvas/
│   ├── __init__.py                       # Package version
│   ├── app.py                            # QApplication entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   └── circuit_commands.py           # Atomic insert/delete/update commands
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── circuit.py                    # Nodes, circuit, settings, snapshots
│   │   ├── components.py                 # Battery, resistor, capacitor, inductor
│   │   └── serialization.py              # Versioned JSON codec
│   ├── solver/
│   │   ├── __init__.py
│   │   ├── validation.py                 # Topology and numeric diagnostics
│   │   ├── mna.py                        # Matrix stamping and system assembly
│   │   ├── transient.py                  # Time stepping and result generation
│   │   └── results.py                    # Immutable branch/time-series results
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py                # Application composition and actions
│       ├── circuit_scene.py              # Grid, snap targets, graph layout
│       ├── component_items.py            # Battery/R/C/L graphics and annotations
│       ├── palette.py                    # Draggable component cards
│       ├── inspector.py                  # Numeric editor, SI units, log slider
│       ├── analysis_panel.py             # PyQtGraph plots, metrics, data table
│       ├── simulation_controller.py      # Debounce, background worker, revisions
│       └── export.py                     # CSV and PNG exports
├── tests/
│   ├── unit/                             # Domain, command, serialization tests
│   ├── solver/                           # Analytical and conservation tests
│   ├── integration/                      # Edit-to-result and persistence flows
│   └── gui/                              # Headless Qt interaction smoke tests
└── examples/                             # Saved R, RC, RL, RLC circuits
```

### Task 1: Project foundation and electrical domain model

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `src/circuitcanvas/__init__.py`
- Create: `src/circuitcanvas/domain/__init__.py`
- Create: `src/circuitcanvas/domain/components.py`
- Create: `src/circuitcanvas/domain/circuit.py`
- Test: `tests/unit/test_domain.py`

**Interfaces:**
- Produces: `ComponentKind`, `Component`, `VoltageSource`, `Resistor`, `Capacitor`, `Inductor`, `SimulationSettings`, `Circuit`, and `CircuitSnapshot`.
- `Circuit.snapshot() -> CircuitSnapshot` is the immutable solver input used by all later tasks.

- [ ] **Step 1: Add packaging and tool configuration**

Define the `circuitcanvas` console script as `circuitcanvas.app:main`, runtime dependencies on PySide6/NumPy/SciPy/PyQtGraph, a `dev` extra for pytest/pytest-qt/Ruff/mypy/PyInstaller, and pytest's `QT_QPA_PLATFORM=offscreen` environment.

- [ ] **Step 2: Write failing domain tests**

```python
def test_new_circuit_contains_source_and_open_drop_target() -> None:
    circuit = Circuit.new(12.0)
    assert circuit.source.voltage == 12.0
    assert circuit.components == {}
    assert circuit.entry_nodes == ("n_pos", "n_neg")

def test_component_values_must_be_positive_and_finite() -> None:
    with pytest.raises(ValueError, match="positive finite"):
        Resistor(id="R1", node_a="a", node_b="b", resistance=0.0)
```

- [ ] **Step 3: Run the tests and verify the missing-package failure**

Run: `python -m pytest tests/unit/test_domain.py -q`  
Expected: collection fails because `circuitcanvas.domain` does not exist.

- [ ] **Step 4: Implement immutable typed components and mutable circuit ownership**

Use frozen dataclasses for components and snapshots. Store components by stable ID and expose `Circuit.replace_component()`, `remove_component()`, and `snapshot()` without importing Qt.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest tests/unit/test_domain.py -q`  
Expected: all domain tests pass.

```bash
git add pyproject.toml .gitignore LICENSE src tests/unit/test_domain.py
git commit -m "feat: establish CircuitCanvas domain model"
```

### Task 2: Atomic series and parallel graph commands

**Files:**
- Create: `src/circuitcanvas/commands/__init__.py`
- Create: `src/circuitcanvas/commands/circuit_commands.py`
- Test: `tests/unit/test_commands.py`

**Interfaces:**
- Consumes: `Circuit`, component dataclasses, and stable node/component IDs.
- Produces: `insert_series(circuit, target_edge, kind, value) -> str`, `add_parallel(circuit, target_component_id, kind, value) -> str`, `delete_component(circuit, component_id) -> None`, and `update_component_value(...)`.
- Each command stores enough before/after state for `undo()` and `redo()` through `CircuitCommandStack`.

- [ ] **Step 1: Write failing graph-edit tests**

```python
def test_repeated_series_and_parallel_additions_preserve_connectivity() -> None:
    circuit = Circuit.new(9.0)
    r1 = insert_series(circuit, circuit.open_edge, ComponentKind.RESISTOR, 100.0)
    c1 = insert_series(circuit, circuit.edge_after(r1), ComponentKind.CAPACITOR, 1e-6)
    r2 = add_parallel(circuit, c1, ComponentKind.RESISTOR, 220.0)
    assert set(circuit.components) == {r1, c1, r2}
    assert circuit.components[c1].endpoints == circuit.components[r2].endpoints
```

- [ ] **Step 2: Verify the tests fail for missing command functions**

Run: `python -m pytest tests/unit/test_commands.py -q`  
Expected: import error for `circuitcanvas.commands.circuit_commands`.

- [ ] **Step 3: Implement stable ID allocation, edge splitting, branch creation, and command history**

Model wires as explicit `Wire` edges so series insertion replaces one wire with `wire → component → wire`. Parallel creation reuses the target's endpoint nodes. Reject edits that would duplicate IDs or reference missing endpoints.

- [ ] **Step 4: Verify add, delete, undo, and redo flows**

Run: `python -m pytest tests/unit/test_commands.py -q`  
Expected: all command tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/circuitcanvas/commands tests/unit/test_commands.py
git commit -m "feat: add repeatable circuit graph commands"
```

### Task 3: Circuit validation and MNA assembly

**Files:**
- Create: `src/circuitcanvas/solver/__init__.py`
- Create: `src/circuitcanvas/solver/validation.py`
- Create: `src/circuitcanvas/solver/mna.py`
- Test: `tests/solver/test_validation.py`
- Test: `tests/solver/test_mna.py`

**Interfaces:**
- Consumes: `CircuitSnapshot`.
- Produces: `Diagnostic(code, message, component_ids, severity)`, `validate(snapshot) -> tuple[Diagnostic, ...]`, and `assemble(snapshot) -> MNASystem`.
- `MNASystem` exposes `g`, `c`, `source_vector`, `unknowns`, and component index metadata.

- [ ] **Step 1: Write failing validation tests for open, shorted, floating, and malformed circuits**

```python
def test_open_circuit_reports_actionable_diagnostic() -> None:
    diagnostics = validate(Circuit.new(12.0).snapshot())
    assert diagnostics[0].code == "open-circuit"
    assert "component" in diagnostics[0].message.lower()
```

- [ ] **Step 2: Write failing resistor MNA test**

Build a 12 V source and 100 Ω resistor and assert the assembled solution gives 0.12 A with KCL residual below `1e-10`.

- [ ] **Step 3: Run and confirm failures**

Run: `python -m pytest tests/solver/test_validation.py tests/solver/test_mna.py -q`  
Expected: missing solver modules.

- [ ] **Step 4: Implement validation and component matrix stamps**

Choose `n_neg` as ground, stamp conductances into `G`, capacitances into `C`, ideal voltage-source rows/columns into `G`, and inductor auxiliary-current rows with `-L` in `C`. Keep component-to-unknown metadata for later branch result extraction.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest tests/solver/test_validation.py tests/solver/test_mna.py -q`  
Expected: all validation and assembly tests pass.

```bash
git add src/circuitcanvas/solver tests/solver/test_validation.py tests/solver/test_mna.py
git commit -m "feat: assemble validated RLC MNA systems"
```

### Task 4: Transient solver and physically derived results

**Files:**
- Create: `src/circuitcanvas/solver/results.py`
- Create: `src/circuitcanvas/solver/transient.py`
- Test: `tests/solver/test_transient.py`
- Test: `tests/solver/test_conservation.py`

**Interfaces:**
- Consumes: `CircuitSnapshot`, `MNASystem`, and `method: Literal["trapezoidal", "backward-euler"]`.
- Produces: `simulate(snapshot) -> SimulationResult`, containing `time`, `node_voltages`, `branches: Mapping[str, BranchResult]`, `source_current`, `source_power`, and `metrics`.
- `BranchResult` contains aligned NumPy arrays for voltage, current, power, and energy.

- [ ] **Step 1: Write analytical response tests**

```python
def test_rc_step_matches_analytic_curve() -> None:
    result = simulate(rc_fixture(R=1_000.0, C=10e-6, voltage=5.0, duration=0.05))
    expected = 5.0 * (1.0 - np.exp(-result.time / 0.01))
    np.testing.assert_allclose(result.branches["C1"].voltage, expected, atol=8e-3)
```

Add corresponding RL and under/critical/overdamped RLC fixtures plus a resistor-only constant-result case.

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `python -m pytest tests/solver/test_transient.py -q`  
Expected: missing `simulate` and result types.

- [ ] **Step 3: Implement implicit trapezoidal and backward-Euler stepping**

For trapezoidal integration solve

```text
(G + 2C/dt) x[k+1] = (2C/dt - G) x[k] + b[k+1] + b[k]
```

Reuse `scipy.linalg.lu_factor` and `lu_solve`, seed zero reactive state, and represent the source step consistently at the first positive sample.

- [ ] **Step 4: Derive branch values, metrics, and conservation residuals**

Use the passive sign convention, compute `0.5*C*v**2` and `0.5*L*i**2`, and expose KCL, KVL, and energy residuals for tests and diagnostics.

- [ ] **Step 5: Run solver tests and commit**

Run: `python -m pytest tests/solver -q`  
Expected: all analytical and conservation tests pass within stated tolerances.

```bash
git add src/circuitcanvas/solver tests/solver
git commit -m "feat: simulate and analyze RLC transients"
```

### Task 5: Versioned persistence and example circuits

**Files:**
- Create: `src/circuitcanvas/domain/serialization.py`
- Create: `examples/resistor.json`
- Create: `examples/rc-charge.json`
- Create: `examples/rl-step.json`
- Create: `examples/rlc-underdamped.json`
- Test: `tests/unit/test_serialization.py`
- Test: `tests/integration/test_examples.py`

**Interfaces:**
- Consumes: `Circuit` and a UTF-8 JSON path.
- Produces: `circuit_to_dict(circuit)`, `circuit_from_dict(payload)`, `save_circuit(path, circuit)`, and `load_circuit(path) -> Circuit`.

- [ ] **Step 1: Write failing round-trip and schema-error tests**

Assert values, IDs, endpoints, positions, simulation settings, and source survive a round trip. Assert an unsupported schema version raises `CircuitFileError` with the received and supported versions.

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/unit/test_serialization.py -q`  
Expected: missing serialization functions.

- [ ] **Step 3: Implement schema version 1 and curated examples**

Serialize SI values as numbers, enum values as lowercase strings, positions as two-number arrays, and never persist computed result arrays.

- [ ] **Step 4: Verify examples load and simulate**

Run: `python -m pytest tests/unit/test_serialization.py tests/integration/test_examples.py -q`  
Expected: every example loads, validates, and produces finite results.

- [ ] **Step 5: Commit**

```bash
git add src/circuitcanvas/domain/serialization.py examples tests
git commit -m "feat: save and load versioned circuit files"
```

### Task 6: Circuit graphics scene, component palette, and repeated drag/drop

**Files:**
- Create: `src/circuitcanvas/ui/__init__.py`
- Create: `src/circuitcanvas/ui/component_items.py`
- Create: `src/circuitcanvas/ui/circuit_scene.py`
- Create: `src/circuitcanvas/ui/palette.py`
- Test: `tests/gui/test_canvas.py`

**Interfaces:**
- Consumes: `Circuit`, graph command functions, and `SimulationResult | None`.
- Produces: `CircuitScene.circuit_changed(revision)`, `selection_changed(component_id)`, and `set_result(result, time_index)`.
- Palette MIME payload is `application/x-circuitcanvas-component` with the lowercase component kind.

- [ ] **Step 1: Write headless GUI tests for the initial battery and repeated additions**

```python
def test_scene_accepts_more_than_one_component_of_each_kind(qtbot) -> None:
    scene = CircuitScene(Circuit.new(12.0))
    for kind in ("resistor", "resistor", "capacitor", "inductor", "capacitor"):
        scene.insert_component_for_test(kind)
    assert len(scene.circuit.components) == 5
```

- [ ] **Step 2: Confirm missing UI tests fail**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_canvas.py -q`  
Expected: missing `CircuitScene`.

- [ ] **Step 3: Implement palette drags, snap overlays, atomic drops, and component items**

Draw IEC-style vector symbols with `QGraphicsItem` primitives. Highlight series insertion targets and parallel targets during drag. Re-layout the series-parallel graph deterministically after each edit while preserving pan and zoom.

- [ ] **Step 4: Add annotations and active time-cursor updates**

Render name/value above each item and signed voltage/current below it. Show `—` before a valid result and dim annotations when the currently displayed result is stale.

- [ ] **Step 5: Run GUI tests and commit**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_canvas.py -q`  
Expected: initial state, repeated component addition, selection, and annotation tests pass.

```bash
git add src/circuitcanvas/ui tests/gui/test_canvas.py
git commit -m "feat: build smart-snap RLC circuit canvas"
```

### Task 7: Component inspector and analysis panel

**Files:**
- Create: `src/circuitcanvas/ui/inspector.py`
- Create: `src/circuitcanvas/ui/analysis_panel.py`
- Test: `tests/gui/test_inspector.py`
- Test: `tests/gui/test_analysis_panel.py`

**Interfaces:**
- Consumes: selected component, component update callback, and `BranchResult`.
- Produces: `ComponentInspector.value_changed(component_id, si_value)`, `delete_requested`, `rotate_requested`, and `AnalysisPanel.time_index_changed(index)`.

- [ ] **Step 1: Write failing SI input and logarithmic-slider tests**

Verify `47 μF` emits `47e-6`, a typed value round-trips without slider rounding, malformed input displays an inline error, and the delete signal carries the selected stable ID.

- [ ] **Step 2: Write failing plot/table consistency tests**

Set a synthetic `BranchResult`; assert both plot curves receive all samples, the table cell at row `k` matches the same arrays, and changing the plot cursor emits `k`.

- [ ] **Step 3: Implement focused widgets**

Use `QDoubleValidator`, explicit unit multipliers, a logarithmic mapping for slider positions, two PyQtGraph view boxes for voltage/current, and a lazily populated `QTableView` model for samples.

- [ ] **Step 4: Run and commit**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_inspector.py tests/gui/test_analysis_panel.py -q`  
Expected: all inspector, plot, table, and time-cursor tests pass.

```bash
git add src/circuitcanvas/ui/inspector.py src/circuitcanvas/ui/analysis_panel.py tests/gui
git commit -m "feat: inspect component values and transient data"
```

### Task 8: Revision-safe simulation controller and main window

**Files:**
- Create: `src/circuitcanvas/ui/simulation_controller.py`
- Create: `src/circuitcanvas/ui/main_window.py`
- Create: `src/circuitcanvas/app.py`
- Test: `tests/integration/test_controller.py`
- Test: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: circuit snapshots and revisions.
- Produces: `SimulationController.request(revision, snapshot)`, `result_ready(revision, result)`, `diagnostics_ready(revision, diagnostics)`, and a composed `MainWindow`.

- [ ] **Step 1: Write failing debounce and stale-result tests**

Use a controllable fake solver. Submit revisions 1 and 2, deliver revision 1 last, and assert only revision 2 reaches the window. Verify rapid requests collapse into one solve after 150 ms.

- [ ] **Step 2: Write a failing headless main-window smoke test**

Create `MainWindow`, add a resistor through its scene, wait for simulation, and assert the summary displays source voltage, total current, total power, and a valid status.

- [ ] **Step 3: Implement controller and window composition**

Use `QThreadPool`/`QRunnable` with signal bridge objects. Compose toolbar, canvas, palette, inspector, analysis panel, summary, and diagnostics. Add `QUndoStack`, Save, Open, Reset, and example-loading actions.

- [ ] **Step 4: Add safe result application**

Apply results only when `result_revision == circuit.revision`; otherwise ignore them. Keep a prior result dimmed when validation fails and clear it when loading a different circuit.

- [ ] **Step 5: Run and commit**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/integration/test_controller.py tests/gui/test_main_window.py -q`  
Expected: debounce, stale-result, startup, valid-result, and diagnostic recovery tests pass.

```bash
git add src/circuitcanvas/app.py src/circuitcanvas/ui tests/integration tests/gui
git commit -m "feat: compose responsive CircuitCanvas desktop app"
```

### Task 9: CSV/PNG export, CI, and desktop packaging

**Files:**
- Create: `src/circuitcanvas/ui/export.py`
- Create: `circuitcanvas.spec`
- Create: `.github/workflows/ci.yml`
- Test: `tests/unit/test_export.py`

**Interfaces:**
- Consumes: `SimulationResult`, selected component ID, `QGraphicsScene`, and output path.
- Produces: `export_branch_csv(...)` and `export_scene_png(...)`.

- [ ] **Step 1: Write failing export tests**

Assert CSV headers are `time_s,voltage_v,current_a,power_w,energy_j`, every row has aligned samples, and a scene export creates a non-empty PNG with the requested transparent/solid background behavior.

- [ ] **Step 2: Implement deterministic exports**

Use Python's `csv` module with UTF-8/newline control and render the scene into a device-pixel-ratio-aware `QImage`.

- [ ] **Step 3: Add CI and PyInstaller configuration**

Run Linux CI on Python 3.12 with offscreen Qt, `ruff check`, `ruff format --check`, `mypy`, and pytest. Configure PyInstaller to collect Qt/PyQtGraph resources and create `CircuitCanvas.app` on macOS.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/unit/test_export.py -q && ruff check . && ruff format --check . && mypy src`  
Expected: all commands exit zero.

```bash
git add src/circuitcanvas/ui/export.py tests/unit/test_export.py circuitcanvas.spec .github
git commit -m "build: add exports CI and desktop packaging"
```

### Task 10: Portfolio documentation, full verification, and visual QA

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/mathematics.md`
- Create: `docs/images/`
- Modify: all files found defective during verification

**Interfaces:**
- Consumes: the completed application and verification commands.
- Produces: a reviewable GitHub landing page and final validated release candidate.

- [ ] **Step 1: Write the README and technical notes**

Lead with the outcome and an application screenshot/GIF. Document install/run commands, interaction model, example circuits, MNA equation, integration method, architecture boundaries, test commands, limitations, and packaging.

- [ ] **Step 2: Run the complete automated verification suite**

Run:

```bash
ruff format .
ruff check .
mypy src
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m build
```

Expected: every command exits zero and the wheel/sdist are created.

- [ ] **Step 3: Perform manual and visual verification**

Launch the app, create resistor, RC, RL, and RLC circuits, add repeated R/C/L components, exercise series/parallel targets, move the time cursor, edit values by typing and slider, delete/undo, save/reload, export CSV/PNG, and verify invalid/open circuits recover. Capture final screenshots only after labels, spacing, plots, and error states are visually clean.

- [ ] **Step 4: Compare implementation against every acceptance criterion**

Record any gap as a failing automated test or reproducible manual case, fix it, and rerun the relevant focused verification before repeating the full suite.

- [ ] **Step 5: Commit the release candidate**

```bash
git add README.md docs src tests examples pyproject.toml
git commit -m "docs: prepare CircuitCanvas portfolio release"
```

## Plan self-review

- Every Version 1 capability in the design specification maps to Tasks 1–10.
- The domain, command, solver, UI, and export interfaces use consistent names across tasks.
- Repeated component insertion is explicitly tested in Tasks 2, 6, 8, and 10.
- Invalid-state, stale-result, conservation, persistence, export, and visual-quality checks are explicit.
- Each task produces an independently testable and committable deliverable.
