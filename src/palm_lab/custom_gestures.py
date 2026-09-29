"""Gestures a person records themselves, stored in gestures.toml.

Because a gesture is just which of the five fingers are extended (see
palm_lab.gestures), recording a custom one needs no landmark matching: hold
your hand up, read the same five-tuple the built-in gestures use, give it a
name, done. This module only owns reading, writing and validating that file;
the actual "hold your hand up" capture flow lives in the engine and UI.
"""

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from palm_lab.config import config_dir
from palm_lab.gestures import BUILTIN_GESTURES, FingerTuple, GestureConflictError

GESTURES_FILENAME = "gestures.toml"


class CustomGestureError(ValueError):
    """A custom gesture file, name or entry is invalid."""


@dataclass(frozen=True)
class CustomGesture:
    """A gesture a person recorded themselves."""

    name: str
    fingers: FingerTuple


def gestures_path() -> Path:
    """Full path to the custom gestures file, whether or not it exists yet."""
    return config_dir() / GESTURES_FILENAME


def _fingers_from_entry(entry: Mapping[str, object], index: int) -> FingerTuple:
    fingers = entry.get("fingers")
    if (
        not isinstance(fingers, list)
        or len(fingers) != 5
        or not all(isinstance(flag, bool) for flag in fingers)
    ):
        raise CustomGestureError(
            f"gesture #{index + 1} needs a 'fingers' list of exactly five true/false values"
        )
    thumb, index_f, middle, ring, pinky = fingers
    return (thumb, index_f, middle, ring, pinky)


def load_custom_gestures(path: Path | None = None) -> list[CustomGesture]:
    """Read the custom gestures a person has recorded, in the order saved."""
    path = path or gestures_path()
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CustomGestureError(f"Gestures file is not valid TOML: {exc}") from exc

    entries = data.get("gesture", [])
    if not isinstance(entries, list):
        raise CustomGestureError("'gesture' must be a list of [[gesture]] tables")

    gestures = []
    seen_lower: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise CustomGestureError(f"gesture #{index + 1} must be a [[gesture]] table")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CustomGestureError(f"gesture #{index + 1} needs a non-empty 'name'")
        name = name.strip()
        if name.lower() in seen_lower:
            raise CustomGestureError(f"gesture #{index + 1}: {name!r} is already used")
        seen_lower.add(name.lower())
        gestures.append(CustomGesture(name=name, fingers=_fingers_from_entry(entry, index)))
    return gestures


def rules_from(gestures: list[CustomGesture]) -> dict[FingerTuple, str]:
    """Turn saved custom gestures into a classify()-ready rules mapping."""
    return {gesture.fingers: gesture.name for gesture in gestures}


def all_rules(custom: list[CustomGesture] | None = None) -> dict[FingerTuple, str]:
    """Built-in gestures plus custom ones, ready to pass to classify().

    Built-ins come first and custom entries are layered on top, but a saved
    conflict should never happen: save_custom_gesture() already refuses a
    shape or name that collides with anything, built-in or custom.
    """
    merged = dict(BUILTIN_GESTURES)
    merged.update(rules_from(custom if custom is not None else load_custom_gestures()))
    return merged


def _find_shape_conflict(fingers: FingerTuple, existing: list[CustomGesture]) -> str | None:
    if fingers in BUILTIN_GESTURES:
        return BUILTIN_GESTURES[fingers]
    for gesture in existing:
        if gesture.fingers == fingers:
            return gesture.name
    return None


def save_custom_gesture(
    name: str, fingers: FingerTuple, path: Path | None = None
) -> list[CustomGesture]:
    """Add a new custom gesture and return the full updated list.

    Raises CustomGestureError for an empty or already-used name (including a
    built-in gesture's name), and GestureConflictError when the shape itself
    already belongs to another gesture.
    """
    name = name.strip()
    if not name:
        raise CustomGestureError("A gesture needs a name.")
    path = path or gestures_path()
    existing = load_custom_gestures(path)

    taken = {gesture.name.lower() for gesture in existing} | {
        builtin.lower() for builtin in BUILTIN_GESTURES.values()
    }
    if name.lower() in taken:
        raise CustomGestureError(f"{name!r} is already the name of a gesture.")

    conflict = _find_shape_conflict(fingers, existing)
    if conflict is not None:
        raise GestureConflictError(fingers, conflict)

    updated = [*existing, CustomGesture(name=name, fingers=fingers)]
    _write(updated, path)
    return updated


def remove_custom_gesture(name: str, path: Path | None = None) -> list[CustomGesture]:
    """Remove a custom gesture by name (case-insensitive) and return what's left."""
    path = path or gestures_path()
    existing = load_custom_gestures(path)
    updated = [gesture for gesture in existing if gesture.name.lower() != name.strip().lower()]
    if len(updated) == len(existing):
        raise CustomGestureError(f"No custom gesture named {name!r}.")
    _write(updated, path)
    return updated


def _write(gestures: list[CustomGesture], path: Path) -> None:
    lines = [
        "# palm-lab custom gestures, written by the palm-lab window.",
        "# Each [[gesture]] is a name and which of the five fingers are up:",
        "# fingers = [thumb, index, middle, ring, pinky]",
        "",
    ]
    for gesture in gestures:
        flags = ", ".join("true" if flag else "false" for flag in gesture.fingers)
        fingers_toml = f"[{flags}]"
        lines += [
            "[[gesture]]",
            f"name = {json.dumps(gesture.name)}",
            f"fingers = {fingers_toml}",
            "",
        ]
    text = "\n".join(lines).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)
