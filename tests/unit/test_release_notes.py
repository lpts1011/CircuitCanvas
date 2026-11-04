import importlib.util
from pathlib import Path

import circuitcanvas

ROOT = Path(__file__).resolve().parents[2]


def _release_notes_module():
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "scripts/release_notes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changelog_has_a_section_for_the_current_version() -> None:
    module = _release_notes_module()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    notes = module.release_notes(changelog, circuitcanvas.__version__)

    assert "Automatic time span" in notes
    assert f"CircuitCanvas-{circuitcanvas.__version__}-Windows-x64.zip" in notes
    assert "## 0.3.1" not in notes


def test_section_stops_at_the_next_version() -> None:
    module = _release_notes_module()
    changelog = "# Changelog\n\n## 2.0.0\n\n- new\n\n## 1.0.0\n\n- old\n"

    assert module.changelog_section(changelog, "2.0.0") == "- new"
    assert module.changelog_section(changelog, "1.0.0") == "- old"
