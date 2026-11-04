"""CircuitCanvas application entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QFileOpenEvent, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def application_icon() -> QIcon:
    pixmap = QPixmap()
    pixmap.loadFromData(files("circuitcanvas.resources").joinpath("icon.png").read_bytes())
    return QIcon(pixmap)


def paths_from_arguments(arguments: Sequence[str]) -> list[Path]:
    """Circuit files named on the command line (macOS may add a -psn_… argument)."""
    return [Path(argument) for argument in arguments[1:] if not argument.startswith("-")]


class FileOpenHandler(QObject):
    """Open circuits that macOS sends when a file is double-clicked in Finder."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FileOpen and isinstance(event, QFileOpenEvent):
            if event.file():
                self.window.open_document(Path(event.file()))
            return True
        return super().eventFilter(watched, event)


def configure_application(app: QApplication) -> None:
    app.setApplicationName("CircuitCanvas")
    app.setOrganizationName("Peichi Li")
    app.setStyle("Fusion")
    app.setWindowIcon(application_icon())
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


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv if argv is None else argv)
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication(arguments)
    configure_application(app)
    window = MainWindow()
    app.installEventFilter(FileOpenHandler(window))
    window.show()
    for path in paths_from_arguments(arguments)[:1]:
        window.open_document(path)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
