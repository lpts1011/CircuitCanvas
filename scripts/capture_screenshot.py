"""Render a deterministic portfolio screenshot with the bundled RLC example."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from circuitcanvas.app import configure_application
from circuitcanvas.domain.serialization import load_circuit
from circuitcanvas.ui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    configure_application(app)
    window = MainWindow(debounce_ms=0)
    window._replace_circuit(load_circuit("examples/rlc-underdamped.json"))
    window.scene.component_items["C1"].setSelected(True)
    window.show()

    def capture() -> None:
        target = Path("docs/images/circuitcanvas-main.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        window.repaint()
        app.processEvents()
        if not window.grab().save(str(target)):
            raise RuntimeError(f"Could not save {target}")
        app.quit()

    QTimer.singleShot(2500, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
