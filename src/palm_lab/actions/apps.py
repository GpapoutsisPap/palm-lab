"""Find installed applications by name, the way the Start menu does.

Nearly every Windows program puts a shortcut in one of two Start menu folders,
one shared by all users and one per user. Scanning those lets "Open app" accept
the name a person already knows ("Steam", "Discord", a game) instead of a path.
"""

import difflib
import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from palm_lab.actions.errors import AppNotFoundError

# Targets that are not Start menu shortcuts: URL protocols and built-in tools.
KNOWN_APPS: dict[str, str] = {
    "spotify": "spotify:",
    "steam": "steam://open/main",
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
}

SHORTCUT_SUFFIXES = frozenset({".lnk", ".url"})
PATH_SUFFIXES = frozenset({".exe", ".lnk", ".url", ".bat", ".cmd", ".msc"})
# Shortcuts that sit next to real apps but are never what someone means.
IGNORED_WORDS = ("uninstall", "readme", "release notes", "documentation", "help", "website")
MAX_SUGGESTIONS = 3

Which = Callable[[str], str | None]


def start_menu_dirs() -> list[Path]:
    """The shared and per-user Start menu program folders that exist."""
    folders = []
    for variable in ("PROGRAMDATA", "APPDATA"):
        base = os.environ.get(variable)
        if base:
            folders.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [folder for folder in folders if folder.is_dir()]


def installed_apps(folders: Iterable[Path] | None = None) -> dict[str, Path]:
    """Start menu shortcuts, keyed by the name shown in the Start menu."""
    apps: dict[str, Path] = {}
    for folder in start_menu_dirs() if folders is None else folders:
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in SHORTCUT_SUFFIXES or not path.is_file():
                continue
            if any(word in path.stem.lower() for word in IGNORED_WORDS):
                continue
            apps.setdefault(path.stem, path)
    return apps


def _looks_like_path_or_url(target: str) -> bool:
    return (
        any(mark in target for mark in ("\\", "/", ":"))
        or Path(target).suffix.lower() in PATH_SUFFIXES
    )


def resolve_app(
    target: str,
    apps: Mapping[str, Path] | None = None,
    which: Which = shutil.which,
) -> str:
    """Turn what the user typed into something Windows can open.

    Tried in order: a built-in name, an exact Start menu name, a path or URL
    used as-is, a program on PATH, then a Start menu name containing the text
    if exactly one does. Anything else raises AppNotFoundError with suggestions.
    Exact names come before paths because game titles can contain colons.
    """
    name = target.strip()
    lowered = name.lower()

    if lowered in KNOWN_APPS:
        return KNOWN_APPS[lowered]

    shortcuts = installed_apps() if apps is None else apps
    by_lower = {app.lower(): path for app, path in shortcuts.items()}
    if lowered in by_lower:
        return str(by_lower[lowered])

    if _looks_like_path_or_url(name):
        return name

    on_path = which(name)
    if on_path:
        return on_path

    partial = sorted((app for app in shortcuts if lowered in app.lower()), key=str.lower)
    if len(partial) == 1:
        return str(shortcuts[partial[0]])

    if partial:
        suggestions = partial[:MAX_SUGGESTIONS]
    else:
        close = difflib.get_close_matches(lowered, list(by_lower), n=MAX_SUGGESTIONS, cutoff=0.6)
        originals = {app.lower(): app for app in shortcuts}
        suggestions = [originals[match] for match in close]
    raise AppNotFoundError(name, suggestions=tuple(suggestions))
