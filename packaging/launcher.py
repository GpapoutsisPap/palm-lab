"""Entry point for the packaged palm-lab programs.

The build makes two programs from this one script:

- palm-lab.exe is the app. It has no console window, so anything it would
  print goes to a log file, and a failure to start is shown in a dialog that
  says where that log is.
- palm-lab-cli.exe has a console, for commands such as `palm-lab-cli doctor`.
  If it fails after a double-click, the console stays open long enough to read
  why; otherwise Windows closes it the instant the process exits.
"""

import contextlib
import sys
import traceback
from datetime import datetime
from pathlib import Path

from palm_lab.cli import main
from palm_lab.config import log_dir
from palm_lab.windows import show_error

LOG_FILENAME = "palm-lab.log"
LOG_LIMIT_BYTES = 1_000_000


def _has_console() -> bool:
    # A windowed PyInstaller build starts with no standard streams at all.
    return sys.stdout is not None


def _launched_by_double_click() -> bool:
    return bool(getattr(sys, "frozen", False)) and len(sys.argv) == 1


def _send_output_to_log() -> Path:
    """Point stdout and stderr at the log file, starting afresh when it gets big."""
    folder = log_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOG_FILENAME
    mode = "w" if path.exists() and path.stat().st_size > LOG_LIMIT_BYTES else "a"
    # Deliberately left open: it is the program's output for as long as it runs.
    stream = open(path, mode, encoding="utf-8", buffering=1)  # noqa: SIM115
    stream.write(f"\n--- palm-lab started {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
    sys.stdout = sys.stderr = stream
    return path


def run() -> int:
    log = None if _has_console() else _send_output_to_log()
    try:
        code = main()
    except Exception:
        traceback.print_exc()
        code = 1
    if code and log is not None:
        show_error(
            "palm-lab",
            f"palm-lab stopped because of a problem.\n\nThe details are in:\n{log}",
        )
    elif code and _launched_by_double_click():
        # EOFError means there is no console to read from; nothing to wait for.
        with contextlib.suppress(EOFError):
            input("\npalm-lab stopped with an error. Press Enter to close...")
    return code


if __name__ == "__main__":
    raise SystemExit(run())
