from pathlib import Path

from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from circuitcanvas.app import (
    FileOpenHandler,
    application_icon,
    configure_application,
    paths_from_arguments,
)
from circuitcanvas.domain.serialization import save_circuit
from circuitcanvas.examples import EXAMPLES, load_example


def _saved_example(tmp_path: Path) -> Path:
    path = tmp_path / "rc.circuitcanvas"
    save_circuit(path, load_example(next(e for e in EXAMPLES if e.filename == "rc-charge.json")))
    return path


def test_application_icon_is_bundled(qapp) -> None:
    icon = application_icon()

    assert not icon.isNull()
    configure_application(qapp)
    assert not qapp.windowIcon().isNull()


def test_command_line_paths_skip_macos_process_serial_number() -> None:
    arguments = ["CircuitCanvas", "-psn_0_12345", "my circuit.circuitcanvas"]

    assert paths_from_arguments(arguments) == [Path("my circuit.circuitcanvas")]


def test_finder_file_open_event_opens_the_circuit(qtbot, tmp_path) -> None:
    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    handler = FileOpenHandler(window)
    path = _saved_example(tmp_path)

    QApplication.instance().installEventFilter(handler)
    try:
        QApplication.sendEvent(QApplication.instance(), QFileOpenEvent(str(path)))
    finally:
        QApplication.instance().removeEventFilter(handler)

    assert set(window.circuit.components) == {"R1", "C1"}
    assert window.windowTitle().startswith("rc.circuitcanvas")


def test_open_document_respects_cancel_on_unsaved_changes(qtbot, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    from circuitcanvas.ui.main_window import MainWindow

    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("inductor")
    monkeypatch.setattr(window, "_ask_save_changes", lambda: QMessageBox.StandardButton.Cancel)

    assert not window.open_document(_saved_example(tmp_path))

    assert component_id in window.circuit.components
