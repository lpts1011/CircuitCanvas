"""CircuitCanvas application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def configure_application(app: QApplication) -> None:
    app.setApplicationName("CircuitCanvas")
    app.setOrganizationName("Peichi Li")
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QMainWindow, QWidget { background:#f8fafc; color:#172033; font-family:Arial; }
        QToolBar { background:#172033; color:white; border:0; padding:6px; spacing:5px; }
        QToolButton {
            color:#e2e8f0; background:transparent;
            padding:7px 10px; border-radius:7px;
        }
        QToolButton:hover { background:#2a3853; }
        #sidebar { background:white; border-left:1px solid #dbe2ea; }
        QLineEdit, QComboBox, QDoubleSpinBox {
            background:white; border:1px solid #cbd5e1;
            border-radius:7px; padding:7px;
        }
        QPushButton {
            background:white; border:1px solid #cbd5e1;
            border-radius:7px; padding:8px;
        }
        QPushButton:hover { background:#f1f5f9; }
        QTabWidget::pane { border:1px solid #e2e8f0; background:white; }
        QTabBar::tab { padding:7px 14px; background:#f1f5f9; }
        QTabBar::tab:selected { background:white; color:#2563eb; }
        """
    )


def main() -> int:
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication(sys.argv)
    configure_application(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
