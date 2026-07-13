"""Render a deterministic portfolio screenshot with a Kirchhoff branch example."""

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
    window.resize(1600, 960)
    window._replace_circuit(load_circuit("examples/parallel-series-17v.json"))
    window.scene.component_items["R1"].setSelected(True)
    window.sidebar_tabs.setCurrentWidget(window.equations)
    window.show()

    def prepare_capture() -> None:
        window.view.horizontalScrollBar().setValue(0)
        window.view.verticalScrollBar().setValue(0)
        QTimer.singleShot(300, capture)

    def capture() -> None:
        target = Path("docs/images/circuitcanvas-main.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        window.repaint()
        app.processEvents()
        if not window.grab().save(str(target)):
            raise RuntimeError(f"Could not save {target}")
        app.quit()

    QTimer.singleShot(2200, prepare_capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
