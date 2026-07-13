# CircuitCanvas Free Wiring and Kirchhoff Visualization Design

**Date:** 2026-07-13

**Status:** Approved for autonomous implementation

**Supersedes:** The smart-snap-only interaction and the exclusion of arbitrary wire routing in the original Version 1 specification

## 1. Objective

Upgrade CircuitCanvas from a series/parallel smart-snap editor into a free-form circuit editor whose diagram, simulation, Kirchhoff equations, and current animation all come from the same electrical topology.

The feature is successful when a user can freely construct circuits such as a resistor `R3` connected in parallel with the complete series branch `R1 + R2`, inspect the resulting KCL and KVL equations, switch between ordinary and differential forms, and see current direction animated on every connected wire without violating Kirchhoff's laws.

## 2. Selected approach

CircuitCanvas will use an explicit terminal-junction-wire graph.

This was selected over:

- a nested series/parallel expression tree, which cannot represent arbitrary bridge and multi-loop circuits; and
- visual-only free wires over the existing commands, which could make the displayed diagram disagree with the solver.

The electrical graph is authoritative. Screen coordinates affect layout and wire routing only; they never imply connectivity by proximity alone.

## 3. Interaction design

### 3.1 Components and terminals

- A palette drop creates a freely movable component at the drop position.
- Every resistor, capacitor, and inductor exposes two circular terminals.
- The battery exposes positive and negative terminals.
- Components may be moved and rotated in 90-degree steps.
- Moving or rotating a component preserves its electrical connections and reroutes the attached wire endpoints.
- A disconnected terminal is orange; a connected terminal is blue; the currently targeted terminal is green.

### 3.2 Creating and editing wires

- Pressing and dragging from a terminal starts a wire preview.
- Releasing on another terminal connects the two terminals.
- Releasing on an existing wire inserts a junction and connects to it.
- Releasing on empty canvas creates a dangling junction and incomplete wire that may be completed later.
- Wires use orthogonal segments by default.
- Double-clicking a wire segment adds a route point.
- Route points and complete segments are draggable while preserving orthogonal geometry.
- Clicking a wire or route point selects it; Delete removes the selected connection or point.
- A junction dot appears where three or more conductive segments meet. Crossing lines without a junction dot are not connected.
- A short drag that ends on its starting electrical net is rejected when it would create a meaningless zero-length connection.

To create `R3 || (R1 + R2)`, the user connects one `R3` terminal to the node before `R1` and the other terminal to the node after `R2`. No special parallel command is required.

### 3.3 Selection and history

- Component moves, rotations, wire creation, wire splitting, junction movement, route edits, and deletion are undoable.
- Continuous drags are coalesced into one undo step.
- Existing value editing, plots, export, pan, and zoom remain available.

## 4. Domain model

The domain layer gains explicit wiring objects with no Qt dependencies:

- `TerminalRef`: a stable reference to component/source ID plus terminal `a` or `b`.
- `Junction`: a stable ID and canvas position.
- `Wire`: a stable ID, two endpoint references, and zero or more orthogonal route points.
- `Netlist`: the derived mapping from every terminal and junction to an electrical node.

The circuit retains component positions and adds component rotations. Visual wire route points are serializable but do not directly enter the MNA matrices.

### 4.1 Connectivity derivation

On every topology edit, a connectivity builder uses union-find over terminals and junctions joined by wire edges. Each connected conductor set becomes one stable electrical node. Component and source terminal nodes in the immutable solver snapshot are derived from this map.

Deleting a wire recomputes connected components instead of attempting to undo a previous node merge. This makes disconnect and branch-splitting behavior reliable.

### 4.2 Compatibility

The save format advances from schema version 1 to version 2 and includes wires, junctions, positions, and rotations. Loading a version 1 circuit synthesizes junctions and wires from the saved node memberships and positions, preserving the original electrical behavior. Version 2 results remain computed state and are never trusted from disk.

## 5. Kirchhoff equation engine

A new solver-independent equation layer consumes the same immutable snapshot and simulation result used by the canvas.

### 5.1 Ordinary mode

Ordinary mode shows three lines for each equation:

1. the symbolic equation;
2. the equation with values substituted at the active time sample; and
3. the evaluated result and residual.

It contains:

- one independent KCL equation for every non-reference electrical node;
- a cycle-basis set of independent KVL equations;
- branch voltage/current definitions; and
- the passive sign convention used by every component.

Example:

```text
KCL N1: I_R1 - I_R2 - I_R3 = 0
         0.170 - 0.085 - 0.085 = 0
         residual = 2.1e-12 A
```

### 5.2 Differential mode

Differential mode expands the constitutive laws:

```text
v_R(t) = R i_R(t)
i_C(t) = C dv_C(t)/dt
v_L(t) = L di_L(t)/dt
```

It then displays the assembled descriptor equation

```text
C x_dot(t) + G x(t) = b(t)
```

with variable definitions and matrices for the active circuit. A scalar explicit ODE is shown only when the topology can be reduced without losing information. General RLC circuits remain differential-algebraic systems, and the UI labels them accurately rather than pretending every network has one scalar ODE.

### 5.3 Equation interaction

- Selecting a KCL equation highlights its node and incident branches.
- Selecting a KVL equation highlights the complete independent loop.
- Selecting a component scrolls to and highlights every equation containing it.
- Moving the time cursor updates numeric substitutions and residuals.
- Residuals inside tolerance are shown with a check mark; failures are red and identify the affected node or loop.

## 6. Current animation

Blue arrow particles move continuously along connected wire paths at a target refresh rate of 60 FPS.

- Direction comes only from signed simulated current at the active time sample.
- A negative result reverses the arrows.
- Speed is a clamped monotonic function of current magnitude.
- Near-zero current stops and fades the arrows.
- DC circuits animate steadily; transient circuits update with playback and the time cursor.
- Pausing time playback pauses value changes while the particles may continue at the current sample's direction and speed.

### 6.1 Wire-segment flow reconstruction

MNA uniquely provides component terminal currents but ideal conductors collapse to electrical nodes, so current inside an ideal wire loop is not always unique. For visualization, each conductor net is expanded back into its wire graph. Component terminal currents become graph injections, and segment flows are obtained from

```text
B f = -q
```

using the minimum-norm solution. This produces a deterministic arrow field that satisfies KCL at every visual junction. The equation panel reports the reconstruction residual. If the terminal injections do not balance within tolerance, arrows for that net are suppressed and the circuit is marked invalid or numerically inconsistent.

The UI labels minimum-norm flow as a visualization convention for ideal-wire loops; it does not claim that an ideal zero-resistance loop has one physically measurable internal current distribution.

## 7. User interface composition

- The central canvas remains the primary workspace.
- The right side becomes a resizable tabbed panel containing Components, Inspector, and Kirchhoff Equations.
- The equation tab contains the Ordinary/Differential toggle, equation tree, symbolic/value/result display, and residual summary.
- The bottom analysis panel keeps plots and the time cursor and adds play/pause and playback speed.
- A compact toolbar provides Select, Wire, Junction, Rotate, Delete, Undo, and Redo actions with keyboard shortcuts.

## 8. Validation and errors

Simulation is blocked, with inline diagnostics, for:

- dangling component terminals;
- wires ending nowhere;
- floating subcircuits;
- a direct ideal-wire short across the battery;
- inconsistent ideal voltage constraints;
- invalid component values;
- singular or non-finite MNA systems; and
- topology references to deleted objects.

Invalid wires and terminals are highlighted in orange or red. The equation panel may still show structural equations, but it clearly labels them incomplete. The last valid numerical result is dimmed and marked stale. Current arrows are never guessed when no valid result exists.

Crossing wires are electrically separate unless an explicit junction is present. Deleting a component leaves attached wire ends dangling so the user can reconnect or delete them; this action remains undoable.

## 9. Data flow

```text
Canvas edit
  -> atomic wiring command
  -> connectivity builder
  -> immutable electrical snapshot
  -> validation
  -> MNA transient solve
  -> Kirchhoff equation evaluation
  -> wire-flow reconstruction
  -> canvas labels, equation panel, plots, and arrows
```

Every stage carries the circuit revision. Results from an older revision are discarded.

## 10. Testing and acceptance criteria

### 10.1 Domain and command tests

- connect two terminals and derive one net;
- split a wire by dropping onto it;
- disconnect a wire and split the net correctly;
- preserve topology while moving and rotating components;
- undo and redo all wiring edits;
- serialize schema version 2 and migrate version 1 files.

### 10.2 Equation tests

- generate independent KCL equations with near-zero residuals;
- generate an independent KVL cycle basis including parallel branches;
- expand resistor, capacitor, and inductor laws correctly;
- match displayed MNA matrices to the solver assembly;
- identify DAE systems without falsely claiming a scalar ODE.

### 10.3 Flow and animation tests

- reconstruct segment currents whose junction residual is below tolerance;
- reverse animation direction when branch current changes sign;
- stop arrows at the zero-current threshold;
- suppress arrows for stale or invalid results;
- keep animation updates separate from expensive re-simulation.

### 10.4 Required integration fixture

Build a 17 V circuit with `R1 = 100 ohm` and `R2 = 100 ohm` in series, and `R3 = 200 ohm` in parallel with the complete `R1 + R2` branch. The application must show:

- the two outer-node connections for `R3`;
- 0.085 A in each 200-ohm branch;
- 0.17 A source current;
- KCL residuals within numerical tolerance;
- zero KVL residual for both independent loops; and
- correctly directed arrows that split equally at the branch and recombine at the return node.

### 10.5 Regression and quality gates

- Existing R, RC, RL, and RLC analytical tests continue to pass.
- Existing value editing, export, plots, and background revision safety continue to work.
- The canvas remains usable with at least 100 components and 200 wire segments.
- Formatting, lint, strict type checking, unit/integration/GUI tests, package build, and macOS launch probe pass before release.

## 11. Scope boundaries

This upgrade does not add nonlinear devices, AC frequency-domain analysis, multiple sources, PCB layout, or electromagnetic wire modelling. The wire animation visualizes currents derived from the ideal lumped-element circuit; it is not a field simulation.
