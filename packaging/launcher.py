"""Entry point for the packaged palm-lab executable.

PyInstaller needs a script to start from. This one runs the normal CLI, and if
the app fails after being double-clicked, keeps the console window open long
enough to read why. Without that, Windows closes the window the instant the
process exits and the error disappears with it.
"""

import contextlib
import sys
import traceback

from palm_lab.cli import main


def _launched_by_double_click() -> bool:
    return bool(getattr(sys, "frozen", False)) and len(sys.argv) == 1


def run() -> int:
    try:
        code = main()
    except Exception:
        traceback.print_exc()
        code = 1
    if code and _launched_by_double_click():
        # EOFError means there is no console to read from; nothing to wait for.
        with contextlib.suppress(EOFError):
            input("\npalm-lab stopped with an error. Press Enter to close...")
    return code


if __name__ == "__main__":
    raise SystemExit(run())
