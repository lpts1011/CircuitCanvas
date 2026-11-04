"""CircuitCanvas application entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QFileOpenEvent, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.theme import ACCENT, STYLESHEET, SURFACE, TEXT, WINDOW


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
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(WINDOW))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)


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
