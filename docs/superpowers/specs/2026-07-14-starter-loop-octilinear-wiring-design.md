# Starter Loop and Octilinear Wiring Design

## Goal

CircuitCanvas opens with the battery already connected to a visible rectangular construction loop. A user can place a component directly on that loop to insert it in series, or place a component elsewhere and connect it across two points to form a parallel branch. Every visible wire segment is horizontal, vertical, or exactly 45 degrees. Electrical junctions and route handles remain attached to existing wire geometry when moved.

## Approaches considered

### 1. Draw a decorative loop that is not electrically connected

This avoids an initial source short, but the picture would disagree with the solver. It violates the project's rule that visible connectivity is authoritative and is rejected.

### 2. Start with an ideal-wire loop and require manual wire deletion

This is electrically honest, but CircuitCanvas does not currently offer a natural wire-deletion-and-reconnection workflow. A beginner would see a short circuit and have no obvious way to insert the first component. It is rejected.

### 3. Start with a real construction loop and let component placement replace a wire span

This is the selected approach. The empty loop is an explicit ideal short, so simulation is paused with an instructional diagnostic. Dropping or quick-adding the first component on a loop segment atomically removes that conductive span and reconnects the two sides through the component. The resulting circuit is a valid series loop. Further components may be inserted on any wire or wired manually in parallel.

## Starter circuit

`Circuit.starter_loop(voltage)` creates the UI's initial model without changing the meaning of `Circuit.new()`, which remains useful for solver and legacy tests.

The starter model contains:

- the existing vertical battery at the left;
- an upper-right and lower-right junction;
- a top wire from the positive battery terminal to the upper-right junction;
- a right vertical wire between the two junctions; and
- a bottom wire from the lower-right junction to the negative terminal.

Together with the battery, these wires form the visible rectangular loop. The solver reports a source-short diagnostic until a component replaces part of the loop. The UI translates that diagnostic into a direct instruction to place a component on a wire.

Reset creates the same starter loop. `Circuit.new()` and saved legacy examples retain their existing behavior.

## Series insertion on a wire

The palette supports two placement paths:

- dropping a component on a `WireItem` inserts it at that location; and
- clicking a palette component inserts it near the middle of the best available construction-loop segment.

Insertion is one undoable domain command. It removes the selected wire, creates the component, and creates two replacement wires from the old endpoints to the component terminals. Horizontal segments produce horizontal components, vertical segments produce 90-degree components, and 45-degree segments use a horizontal component with octilinear connector routes. No hidden ideal-wire bypass remains.

Dropping away from a wire continues to create a loose component for manual parallel wiring. Existing terminal-to-terminal and terminal-to-wire connection gestures remain available.

## Octilinear geometry

A new Qt-independent routing module owns the geometry rules:

- `is_octilinear(a, b)` accepts only horizontal, vertical, or absolute-slope-one segments;
- `project_to_octilinear(origin, point)` projects a free pointer position onto the nearest permitted axis through `origin`;
- `octilinear_route(start, end)` returns a direct segment when already aligned, otherwise a deterministic one-bend route made from a 45-degree segment plus a horizontal or vertical segment; and
- `project_to_polyline(point, points)` returns the nearest point on existing wire geometry.

`WireItem` constructs its painter path only from these primitives. If a loaded route or a moved component makes a stored segment invalid, the renderer inserts a deterministic octilinear bend. It never draws an arbitrary-angle fallback segment.

## Node and handle constraints

There are two draggable point types:

- route handles are projected onto the wire polyline they already belong to before their position is committed; and
- electrical junctions are projected onto the nearest incident wire polyline from the pre-drag circuit state.

Therefore a point may slide along wire geometry but cannot be committed in empty space. Connected branches remain electrically attached. After a constrained point moves, every incident wire is rebuilt through the octilinear router, so all resulting segments still satisfy the allowed-angle rule.

Double-clicking a wire adds a route handle at the nearest projected point on that wire, not at the unrestricted pointer coordinate.

## Wire creation preview

While a user drags from a terminal or Shift-drags from a junction, the preview endpoint is projected to the nearest horizontal, vertical, or 45-degree axis. Releasing on empty space creates a junction at that snapped location. Releasing on an existing terminal, junction, or wire uses the exact target and inserts a deterministic octilinear bend when direct alignment is impossible.

## Persistence and compatibility

The existing schema already stores junction positions and route points, so no schema bump is required. New saves contain only constrained route geometry. Older schema-2 files remain loadable; any nonconforming stored segment is normalized for display and on the next related edit. Electrical connectivity is unchanged by route normalization.

## Error handling

- The starter short is expected and produces an instructional status instead of a generic singular-circuit message.
- A series insertion rejects a missing or stale wire ID without partially changing the circuit.
- Degenerate zero-length route segments are removed.
- A junction with no usable incident segment stays at its last committed position.

## Testing

Tests cover:

- starter-loop topology and source-short diagnosis;
- atomic series insertion removing the direct wire path and supporting undo/redo;
- palette click and drop-on-wire behavior;
- horizontal, vertical, and both 45-degree projections;
- deterministic routes for arbitrary endpoint pairs;
- every painted path segment satisfying the allowed-angle predicate;
- route handles and junctions projecting back onto their existing wire geometry;
- saved-circuit compatibility;
- the existing 17 V parallel-series Kirchhoff fixture; and
- full Ruff, mypy, pytest, package-build, macOS-app launch, and GitHub CI verification.
