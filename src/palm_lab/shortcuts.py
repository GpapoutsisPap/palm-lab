"""Desktop and Start menu shortcuts that open palm-lab.

Shortcuts (.lnk files) are made by Windows' own WScript.Shell object through
PowerShell, which ships with every supported Windows. Folder locations come
from Windows too, so a Desktop moved into OneDrive is still found.
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from palm_lab.config import APP_NAME, icon_path, is_frozen

SHORTCUT_FILENAME = f"{APP_NAME}.lnk"
DESCRIPTION = "Trigger shortcuts with hand gestures"

# Where each kind of shortcut lives, as named by .NET's Environment.SpecialFolder.
FOLDERS = {"desktop": "Desktop", "start_menu": "Programs"}

FIND_FOLDERS = (
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "@{"
    + "; ".join(
        f"{kind}=[Environment]::GetFolderPath('{folder}')" for kind, folder in FOLDERS.items()
    )
    + "} | ConvertTo-Json -Compress"
)

# Paths travel in environment variables rather than inside the script, so no
# name (spaces, quotes, Greek letters) can break the PowerShell syntax.
CREATE_SHORTCUT = """
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($env:PALM_LINK)
$link.TargetPath = $env:PALM_TARGET
$link.Arguments = $env:PALM_ARGUMENTS
$link.WorkingDirectory = $env:PALM_WORKDIR
$link.IconLocation = "$($env:PALM_ICON),0"
$link.Description = $env:PALM_DESCRIPTION
$link.Save()
"""


class ShortcutError(RuntimeError):
    """A shortcut could not be found, made or removed."""


@dataclass(frozen=True)
class LaunchTarget:
    """What a shortcut runs, and which icon it shows."""

    target: Path
    arguments: str
    working_dir: Path
    icon: Path


APP_EXE = f"{APP_NAME}.exe"


def launch_target(executable: Path | None = None, frozen: bool | None = None) -> LaunchTarget:
    """How to start palm-lab: the .exe when installed, pythonw from source."""
    executable = executable or Path(sys.executable)
    if frozen is None:
        frozen = is_frozen()
    if frozen:
        # Always the windowed app, even when palm-lab-cli.exe made the shortcut.
        app = executable.with_name(APP_EXE)
        exe = app if app.exists() else executable
        return LaunchTarget(exe, "", exe.parent, exe)
    # pythonw.exe runs the same interpreter without opening a console window.
    pythonw = executable.with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else executable
    return LaunchTarget(interpreter, "-m palm_lab", Path.home(), icon_path())


PowerShell = Callable[[str, dict[str, str]], str]


def run_powershell(script: str, env: dict[str, str]) -> str:
    """Run a PowerShell snippet without a console window and return its output."""
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, **env},
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ShortcutError(f"PowerShell could not run: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise ShortcutError(detail[0] if detail else "PowerShell reported an error.")
    return completed.stdout


class Shortcuts:
    """Create, remove and check palm-lab's shortcuts."""

    def __init__(
        self,
        powershell: PowerShell = run_powershell,
        target: Callable[[], LaunchTarget] = launch_target,
        platform: str = sys.platform,
    ) -> None:
        self._powershell = powershell
        self._target = target
        self._platform = platform
        self._folders: dict[str, Path] | None = None

    @property
    def supported(self) -> bool:
        return self._platform == "win32"

    def folders(self) -> dict[str, Path]:
        """Where the Desktop and Start menu are for this user (asked once)."""
        if not self.supported:
            raise ShortcutError("Shortcuts can only be made on Windows.")
        if self._folders is None:
            output = self._powershell(FIND_FOLDERS, {})
            try:
                found = json.loads(output)
            except json.JSONDecodeError as exc:
                raise ShortcutError("Windows did not say where the Desktop is.") from exc
            if not all(isinstance(found.get(kind), str) and found[kind] for kind in FOLDERS):
                raise ShortcutError("Windows did not say where the Desktop is.")
            self._folders = {kind: Path(found[kind]) for kind in FOLDERS}
        return self._folders

    def path(self, kind: str) -> Path:
        if kind not in FOLDERS:
            raise ShortcutError(f"Unknown shortcut {kind!r}.")
        return self.folders()[kind] / SHORTCUT_FILENAME

    def exists(self, kind: str) -> bool:
        return self.path(kind).exists()

    def state(self) -> dict[str, bool]:
        """Which shortcuts exist, for the settings page. Never raises."""
        try:
            return {"supported": True, **{kind: self.exists(kind) for kind in FOLDERS}}
        except ShortcutError:
            return {"supported": False, **dict.fromkeys(FOLDERS, False)}

    def create(self, kind: str) -> Path:
        link = self.path(kind)
        link.parent.mkdir(parents=True, exist_ok=True)
        target = self._target()
        self._powershell(
            CREATE_SHORTCUT,
            {
                "PALM_LINK": str(link),
                "PALM_TARGET": str(target.target),
                "PALM_ARGUMENTS": target.arguments,
                "PALM_WORKDIR": str(target.working_dir),
                "PALM_ICON": str(target.icon),
                "PALM_DESCRIPTION": DESCRIPTION,
            },
        )
        if not link.exists():
            raise ShortcutError(f"Windows did not create {link}.")
        return link

    def remove(self, kind: str) -> None:
        try:
            self.path(kind).unlink(missing_ok=True)
        except OSError as exc:
            raise ShortcutError(f"Could not remove the shortcut: {exc}") from exc

    def set(self, kind: str, enabled: bool) -> None:
        if enabled:
            self.create(kind)
        else:
            self.remove(kind)
