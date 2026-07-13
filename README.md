# CircuitCanvas

**An interactive RLC circuit builder and time-domain simulator.** Drag resistors, capacitors, and inductors into a battery-powered circuit, edit their values, and watch every voltage, current, power, and stored-energy result update automatically.

![CircuitCanvas showing an underdamped RLC transient](docs/images/circuitcanvas-main.png)

## Why this project exists

CircuitCanvas connects three subjects that are often taught separately:

- circuit theory and Kirchhoff's laws;
- differential equations and numerical integration; and
- interactive software engineering.

The application does not call an external circuit simulator. Its Python solver assembles a Modified Nodal Analysis system for the circuit and integrates the resulting linear descriptor equation over time.

## Highlights

- Smart-snap circuit canvas with a battery and expandable series/parallel layout
- Repeated addition of any practical number of R, C, and L components
- Direct value entry, SI units, and logarithmic parameter sliders
- Live voltage and current labels next to every component
- RC, RL, and RLC transient simulation after every edit
- Independent voltage and current axes with a shared time cursor
- Data table for time, voltage, current, power, and stored energy
- Circuit totals for source current, source power, and reactive energy
- Versioned JSON save/load plus CSV and PNG export
- Undo/redo and revision-safe background calculation
- Specific diagnostics for open, floating, singular, and non-finite circuits
- Analytical tests against closed-form RC and RL solutions

## Install and run

CircuitCanvas requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
circuitcanvas
```

On Windows, activate the environment with `.venv\Scripts\activate` before running the remaining commands.

## Build a circuit

1. Start with the battery and open drop target.
2. Drag a component onto the top wire, or click its palette card, to insert it in series.
3. Drop a component below an existing one to create a parallel branch.
4. Repeat the operation to add more components; the canvas expands automatically.
5. Select a component and type a value or move its logarithmic slider.
6. Drag the time cursor under the graph to inspect all on-canvas values at the same instant.
7. Use **Data table**, **Export CSV**, or **Export PNG** to keep the result.

Four ready-to-run circuits are included in [`examples/`](examples): resistor, RC charge, RL step, and underdamped RLC.

## Mathematical model

The solver forms the Modified Nodal Analysis equation

\[
Gx(t)+C\dot{x}(t)=b(t),
\]

where the state contains non-ground node voltages and auxiliary currents for the ideal source and inductors. The battery is a step input at \(t=0\), capacitor voltage begins at zero, and inductor current begins at zero.

The default integrator is the implicit trapezoidal rule:

\[
\left(G+\frac{2C}{\Delta t}\right)x_{k+1}
=\left(\frac{2C}{\Delta t}-G\right)x_k+b_{k+1}+b_k.
\]

Backward Euler is also supported. Matrix factorizations are reused across fixed steps. See [the mathematical notes](docs/mathematics.md) for component stamps, sign conventions, and verification equations.

## Architecture

```text
PySide6 interaction
       ↓ atomic command
Circuit graph + revision
       ↓ immutable snapshot
Validation → MNA assembly → transient integration
       ↓ revision check
Canvas labels + plots + table + exports
```

The domain and solver packages have no Qt dependencies, which keeps the numerical core easy to test and reusable. Background results carry the circuit revision that produced them, so a slow older simulation cannot overwrite a newer edit. See [the architecture notes](docs/architecture.md) for module boundaries and data flow.

## Verify the project

```bash
ruff format --check .
ruff check .
mypy src
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m build
```

The suite covers domain validation, repeated graph edits, persistence, MNA stamps, analytical transients, conservation residuals, GUI interaction, stale background results, exports, and example circuits.

## Create the macOS application

```bash
pyinstaller --noconfirm circuitcanvas.spec
open "dist/CircuitCanvas.app"
```

The source remains Windows-compatible; a Windows executable can be built from the same spec on Windows.

## Current scope

Version 1 models one ideal DC source and linear R, C, and L components in circuits constructed through repeated series and parallel operations. It intentionally does not claim support for diodes, transistors, arbitrary freehand wiring, multiple sources, or frequency-domain analysis.

The next mathematically coherent extension is a sinusoidal source with impedance, phasors, resonance sweeps, and Bode plots.

## License

Released under the [MIT License](LICENSE).

