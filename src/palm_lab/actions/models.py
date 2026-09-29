"""Data model for gesture-to-action bindings."""

import json
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from palm_lab.actions.errors import InvalidBindingError
from palm_lab.actions.hotkeys import parse_hotkey

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

    Raises InvalidBindingError, with a message naming the offending section,
    if the structure or any field is wrong.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise InvalidBindingError(f"Bindings file is not valid TOML: {exc}") from exc
    return bindings_from_data(data)


def bindings_from_data(data: Mapping[str, object]) -> tuple[Binding, ...]:
    """Validate already-decoded configuration, from a file or from the UI.

    A configuration with no bindings at all is valid: it means nothing is
    bound yet. Each gesture may be bound at most once.
    """
    unknown = sorted(set(data) - {"binding"})
    if unknown:
        raise InvalidBindingError(f"Unknown top-level key {unknown[0]!r}")

    raw_bindings = data.get("binding", [])
    if not isinstance(raw_bindings, list):
        raise InvalidBindingError("'binding' must be a list of [[binding]] sections")

    bindings = []
    seen_gestures: dict[str, int] = {}
    for index, raw in enumerate(raw_bindings, start=1):
        if not isinstance(raw, dict):
            raise InvalidBindingError(f"Binding {index}: must be a table")

        gesture = raw.get("gesture")
        if not isinstance(gesture, str) or not gesture:
            raise InvalidBindingError(f"Binding {index}: 'gesture' must be a non-empty string")
        if gesture in seen_gestures:
            raise InvalidBindingError(
                f"Binding {index}: gesture {gesture!r} is already bound "
                f"by binding {seen_gestures[gesture]}"
            )
        seen_gestures[gesture] = index

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

            if action_type is ActionType.HOTKEY:
                try:
                    parse_hotkey(target)
                except ValueError as exc:
                    raise InvalidBindingError(f"{where}: {exc}") from exc

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


GENERATED_HEADER = """\
# palm-lab gesture bindings.
#
# This file is written by the palm-lab window. You can still edit it by hand,
# but comments are not kept when the window saves it.
"""


def _toml_string(value: str) -> str:
    # A JSON string is also a valid TOML basic string: both escape quotes,
    # backslashes and control characters the same way.
    return json.dumps(value, ensure_ascii=False)


def format_bindings(bindings: Iterable[Binding]) -> str:
    """Render bindings as TOML that parse_bindings reads back unchanged."""
    lines = [GENERATED_HEADER]
    for binding in bindings:
        lines.append("[[binding]]")
        lines.append(f"gesture = {_toml_string(binding.gesture)}")
        lines.append(f"name = {_toml_string(binding.name)}")
        if binding.step_delay_seconds != DEFAULT_STEP_DELAY_SECONDS:
            lines.append(f"step_delay_seconds = {binding.step_delay_seconds!r}")
        for action in binding.actions:
            lines.append("")
            lines.append("  [[binding.action]]")
            lines.append(f"  type = {_toml_string(action.type.value)}")
            lines.append(f"  target = {_toml_string(action.target)}")
        lines.append("")
    return "\n".join(lines)


def save_bindings(bindings: Iterable[Binding], path: Path) -> None:
    """Write bindings to disk atomically, so a crash never leaves half a file."""
    text = format_bindings(bindings)
    parse_bindings(text)  # never write something that would not load back
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)
