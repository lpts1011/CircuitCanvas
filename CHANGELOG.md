# Changelog

## 0.4.0

The "usable by anyone" release: CircuitCanvas now explains itself, picks sensible
simulation settings, protects your work, and ships as a downloadable app.

### New

- **Download and run** without Python: a macOS (Apple silicon) app and a Windows app are
  built for every release, plus a Python wheel for everything else.
- **Automatic time span.** The simulation covers about five of the circuit's slowest time
  constants, so an RC with τ = 10 s is simulated for 50 s instead of 0.1 s. Type your own
  span (`200 ms`, `2 s`) to override it.
- **Type values the way engineers write them:** `4.7k`, `10u`, `4k7`, `2.2 MΩ`, `330 ohm`.
- **Double-click to edit:** a component opens its value; the battery opens its voltage.
- **Menu bar** with File, Edit, View, and Help, including **File → Open Example** with five
  ready-made circuits and **Help → Quick Start Guide** (F1) and **Keyboard Shortcuts**.
- **"Start here" card** on an empty circuit, and tooltips on every control and canvas item.
- **Delete anything:** wires, junction dots, and wire bends, not only components.
- **Save As**, a file name in the title bar, and a prompt before New, Open, or Quit
  discards unsaved changes.
- **Export CSV** with nothing selected saves every component in one table.
- **Fit view** (⌘/Ctrl 0) and zoom shortcuts; the whole circuit is shown when a file opens.
- An app icon, and double-clicking a saved `.circuitcanvas` file in Finder opens it.

### Changed

- **A clearer layout.** Components to add are on the left, the circuit in the middle, and a
  Details panel on the right shows either the whole circuit or the selected component with
  large voltage, current, power, and energy readings. Graphs fill the bottom, with voltage and
  current in separate plots. Play and a time slider sit at the top with the current moment
  ("t = 10 ms of 50 ms"); the canvas, readings, graphs, and laws all follow it, and the dashed
  line on a graph can be dragged too.
- Voltage is always blue and current always orange, on the canvas and in the graphs.
- Play runs the whole time span in about six seconds (adjustable) and stops at the end; before,
  1× was real time, so a 25 ms circuit finished before you could see it.
- When the circuit cannot be solved, a plain-language message appears above it, the component
  causing it is outlined in red, and stale numbers and graphs are hidden.
- Right-click menus on components, wires, junctions, bends, the battery, and empty canvas.
- Dropping a component near a wire inserts it there (the target wire glows while you drag), and dragging a loose component onto a wire connects it.
- Kirchhoff's laws have readable names (Junction 1, Loop 1, R1: Ohm's law).
- Icons in the toolbar, symbols on the component buttons, a light theme, the system font, and
  upright labels on rotated components.
- Scrolling or a two-finger swipe now pans the canvas. Zoom with ⌘/Ctrl + scroll or a pinch;
  zoom is limited to 20–400 % so the circuit can no longer shrink out of sight.
- Values are shown with SI prefixes everywhere (`10 kΩ`, `4.7 nF`, `1.188 mA`) instead of
  `10000 Ω`, `2.2e+06 Ω`, or `6.969e-11 A`.
- One slider drag, or one battery-voltage edit, is a single undo step. The battery voltage and
  the time span are now part of undo history.
- Bundled examples were redrawn as tidy loops and live inside the package.

### Fixed

- The Inspector's **Rotate** button did nothing.
- Every recalculation made the Equations panel select components on the canvas, so Delete or
  Rotate could act on components you never chose. Equation highlighting is now a separate
  outline, shown only on the Equations tab.
- Adding a component left the previously selected one selected too, so the Inspector could
  edit the wrong component and Delete removed both.
- The Inspector kept showing a component after it was deselected.
- On startup the battery was outside the visible canvas.
- Clicking a component marked the circuit as changed and added an undo step.
- The window could open larger than a small screen.
- Saving or exporting to a location that cannot be written crashed instead of showing a message.

## 0.3.1

- Delete or Backspace removes the selected component.

## 0.3.0

- Start from an editable closed loop; wires follow horizontal, vertical, or 45° paths.

## 0.2.0

- Free wiring with junctions, Kirchhoff equation browser, and animated current arrows.
