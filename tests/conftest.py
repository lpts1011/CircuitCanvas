import pytest


@pytest.fixture(autouse=True)
def _discard_unsaved_changes_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Closing a window with edits would otherwise open a modal save prompt and hang."""
    from PySide6.QtWidgets import QMessageBox

    from circuitcanvas.ui.main_window import MainWindow

    monkeypatch.setattr(
        MainWindow, "_ask_save_changes", lambda self: QMessageBox.StandardButton.Discard
    )
