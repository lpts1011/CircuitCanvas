"""Render the README screenshot: the RLC ringing example with its Kirchhoff equations.

    python scripts/capture_screenshot.py

Renders off screen at 2x so the image stays sharp on high-density displays.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from circuitcanvas.app import configure_application
from circuitcanvas.examples import EXAMPLES
from circuitcanvas.ui.main_window import MainWindow

TARGET = Path("docs/images/circuitcanvas-main.png")


def main() -> int:
    app = QApplication([])
    configure_application(app)
    window = MainWindow(debounce_ms=0)
    window.resize(1500, 900)
    window.show()
    window.open_example(next(item for item in EXAMPLES if item.filename == "rlc-underdamped.json"))

    def prepare_capture() -> None:
        window.sidebar_tabs.setCurrentWidget(window.equations)
        window.scene.select_only("C1")
        window.equations.select_equation("KVL1")
        # A moment during the first swing, so the readings and cursor are interesting.
        result = window.current_result
        if result is not None:
            window.time_bar.slider.setValue(len(result.time) // 6)
        window.statusBar().clearMessage()
        window.view.fit_circuit()
        QTimer.singleShot(300, capture)

    def capture() -> None:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        window.repaint()
        app.processEvents()
        if not window.grab().save(str(TARGET)):
            raise RuntimeError(f"Could not save {TARGET}")
        print(f"Saved {TARGET}")
        window.scene.command_stack.mark_clean()
        app.quit()

    QTimer.singleShot(1500, prepare_capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
