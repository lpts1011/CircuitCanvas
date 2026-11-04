"""Check that a built CircuitCanvas executable starts and keeps running.

    QT_QPA_PLATFORM=offscreen python scripts/smoke_test_app.py dist/CircuitCanvas/CircuitCanvas.exe

A frozen app that is missing a library or data file usually exits within a
second or two, so staying alive for a few seconds is a useful first check.
"""

from __future__ import annotations

import subprocess
import sys

STARTUP_SECONDS = 8.0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    process = subprocess.Popen(
        [sys.argv[1]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        process.wait(timeout=STARTUP_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        print(f"OK: {sys.argv[1]} was still running after {STARTUP_SECONDS:g} s")
        return 0
    output = process.stdout.read() if process.stdout is not None else ""
    print(output)
    print(f"FAILED: {sys.argv[1]} exited early with code {process.returncode}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
