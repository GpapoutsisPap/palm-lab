"""Execute the actions in a binding."""

import os
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

from palm_lab.actions import desktop
from palm_lab.actions.apps import resolve_app
from palm_lab.actions.errors import (
    ActionError,
    ActionFailedError,
    AppNotFoundError,
    LaunchFailedError,
)
from palm_lab.actions.hotkeys import parse_hotkey, send_hotkey
from palm_lab.actions.models import Action, ActionType, Binding
from palm_lab.actions.targets import (
    SETTINGS_PAGES,
    SYSTEM_COMMANDS,
    parse_system,
    parse_volume,
    parse_wait,
    settings_uri,
)


@dataclass(frozen=True)
class ActionResult:
    """The outcome of one action within a binding."""

    action: Action
    error: ActionError | None = None

    @property
    def ok(self) -> bool:
        """True when the action ran without raising."""
        return self.error is None


def _open_url(target: str) -> None:
    if not webbrowser.open(target):
        raise LaunchFailedError(target, "no browser available")


def _launch(target: str) -> None:
    """Start an application by Start menu name, program name, path or URL."""
    resolved = resolve_app(target)
    try:
        if sys.platform == "win32":
            os.startfile(resolved)
        else:
            subprocess.Popen(["xdg-open", resolved])
    except FileNotFoundError as exc:
        raise AppNotFoundError(target) from exc
    except OSError as exc:
        raise LaunchFailedError(target, str(exc)) from exc


def _hotkey(target: str) -> None:
    """Parse and send a hotkey, translating failures into typed errors."""
    try:
        hotkey = parse_hotkey(target)
    except ValueError as exc:
        raise LaunchFailedError(target, str(exc)) from exc
    try:
        send_hotkey(hotkey)
    except OSError as exc:
        raise LaunchFailedError(target, str(exc)) from exc


# The newer pieces: what they're called in messages, and how each one runs.
SHOW_DESKTOP_KEYS = "win+d"
SCREENSHOT_KEYS = "win+shift+s"  # Windows' own Snipping Tool overlay


def _type_text(target: str) -> None:
    desktop.type_text(target)


def _volume(target: str) -> None:
    desktop.set_volume(parse_volume(target))


def _open_path(target: str) -> None:
    desktop.open_path(target)


def _settings(target: str) -> None:
    desktop.open_settings(settings_uri(target))


def _system(target: str) -> None:
    command = parse_system(target)
    if command == "lock":
        desktop.lock_pc()
    elif command == "show_desktop":
        send_hotkey(parse_hotkey(SHOW_DESKTOP_KEYS))
    else:
        send_hotkey(parse_hotkey(SCREENSHOT_KEYS))


def _describe(action: Action) -> str:
    """How a failure message names the piece: "Volume", "Open Downloads"."""
    target = action.target.strip()
    return {
        ActionType.TYPE_TEXT: "Typing",
        ActionType.VOLUME: "Volume",
        ActionType.OPEN_PATH: f"Opening {target}",
        ActionType.SETTINGS: f"Opening {SETTINGS_PAGES.get(target.lower(), 'Settings')} settings",
        ActionType.SYSTEM: SYSTEM_COMMANDS.get(target.lower(), "Windows"),
        ActionType.WAIT: "Waiting",
    }.get(action.type, action.type.value)


NEWER_PIECES: dict[ActionType, Callable[[str], None]] = {
    ActionType.TYPE_TEXT: _type_text,
    ActionType.VOLUME: _volume,
    ActionType.OPEN_PATH: _open_path,
    ActionType.SETTINGS: _settings,
    ActionType.SYSTEM: _system,
}


def run_action(action: Action, sleep: Callable[[float], None] = time.sleep) -> ActionResult:
    """Run one action, capturing any failure rather than raising."""
    try:
        if action.type is ActionType.OPEN_URL:
            _open_url(action.target)
        elif action.type is ActionType.LAUNCH:
            _launch(action.target)
        elif action.type is ActionType.HOTKEY:
            _hotkey(action.target)
        else:
            try:
                if action.type is ActionType.WAIT:
                    sleep(parse_wait(action.target))
                else:
                    # Looked up at call time, so tests can replace one.
                    globals()[NEWER_PIECES[action.type].__name__](action.target)
            except (OSError, ValueError) as exc:
                raise ActionFailedError(_describe(action), str(exc)) from exc
    except ActionError as exc:
        return ActionResult(action=action, error=exc)
    return ActionResult(action=action)


def run_binding(
    binding: Binding,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ActionResult]:
    """Run every action in order, pausing between them.

    A failing action does not stop the rest: the caller gets one result per
    action and can report partial success. A Wait piece is its own pause, so
    no extra step delay is added around it.
    """
    results = []
    previous: Action | None = None
    for action in binding.actions:
        if previous is not None and ActionType.WAIT not in (previous.type, action.type):
            sleep(binding.step_delay_seconds)
        results.append(run_action(action, sleep))
        previous = action
    return results
