# CircuitCanvas Design Specification

**Date:** 2026-07-13

**Working title:** CircuitCanvas — Interactive RLC Circuit Simulator

**Technology:** Python 3.12+, PySide6, NumPy, SciPy, PyQtGraph

**Primary platform:** macOS desktop, with Windows-compatible code and packaging

## 1. Product purpose

CircuitCanvas is a desktop circuit-building and transient-simulation application. It opens with a DC battery and an incomplete loop. The user drags resistors, capacitors, and inductors from a component palette onto highlighted snap targets. Each valid edit immediately updates component voltage, current, power, stored energy, circuit totals, and voltage/current-versus-time plots.

The project is intended to demonstrate mathematical modelling, circuit theory, numerical methods, interactive software design, automated testing, and clear technical communication. It should be understandable from the GitHub README even if a reviewer does not install the application.

## 2. Design principles

1. **The circuit is the interface.** Results appear next to the relevant component instead of being hidden in a separate calculator form.
2. **Every result must be physically defensible.** Invalid or singular circuits show an explanation rather than a fabricated number.
3. **Progressive complexity.** The first resistor is easy to add, while the same interaction supports larger series-parallel RLC networks.
4. **Unlimited composition within practical resources.** The UI does not impose a small fixed number of R, C, or L components. The canvas grows through pan and zoom.
5. **Educational transparency.** Users can inspect plots, data tables, current directions, voltage polarities, solver settings, and validation messages.
6. **Portfolio quality over feature count.** The initial release has a focused, tested scope and a strong demonstration rather than unrelated electrical tools.

## 3. Version 1 scope

### Included

- One editable ideal DC voltage source, represented as a battery
- Any practical number of resistors, capacitors, and inductors
- Series insertion and parallel-branch creation through smart snap targets
- Component movement, rotation, deletion, naming, and value editing
- Direct numeric entry with SI unit selection
- A logarithmic value slider for fast experimentation
- Automatic transient simulation after topology or value changes
- Zero initial capacitor voltage and zero initial inductor current
- Voltage, current, and instantaneous power for every component
- Stored energy for capacitors and inductors
- Total source current and source power
- Per-component voltage and current labels on the canvas
- Selected-component voltage and current plots against time
- A data-table view with time, voltage, current, power, and energy
- Simulation duration and sample-count controls
- Pan, zoom, selection, undo, and redo
- Save/load of a circuit in a documented JSON format
- PNG circuit export and CSV transient-data export
- Clear diagnostics for invalid topologies and numerical failures
- macOS application packaging and documented source installation

### Explicitly excluded from Version 1

- AC sinusoidal sources and frequency-domain/Bode analysis
- Diodes, transistors, op-amps, switches, dependent sources, and nonlinear devices
- Arbitrary freehand wire routing or PCB/breadboard design
- Multiple independent voltage or current sources
- User-set non-zero reactive initial conditions
- Cloud accounts, collaboration, and online storage
- Mobile or browser editions

These exclusions keep the first release coherent. The circuit model and file format will retain component type fields and source abstractions so later releases can add capabilities without rewriting the UI.

## 4. User experience and interaction model

### 4.1 Initial state

The main window displays:

- a central grid canvas with a battery on the left;
- an open loop containing a highlighted `Drop a component here` target;
- a right sidebar containing draggable Resistor, Capacitor, and Inductor cards;
- a properties panel below the palette;
- a bottom transient-analysis panel; and
- a compact circuit summary and validation indicator.

The initial loop is intentionally open. A closed wire around an ideal battery would be a short circuit, so the first component closes the path safely.

### 4.2 Adding more components

Dragging a palette item over the canvas reveals only valid targets:

- **Insert in series:** dropping on a highlighted wire segment splits that segment and places the component between the resulting nodes.
- **Add in parallel:** hovering an existing component or branch reveals a parallel target. Dropping there creates two junctions when necessary and adds a new branch between the same endpoint nodes.
- **Extend a branch:** dropping on any wire segment inside a branch inserts another series component into that branch.

The same operations may be repeated. There is no design-level limit such as one resistor, one capacitor, and one inductor. Invalid drops return the component to the palette and briefly explain why the target was rejected.

Version 1 therefore supports networks built by repeated series and parallel composition. The internal graph and solver are more general, but the UI does not expose unrestricted manual wiring in this release.

### 4.3 Editing

Selecting a component opens its inspector. The user can:

- enter a value directly;
- choose an SI prefix and unit;
- move a logarithmic slider over a component-appropriate range;
- rename, rotate, move, or delete the component; and
- focus its analysis plot and table.

Numeric entry is authoritative. The slider mirrors the value and never rounds a typed value without permission. Edits are debounced for 150 ms so continuous slider movement feels responsive without launching overlapping simulations.

### 4.4 Live annotations

Each component shows its name and value. When a simulation succeeds, a compact secondary label shows the voltage and current at the active time cursor. Arrows and `+`/`−` markers define the reported reference directions. The plot cursor may be dragged through time, updating every visible annotation consistently.

The default cursor rests at the final simulated time, so resistor-only circuits display their DC result immediately. Reactive circuits show their final simulated value while the plot communicates the complete transient.

### 4.5 Analysis panel

Selecting a component displays:

- voltage and current curves on aligned time axes;
- optional power and stored-energy curves;
- current value, peak magnitude, final value, and approximate settling time;
- an RC/RL time constant when it is unambiguous for a simple first-order circuit; and
- a table with the exact plotted samples.

The UI must not claim a single time constant for a higher-order network. In that case it reports modal/settling information or labels the time constant as not applicable.

## 5. Circuit model

The domain model is independent of PySide6. A `Circuit` owns:

- stable node identifiers;
- a single `VoltageSource`;
- a collection of two-terminal `Resistor`, `Capacitor`, and `Inductor` objects;
- the endpoint nodes and display metadata of every component; and
- serializable simulation settings.

The canvas maintains graphics objects that refer to domain-model IDs. Electrical connectivity is derived from explicit nodes, never from approximate screen coordinates. A snap operation changes the graph in one atomic command, which enables undo/redo and prevents half-connected circuits.

The saved JSON format includes a schema version, source, nodes, components, canvas positions, and simulation settings. Computed results are not authoritative saved state; they are regenerated when the file opens.

## 6. Simulation and mathematical approach

### 6.1 Formulation

The solver uses time-domain Modified Nodal Analysis (MNA). It assembles the linear descriptor system

\[
Gx(t) + C\dot{x}(t) = b(t),
\]

where the unknown vector contains non-ground node voltages plus the auxiliary currents required by ideal voltage sources and inductors. Each component contributes a small stamp to the global matrices.

The battery is modelled as a step from 0 V to the configured voltage at \(t=0\). Version 1 assumes zero initial capacitor voltages and zero initial inductor currents.

### 6.2 Time integration

The default method is implicit trapezoidal integration because it is stable for linear RLC networks and more accurate than forward Euler. Backward Euler is available as a robust alternative and as a fallback diagnostic method. The matrix factorization is reused across fixed time steps when the topology and step size are unchanged.

Default settings are 0.1 seconds and 1,000 samples. The user can change both. Simple first-order circuits may receive an automatic duration suggestion based on their computed time constant, but the application never silently changes a user-entered duration.

### 6.3 Derived quantities

For every sample, the result layer derives:

- resistor current and voltage from Ohm's law;
- capacitor voltage from node voltages and current from its constitutive relation;
- inductor current from the MNA auxiliary unknown and voltage from node voltages;
- passive-sign-convention power \(p(t)=v(t)i(t)\);
- capacitor energy \(E_C=\tfrac12 Cv^2\); and
- inductor energy \(E_L=\tfrac12 Li^2\).

The source current and power use a clearly documented sign convention. Canvas arrows and plot legends use the same convention.

## 7. Software architecture

```text
CircuitCanvas/
├── pyproject.toml
├── README.md
├── src/circuitcanvas/
│   ├── app.py
│   ├── domain/
│   │   ├── circuit.py
│   │   ├── components.py
│   │   └── serialization.py
│   ├── solver/
│   │   ├── validation.py
│   │   ├── mna.py
│   │   ├── transient.py
│   │   └── results.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── circuit_scene.py
│   │   ├── component_items.py
│   │   ├── inspector.py
│   │   └── analysis_panel.py
│   └── commands/
│       └── circuit_commands.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── gui/
├── examples/
└── docs/
```

Responsibilities are separated as follows:

- **Domain:** component values, nodes, connectivity, and persistence; no UI imports.
- **Solver:** validation, MNA assembly, integration, and derived results; no UI imports.
- **UI:** drag/drop, drawing, property controls, plots, and messages.
- **Commands:** atomic graph edits shared by UI actions and undo/redo.

The main window sends an immutable circuit snapshot to a background simulation worker. Every edit increments a revision number. A result is applied only if its revision matches the current circuit, preventing a slow older calculation from overwriting a newer one.

## 8. Data flow

```text
Drag, delete, or value edit
        ↓
Atomic circuit command + new revision
        ↓
Topology/value validation
        ↓
Background MNA assembly and transient solve
        ↓
Revision check
        ↓
Result model
        ↓
Canvas labels + summary + plots + data table
```

Presentation widgets receive a result object rather than reaching into solver internals. This makes the mathematical core independently testable and allows a future command-line or web interface to reuse it.

## 9. Validation and error handling

Validation runs before simulation and detects:

- an open circuit with no complete path;
- a direct ideal-wire short across the voltage source;
- floating subcircuits and disconnected components;
- non-positive, non-finite, or malformed component values;
- duplicate or missing graph references;
- singular MNA matrices;
- non-finite or numerically unstable results; and
- stale background results from an older revision.

Expected user errors appear in the sidebar with the affected nodes/components highlighted. They do not open repeated modal dialogs. Unexpected internal errors are logged with context and shown as a short recoverable message. The last valid result may remain visible but is marked stale and visually dimmed until the circuit becomes valid again.

## 10. Testing strategy

### Unit tests

- component validation and SI-unit conversion;
- graph edits, series insertion, parallel creation, and undo/redo;
- JSON round trips and schema-version checks;
- individual MNA stamps for R, C, L, and the source; and
- voltage, current, power, and energy sign conventions.

### Analytical solver tests

- a resistor circuit against \(I=V/R\);
- RC charging against \(v_C(t)=V(1-e^{-t/RC})\);
- RL step response against \(i_L(t)=V/R(1-e^{-Rt/L})\);
- underdamped, critically damped, and overdamped series RLC fixtures;
- series and parallel resistor equivalents;
- KCL and KVL residual checks at every time sample; and
- passive energy balance within numerical tolerance.

### Integration and GUI tests

- adding, moving, editing, and deleting multiple components updates the model;
- rapid slider edits cannot display stale results;
- invalid circuits show the correct diagnostic and recover after repair;
- plot and table values agree with the result object;
- save/load preserves topology and layout; and
- a headless startup smoke test verifies the main window.

All pull-request-quality changes must pass formatting, static analysis, unit tests, integration tests, and the GUI smoke test.

## 11. Performance and usability targets

- A valid 50-component circuit with 1,000 samples should normally refresh in under 250 ms on the development Mac after the 150 ms debounce.
- Pan, zoom, dragging, and slider feedback should remain visually smooth while simulation runs in the background.
- A new user should be able to build a resistor circuit and see current and power within one minute without reading documentation.
- The UI must remain legible at common macOS laptop resolutions and support keyboard focus for essential controls.

## 12. GitHub portfolio deliverables

The repository will include:

- a concise English README with an animated demonstration;
- a mathematical-method section explaining MNA and transient integration;
- architecture and circuit-data diagrams;
- reproducible installation and packaging instructions;
- example circuits for resistor, RC, RL, and RLC responses;
- a test badge and documented verification commands;
- screenshots and exported plots; and
- a short limitations and future-work section that distinguishes completed work from planned work.

The history should use focused commits that make the design and personal technical contribution easy to review.

## 13. Acceptance criteria for Version 1

Version 1 is complete when a user can start from the battery, drag any number of supported components into series or parallel positions, edit their values, and receive a physically consistent transient solution without restarting the application. Each component must show time-cursor voltage and current on the canvas; the selected component must expose plots and a table; total source current and power must update; invalid circuits must be explained; circuits must save and reload; and the analytical solver tests must pass.

## 14. Future releases

The preferred next release adds a sinusoidal source, phasor analysis, impedance, resonance sweeps, and Bode plots. Later releases may add nonlinear components and unrestricted wiring only after the linear solver, UI interaction model, and test suite are mature.
