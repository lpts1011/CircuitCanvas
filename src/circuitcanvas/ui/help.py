"""Built-in help: quick start guide, keyboard shortcuts, and About."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from circuitcanvas import __version__

REPOSITORY_URL = "https://github.com/lpts1011/CircuitCanvas"

_STYLE = """
<style>
  body { font-family: Arial, sans-serif; color: #172033; line-height: 1.45; }
  h2 { margin: 4px 0 8px 0; }
  h3 { margin: 16px 0 6px 0; color: #334155; }
  li { margin-bottom: 5px; }
  code { background: #f1f5f9; padding: 1px 4px; }
  td { padding: 4px 14px 4px 0; vertical-align: top; }
  .muted { color: #64748b; }
</style>
"""

QUICK_START_HTML = (
    _STYLE
    + """
<h2>Build your first circuit</h2>
<ol>
  <li><b>Add a component.</b> Click <i>Resistor</i>, <i>Capacitor</i> or <i>Inductor</i>
  on the left. It is placed in series where there is room, and the loop grows when it
  gets crowded. You can also drag it onto the exact wire you want.</li>
  <li><b>Set its value.</b> Double-click the component, or select it and use the
  <i>Details</i> panel on the right. Type values such as <code>4.7k</code>,
  <code>10u</code> or <code>4k7</code>, or drag the slider.</li>
  <li><b>Watch it work.</b> Press <b>Play</b> at the top, or drag the time slider next to
  it. Every component shows its voltage (blue) and current (orange) at that moment, and
  the graphs below the canvas show the whole response over time.</li>
</ol>

<h3>Wiring by hand</h3>
<ul>
  <li>Drag from a terminal dot (orange = not connected yet) towards another dot or a wire.
  The wire snaps on when you get close and the target turns <b>green</b>; release there.
  Releasing anywhere else adds nothing, and Esc cancels.</li>
  <li>Ending on a wire joins it with a junction dot. Wires that merely cross are
  <i>not</i> connected.</li>
  <li>A wire with a loose end shows an orange dot there: drag that dot onto a dot or a
  wire to finish it. Shift-drag a junction dot to start a new wire from it. Double-click
  a wire to add a bend that you can drag.</li>
  <li><b>Parallel copy</b> (in the Details panel, or right-click) adds a copy of the
  selected component side by side with it, already wired.</li>
  <li>Select anything and press <b>Delete</b> to remove it, or right-click it for more
  choices. Deleting a component in series closes the wire behind it, so the circuit
  stays complete. Every edit can be undone.</li>
</ul>

<h3>Understanding what you see</h3>
<ul>
  <li><b>Time span</b>: <i>Auto</i> simulates long enough for capacitors to charge and
  inductor currents to settle (about five time constants). Type your own value to
  override it.</li>
  <li><b>Kirchhoff's laws tab</b>: the current law (KCL) for every junction, the voltage
  law (KVL) for every loop, and each component's own law, with the solved numbers
  filled in. ✓ means the equation balances.</li>
  <li>If the circuit cannot be solved, a message above the circuit says what to fix and
  the component that causes it is outlined in red.</li>
</ul>

<h3>Moving around</h3>
<p>Scroll to pan. Zoom with ⌘/Ctrl + scroll or a trackpad pinch. ⌘/Ctrl 0 fits the whole
circuit. For ready-made circuits, choose <b>File ▸ Open Example</b>.</p>
"""
)

_GESTURES = (
    ("Click a palette button", "Add that component in series"),
    ("Drag a palette button onto a wire", "Insert the component there"),
    ("Drag from a terminal dot", "Draw a wire"),
    ("Drag an orange loose wire end", "Continue that wire"),
    ("Shift + drag a junction dot", "Draw a wire from a junction"),
    ("Double-click a wire", "Add a draggable bend"),
    ("Double-click a component", "Edit its value"),
    ("Double-click the battery", "Edit the battery voltage"),
    ("Scroll / two-finger swipe", "Pan the canvas"),
    ("⌘/Ctrl + scroll, or pinch", "Zoom"),
)


def shortcuts_html(actions: Iterable[QAction]) -> str:
    """Build the shortcut table from the live actions so it never goes stale."""
    rows = []
    for action in actions:
        shortcuts = [
            shortcut.toString(QKeySequence.SequenceFormat.NativeText)
            for shortcut in action.shortcuts()
            if not shortcut.isEmpty()
        ]
        if shortcuts:
            name = action.text().replace("&", "").rstrip("…").rstrip(".")
            rows.append((" or ".join(shortcuts), name))
    keyboard = "".join(f"<tr><td><b>{escape(k)}</b></td><td>{escape(v)}</td></tr>" for k, v in rows)
    mouse = "".join(
        f"<tr><td><b>{escape(k)}</b></td><td>{escape(v)}</td></tr>" for k, v in _GESTURES
    )
    return (
        _STYLE
        + "<h2>Keyboard shortcuts</h2><table>"
        + keyboard
        + "</table><h3>Mouse and trackpad</h3><table>"
        + mouse
        + "</table>"
    )


ABOUT_HTML = (
    _STYLE
    + f"""
<h2>CircuitCanvas {escape(__version__)}</h2>
<p>An interactive RLC circuit builder and time-domain simulator.</p>
<p class="muted">Circuits are solved with Modified Nodal Analysis and implicit
trapezoidal integration, with no external simulator.</p>
<p>Released under the MIT License.<br>
<a href="{REPOSITORY_URL}">{REPOSITORY_URL}</a></p>
"""
)


class HelpDialog(QDialog):
    """A small non-modal window that shows rich help text."""

    def __init__(self, title: str, html: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 620)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(html)
        layout.addWidget(self.browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
