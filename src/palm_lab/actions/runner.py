"""Execute the actions in a binding."""

import os
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

from palm_lab.actions.errors import ActionError, AppNotFoundError, LaunchFailedError
from palm_lab.actions.models import Action, ActionType, Binding

KNOWN_APPS = {
    "spotify": "spotify:",
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
}


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
    """Start an application, resolving known names to launchable targets."""
    resolved = KNOWN_APPS.get(target.lower(), target)
    try:
        if sys.platform == "win32":
            os.startfile(resolved)
        else:
            subprocess.Popen(["xdg-open", resolved])
    except FileNotFoundError as exc:
        raise AppNotFoundError(target) from exc
    except OSError as exc:
        raise LaunchFailedError(target, str(exc)) from exc


def run_action(action: Action) -> ActionResult:
    """Run one action, capturing any failure rather than raising."""
    try:
        if action.type is ActionType.OPEN_URL:
            _open_url(action.target)
        elif action.type is ActionType.LAUNCH:
            _launch(action.target)
        else:
            raise LaunchFailedError(action.target, "hotkey actions are not supported yet")
    except ActionError as exc:
        return ActionResult(action=action, error=exc)
    return ActionResult(action=action)


def run_binding(
    binding: Binding,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ActionResult]:
    """Run every action in order, pausing between them.

    A failing action does not stop the rest: the caller gets one result per
    action and can report partial success.
    """
    results = []
    for position, action in enumerate(binding.actions):
        if position:
            sleep(binding.step_delay_seconds)
        results.append(run_action(action))
    return results
