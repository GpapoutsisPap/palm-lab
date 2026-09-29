"""The Python side of the palm-lab window.

pywebview exposes the public methods of `Api` to JavaScript as
`window.pywebview.api.<method>()`. Every method takes and returns plain
JSON-compatible data, and reports failures as `{"ok": false, "error": ...}`
rather than raising, so the page can always show the user a message.
"""

import base64
import shutil
import threading
import time
import webbrowser
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from palm_lab.actions.apps import KNOWN_APPS, installed_apps
from palm_lab.actions.errors import ActionError
from palm_lab.actions.models import (
    ActionType,
    Binding,
    bindings_from_data,
    load_bindings,
    save_bindings,
)
from palm_lab.actions.runner import ActionResult, run_binding
from palm_lab.config import PROJECT_URL
from palm_lab.custom_css import CustomCssError, load_custom_css, save_custom_css
from palm_lab.custom_gestures import (
    CustomGesture,
    CustomGestureError,
    load_custom_gestures,
    remove_custom_gesture,
    save_custom_gesture,
)
from palm_lab.engine import EngineStatus, FiredEvent, Hands, TrackingEngine
from palm_lab.gestures import BUILTIN_GESTURES, GestureConflictError
from palm_lab.settings import (
    COOLDOWN_RANGE,
    DWELL_RANGE,
    MAX_CAMERA_INDEX,
    Settings,
    SettingsError,
    load_settings,
    save_settings,
    settings_from_data,
)
from palm_lab.shortcuts import ShortcutError, Shortcuts
from palm_lab.state import TriggerState
from palm_lab.version import __version__
from palm_lab.windows import accent_palette, open_folder

JsonDict = dict[str, Any]

HOTKEY_PRESETS = (
    "media_play_pause",
    "media_next",
    "media_previous",
    "volume_up",
    "volume_down",
    "volume_mute",
    "win+d",
    "alt+tab",
    "ctrl+alt+t",
)


def _binding_to_json(binding: Binding) -> JsonDict:
    return {
        "gesture": binding.gesture,
        "name": binding.name,
        "step_delay_seconds": binding.step_delay_seconds,
        "action": [{"type": a.type.value, "target": a.target} for a in binding.actions],
    }


def _result_to_json(result: ActionResult) -> JsonDict:
    return {
        "type": result.action.type.value,
        "target": result.action.target,
        "ok": result.ok,
        "message": result.error.user_message() if result.error else None,
    }


def _fired_to_json(event: FiredEvent | None) -> JsonDict | None:
    if event is None:
        return None
    return {
        "gesture": event.gesture,
        "name": event.binding_name,
        "at": event.at,
        "finished": event.finished,
        "results": [_result_to_json(r) for r in event.results],
    }


def _hands_to_json(hands: Hands) -> list[list[list[float]]]:
    """Landmarks as [x, y] pairs from 0 to 1, mirrored to match the preview."""
    return [[[round(1 - p.x, 4), round(p.y, 4)] for p in hand] for hand in hands]


def _custom_gesture_to_json(gesture: CustomGesture) -> JsonDict:
    return {"name": gesture.name, "fingers": list(gesture.fingers)}


# Pausing is for a while, not for good: longer than this is what the switch is for.
MAX_PAUSE_MINUTES = 24 * 60

# Starts `job` after `delay` seconds; returns a function that cancels it.
Scheduler = Callable[[float, Callable[[], None]], Callable[[], None]]


def run_after(delay: float, job: Callable[[], None]) -> Callable[[], None]:
    timer = threading.Timer(delay, job)
    timer.daemon = True
    timer.start()
    return timer.cancel


def _hold_to_json(trigger: TriggerState) -> JsonDict:
    """The hold in progress, for the ring and status line on the Gestures page."""
    return {
        "phase": trigger.phase,
        "gesture": trigger.gesture,
        "progress": round(trigger.progress, 3),
        "cooldown": round(trigger.cooldown_remaining, 1),
    }


def _status_to_json(status: EngineStatus) -> JsonDict:
    return {
        "running": status.running,
        "gesture": status.gesture,
        "hands": status.hands,
        "fps": round(status.fps, 1),
        "error": status.error,
        "last_fired": _fired_to_json(status.last_fired),
        "hold": _hold_to_json(status.trigger),
    }


class Api:
    """Everything the page can ask Python to do."""

    def __init__(
        self,
        engine: TrackingEngine,
        *,
        bindings_file: Path,
        settings_file: Path,
        gestures_file: Path,
        probe_cameras: Callable[[], list[int]],
        run: Callable[[Binding], list[ActionResult]] = run_binding,
        list_apps: Callable[[], Iterable[str]] = lambda: installed_apps().keys(),
        shortcuts: Shortcuts | None = None,
        accent: Callable[[], tuple[str, ...]] = accent_palette,
        open_path: Callable[[Path], None] = open_folder,
        open_url: Callable[[str], object] = webbrowser.open,
        on_theme_change: Callable[[], None] = lambda: None,
        on_close_choice: Callable[[str], None] = lambda choice: None,
        custom_css_file: Path | None = None,
        custom_css_allowed: bool = True,
        schedule: Scheduler = run_after,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._engine = engine
        self._bindings_file = bindings_file
        self._settings_file = settings_file
        self._gestures_file = gestures_file
        self._probe_cameras = probe_cameras
        self._run = run
        self._list_apps = list_apps
        self._shortcuts = shortcuts or Shortcuts()
        self._accent = accent
        self._open_path = open_path
        self._open_url = open_url
        self._on_theme_change = on_theme_change
        self._on_close_choice = on_close_choice
        self._custom_css_file = custom_css_file
        # False for `palm-lab ui --no-custom-css`: the way back from CSS that
        # hid the window's own controls.
        self._custom_css_allowed = custom_css_allowed
        self._schedule = schedule
        self._wall_clock = wall_clock
        self._pause_lock = threading.Lock()
        self._paused_until: float | None = None  # wall-clock time tracking comes back
        self._cancel_resume: Callable[[], None] | None = None
        self._resume_error: str | None = None
        self._problems: list[str] = []
        self._bindings_unreadable = False

        try:
            self._bindings = load_bindings(bindings_file)
        except ActionError as exc:
            self._bindings = ()
            self._bindings_unreadable = True
            self._problems.append(
                f"Your bindings file could not be read: {exc.user_message()} "
                "It will be backed up before anything is saved over it."
            )
        try:
            self._settings = load_settings(settings_file)
        except SettingsError as exc:
            self._settings = Settings()
            self._problems.append(f"Your settings file could not be read ({exc}); using defaults.")
        try:
            self._custom_gestures = load_custom_gestures(gestures_file)
        except CustomGestureError as exc:
            self._custom_gestures = []
            self._problems.append(
                f"Your custom gestures file could not be read ({exc}); ignoring it."
            )

        engine.update_bindings(self._bindings)
        engine.update_settings(self._settings)
        engine.update_custom_gestures(self._custom_gestures)

    # State -----------------------------------------------------------------

    def get_state(self) -> JsonDict:
        """Everything the page needs to draw itself on startup."""
        return {
            "gestures": list(BUILTIN_GESTURES.values()),
            "custom_gestures": [_custom_gesture_to_json(g) for g in self._custom_gestures],
            "action_types": [t.value for t in ActionType],
            "known_apps": self._app_suggestions(),
            "hotkey_presets": list(HOTKEY_PRESETS),
            "bindings": [_binding_to_json(b) for b in self._bindings],
            "settings": self._settings.as_dict(),
            "limits": {
                "dwell_seconds": list(DWELL_RANGE),
                "cooldown_seconds": list(COOLDOWN_RANGE),
                "camera_index": [0, MAX_CAMERA_INDEX],
            },
            "problems": list(self._problems),
            "bindings_file": str(self._bindings_file),
            "status": self.status(),
            "version": __version__,
            "accent": list(self._accent()),
            "project_url": PROJECT_URL,
            "custom_css": self._custom_css_state(),
        }

    def _custom_css_state(self) -> JsonDict:
        if self._custom_css_file is None:
            return {"text": "", "file": None, "allowed": False, "error": None}
        try:
            text, error = load_custom_css(self._custom_css_file), None
        except (CustomCssError, OSError) as exc:
            text, error = "", str(exc)
        return {
            "text": text,
            "file": str(self._custom_css_file),
            "allowed": self._custom_css_allowed,
            "error": error,
        }

    def _app_suggestions(self) -> list[str]:
        """Names to suggest while typing an app: installed apps plus built-ins."""
        try:
            installed = set(self._list_apps())
        except OSError:
            installed = set()
        taken = {name.lower() for name in installed}
        extras = {name for name in KNOWN_APPS if name not in taken}
        return sorted(installed | extras, key=str.lower)

    # Bindings ----------------------------------------------------------------

    def save_bindings(self, payload: JsonDict) -> JsonDict:
        """Validate and save bindings sent from the page, then apply them."""
        try:
            bindings = bindings_from_data(payload)
        except ActionError as exc:
            return {"ok": False, "error": exc.user_message()}
        try:
            self._back_up_unreadable_bindings()
            save_bindings(bindings, self._bindings_file)
        except OSError as exc:
            return {"ok": False, "error": f"Could not save {self._bindings_file}: {exc}"}
        self._bindings = bindings
        self._engine.update_bindings(bindings)
        return {"ok": True, "bindings": [_binding_to_json(b) for b in bindings]}

    def _back_up_unreadable_bindings(self) -> None:
        """Before the first save over a file we could not read, keep a copy."""
        if not self._bindings_unreadable:
            return
        backup = self._bindings_file.with_suffix(".toml.bak")
        if self._bindings_file.exists() and not backup.exists():
            shutil.copy2(self._bindings_file, backup)
        self._bindings_unreadable = False

    def test_binding(self, gesture: str) -> JsonDict:
        """Run a gesture's actions now, as if the gesture had been held."""
        binding = next((b for b in self._bindings if b.gesture == gesture), None)
        if binding is None:
            return {"ok": False, "error": f"Nothing is bound to {gesture!r} yet."}
        results = self._run(binding)
        return {"ok": all(r.ok for r in results), "results": [_result_to_json(r) for r in results]}

    # Settings ----------------------------------------------------------------

    def save_settings(self, payload: JsonDict) -> JsonDict:
        """Validate and save settings, then apply them to the engine."""
        try:
            settings = settings_from_data(payload)
        except SettingsError as exc:
            return {"ok": False, "error": str(exc)}
        try:
            save_settings(settings, self._settings_file)
        except OSError as exc:
            return {"ok": False, "error": f"Could not save settings: {exc}"}
        self._settings = settings
        try:
            self._engine.update_settings(settings)
        except (RuntimeError, OSError) as exc:
            # Saved, but restarting tracking on the new camera failed.
            return {"ok": False, "error": str(exc), "settings": settings.as_dict()}
        return {"ok": True, "settings": settings.as_dict()}

    def list_cameras(self) -> JsonDict:
        """Camera numbers that work right now. Slow: call on demand only."""
        if self._engine.running:
            return {"ok": False, "error": "Stop tracking before scanning for cameras."}
        return {"ok": True, "cameras": self._probe_cameras()}

    # Tracking ----------------------------------------------------------------

    def start(self) -> JsonDict:
        """Start tracking. Also ends a pause early."""
        self._clear_pause()
        try:
            self._engine.start()
        except (RuntimeError, OSError) as exc:
            return {"ok": False, "error": str(exc), "status": self.status()}
        return {"ok": True, "status": self.status()}

    def stop(self) -> JsonDict:
        """Stop tracking for good (until switched back on), cancelling any pause."""
        self._clear_pause()
        self._engine.stop()
        return {"ok": True, "status": self.status()}

    def status(self) -> JsonDict:
        status = _status_to_json(self._engine.status())
        with self._pause_lock:
            status["paused_until"] = self._paused_until
            if not status["running"] and not status["error"] and self._resume_error:
                status["error"] = self._resume_error
        return status

    # Pausing -------------------------------------------------------------------

    def pause(self, minutes: float) -> JsonDict:
        """Stop tracking for a while, releasing the camera, then start again by itself."""
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int | float)
            or not 0 < minutes <= MAX_PAUSE_MINUTES
        ):
            return {
                "ok": False,
                "error": f"Pause for between 1 and {MAX_PAUSE_MINUTES} minutes.",
                "status": self.status(),
            }
        self._clear_pause()
        self._engine.stop()
        with self._pause_lock:
            self._paused_until = self._wall_clock() + minutes * 60
            self._cancel_resume = self._schedule(minutes * 60, self._resume_when_due)
        return {"ok": True, "status": self.status()}

    def resume(self) -> JsonDict:
        """End a pause now."""
        return self.start()

    def _resume_when_due(self) -> None:
        with self._pause_lock:
            if self._paused_until is None:
                return  # resumed or switched off in the meantime
            self._paused_until = None
            self._cancel_resume = None
        try:
            self._engine.start()
        except (RuntimeError, OSError) as exc:
            with self._pause_lock:
                self._resume_error = f"Tracking could not start again after the pause: {exc}"

    def _clear_pause(self) -> None:
        with self._pause_lock:
            cancel, self._cancel_resume = self._cancel_resume, None
            self._paused_until = None
            self._resume_error = None
        if cancel is not None:
            cancel()

    def preview(self) -> JsonDict | None:
        """The latest camera frame and its hands, or None when not tracking."""
        frame = self._engine.snapshot()
        if frame is None:
            return None
        return {
            "image": "data:image/jpeg;base64," + base64.b64encode(frame.image).decode("ascii"),
            "hands": _hands_to_json(frame.hands),
            # Sent with every frame, so the hold ring moves as smoothly as the video.
            "hold": _hold_to_json(self._engine.status().trigger),
        }

    # Custom gestures -----------------------------------------------------------

    def start_gesture_capture(self) -> JsonDict:
        """Begin recording a new gesture, starting the camera if it isn't running."""
        self._clear_pause()  # the camera is coming on, so a pause is over
        if not self._engine.running:
            try:
                self._engine.start()
            except (RuntimeError, OSError) as exc:
                return {"ok": False, "error": str(exc)}
        self._engine.start_gesture_capture()
        return {"ok": True, "status": self.status()}

    def cancel_gesture_capture(self) -> JsonDict:
        self._engine.cancel_gesture_capture()
        return {"ok": True}

    def capture_status(self) -> JsonDict | None:
        """What the "Add gesture" wizard should show right now, polled per frame."""
        status = self._engine.capture_status()
        if status is None:
            return None
        return {
            "stage": status.stage,
            "attempt": status.attempt,
            "progress": round(status.progress, 3),
            "fingers": list(status.fingers) if status.fingers is not None else None,
            "matches": status.matches,
        }

    def save_captured_gesture(self, name: str) -> JsonDict:
        """Name and save the shape a completed capture just recorded."""
        status = self._engine.capture_status()
        if status is None or status.stage != "done" or status.fingers is None:
            return {"ok": False, "error": "No completed gesture capture to save."}
        try:
            updated = save_custom_gesture(name, status.fingers, self._gestures_file)
        except (CustomGestureError, GestureConflictError) as exc:
            return {"ok": False, "error": str(exc)}
        self._custom_gestures = updated
        self._engine.update_custom_gestures(updated)
        self._engine.cancel_gesture_capture()
        return {"ok": True, "custom_gestures": [_custom_gesture_to_json(g) for g in updated]}

    def remove_custom_gesture(self, name: str) -> JsonDict:
        try:
            updated = remove_custom_gesture(name, self._gestures_file)
        except CustomGestureError as exc:
            return {"ok": False, "error": str(exc)}
        self._custom_gestures = updated
        self._engine.update_custom_gestures(updated)
        return {"ok": True, "custom_gestures": [_custom_gesture_to_json(g) for g in updated]}

    # Custom CSS ---------------------------------------------------------------------

    def save_custom_css(self, text: str) -> JsonDict:
        """Save the CSS typed in Settings (the page has already applied it)."""
        if self._custom_css_file is None:
            return {"ok": False, "error": "Custom CSS is not available here."}
        if not isinstance(text, str):
            return {"ok": False, "error": "Custom CSS must be text."}
        try:
            save_custom_css(text, self._custom_css_file)
        except CustomCssError as exc:
            return {"ok": False, "error": str(exc)}
        except OSError as exc:
            return {"ok": False, "error": f"Could not save {self._custom_css_file}: {exc}"}
        return {"ok": True}

    # Window ------------------------------------------------------------------------

    def close_choice(self, choice: str, remember: bool) -> JsonDict:
        """The answer to "keep palm-lab running in the background?" on closing.

        choice is "background" or "quit". With remember, it becomes the
        close_action setting, so the question is not asked again (Settings can
        change it back).
        """
        if choice not in ("background", "quit"):
            return {"ok": False, "error": f"Unknown choice {choice!r}."}
        if remember:
            result = self.save_settings({**self._settings.as_dict(), "close_action": choice})
            if not result["ok"]:
                return result
        self._on_close_choice(choice)
        return {"ok": True, "settings": self._settings.as_dict()}

    def theme_changed(self) -> JsonDict:
        """The page saw Windows switch between light and dark."""
        self._on_theme_change()
        return {"ok": True}

    # Shortcuts and links --------------------------------------------------------

    def shortcut_state(self) -> JsonDict:
        """Which shortcuts exist. Separate from get_state because it is slow."""
        return self._shortcuts.state()

    def set_shortcut(self, kind: str, enabled: bool) -> JsonDict:
        """Add or remove the desktop or Start menu shortcut."""
        try:
            self._shortcuts.set(kind, bool(enabled))
        except ShortcutError as exc:
            return {"ok": False, "error": str(exc), "shortcuts": self._shortcuts.state()}
        return {"ok": True, "shortcuts": self._shortcuts.state()}

    def open_config_folder(self) -> JsonDict:
        """Show the folder holding the bindings and settings files."""
        folder = self._bindings_file.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self._open_path(folder)
        except OSError as exc:
            return {"ok": False, "error": f"Could not open {folder}: {exc}"}
        return {"ok": True}

    def open_project_page(self) -> JsonDict:
        """Open the project's page in the default browser."""
        self._open_url(PROJECT_URL)
        return {"ok": True}
