import importlib.util
import re
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

    version = circuitcanvas.__version__
    notes = module.release_notes(changelog, version)

    # The current version's own section, and nothing from the release before it.
    assert module.changelog_section(changelog, version)
    assert notes.startswith(module.changelog_section(changelog, version))
    assert f"CircuitCanvas-{version}-Windows-x64.zip" in notes
    assert not re.search(r"^## \d", notes, flags=re.MULTILINE)


def test_section_stops_at_the_next_version() -> None:
    module = _release_notes_module()
    changelog = "# Changelog\n\n## 2.0.0\n\n- new\n\n## 1.0.0\n\n- old\n"

    assert module.changelog_section(changelog, "2.0.0") == "- new"
    assert module.changelog_section(changelog, "1.0.0") == "- old"
