"""Data model for gesture-to-action bindings."""

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from palm_lab.actions.errors import InvalidBindingError

DEFAULT_STEP_DELAY_SECONDS = 0.4


class ActionType(StrEnum):
    """The kinds of thing a binding can do."""

    LAUNCH = "launch"
    OPEN_URL = "open_url"
    HOTKEY = "hotkey"


@dataclass(frozen=True)
class Action:
    """A single step within a binding."""

    type: ActionType
    target: str


@dataclass(frozen=True)
class Binding:
    """Everything one gesture triggers, in order."""

    gesture: str
    name: str
    actions: tuple[Action, ...]
    step_delay_seconds: float = DEFAULT_STEP_DELAY_SECONDS


def parse_bindings(text: str) -> tuple[Binding, ...]:
    """Parse TOML configuration into bindings.

    Raises InvalidBinding, with a message naming the offending section, if
    the structure or any field is wrong.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise InvalidBindingError(f"Bindings file is not valid TOML: {exc}") from exc

    raw_bindings = data.get("binding")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise InvalidBindingError("Expected one or more [[binding]] sections")

    bindings = []
    for index, raw in enumerate(raw_bindings, start=1):
        if not isinstance(raw, dict):
            raise InvalidBindingError(f"Binding {index}: must be a table")

        gesture = raw.get("gesture")
        if not isinstance(gesture, str) or not gesture:
            raise InvalidBindingError(f"Binding {index}: 'gesture' must be a non-empty string")

        name = raw.get("name")
        if not isinstance(name, str) or not name:
            raise InvalidBindingError(f"Binding {index}: 'name' must be a non-empty string")

        raw_actions = raw.get("action")
        if not isinstance(raw_actions, list) or not raw_actions:
            raise InvalidBindingError(f"Binding {index}: needs at least one [[binding.action]]")

        actions = []
        for position, raw_action in enumerate(raw_actions, start=1):
            where = f"Binding {index}, action {position}"
            if not isinstance(raw_action, dict):
                raise InvalidBindingError(f"{where}: must be a table")

            raw_type = raw_action.get("type")
            if not isinstance(raw_type, str):
                raise InvalidBindingError(f"{where}: 'type' must be a string")
            try:
                action_type = ActionType(raw_type)
            except ValueError as exc:
                known = ", ".join(sorted(t.value for t in ActionType))
                raise InvalidBindingError(
                    f"{where}: unknown type {raw_type!r} (expected one of: {known})"
                ) from exc

            target = raw_action.get("target")
            if not isinstance(target, str) or not target:
                raise InvalidBindingError(f"{where}: 'target' must be a non-empty string")

            actions.append(Action(type=action_type, target=target))

        delay = raw.get("step_delay_seconds", DEFAULT_STEP_DELAY_SECONDS)
        if not isinstance(delay, int | float) or isinstance(delay, bool):
            raise InvalidBindingError(f"Binding {index}: 'step_delay_seconds' must be a number")
        if delay < 0:
            raise InvalidBindingError(f"Binding {index}: 'step_delay_seconds' cannot be negative")

        bindings.append(
            Binding(
                gesture=gesture,
                name=name,
                actions=tuple(actions),
                step_delay_seconds=float(delay),
            )
        )

    return tuple(bindings)


def load_bindings(path: Path) -> tuple[Binding, ...]:
    """Read and parse a bindings file."""
    if not path.exists():
        raise InvalidBindingError(f"No bindings file at {path}")
    return parse_bindings(path.read_text(encoding="utf-8"))
