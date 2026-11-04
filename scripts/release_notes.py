"""Print GitHub release notes for one version: its CHANGELOG section plus install steps.

python scripts/release_notes.py 0.4.0 > notes.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INSTALL_NOTES = """
## Download and open

**Mac with Apple silicon (M1 or newer):** `CircuitCanvas-{version}-macOS-AppleSilicon.zip`

1. Unzip it and drag **CircuitCanvas** into Applications.
2. Open it. The app is not notarized by Apple, so the first time macOS says it cannot
   verify the developer. Open **System Settings → Privacy & Security** and click
   **Open Anyway**.

**Windows 10 or 11 (64-bit):** `CircuitCanvas-{version}-Windows-x64.zip`

1. Unzip the whole folder (do not run the app from inside the zip).
2. Run **CircuitCanvas.exe**. If SmartScreen appears, click **More info → Run anyway**.

**Intel Mac, Linux, or anything else:** `circuitcanvas-{version}-py3-none-any.whl`

With Python 3.12 or newer, run `python -m pip install circuitcanvas-{version}-py3-none-any.whl`,
then start the app with `circuitcanvas`.

New to the app? Choose **Help → Quick Start Guide**, or **File → Open Example**.
"""


def changelog_section(changelog: str, version: str) -> str:
    """Return the body under the ``## <version>`` heading, up to the next ``## `` heading."""
    pattern = rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, changelog, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise SystemExit(f"CHANGELOG.md has no section for version {version}")
    return match.group(1).strip()


def release_notes(changelog: str, version: str) -> str:
    return changelog_section(changelog, version) + "\n" + INSTALL_NOTES.format(version=version)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    print(release_notes(Path("CHANGELOG.md").read_text(encoding="utf-8"), sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
