"""Tests for recording, storing and reusing custom gestures."""

from pathlib import Path

import pytest

from palm_lab.custom_gestures import (
    CustomGesture,
    CustomGestureError,
    all_rules,
    load_custom_gestures,
    remove_custom_gesture,
    rules_from,
    save_custom_gesture,
)
from palm_lab.gestures import BUILTIN_GESTURES, GestureConflictError

THREE_UP = (False, True, True, True, False)
ROCK_ON = (False, True, False, False, True)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "gestures.toml"


def test_a_missing_file_has_no_custom_gestures(path: Path) -> None:
    assert load_custom_gestures(path) == []


def test_saving_writes_a_gesture_that_can_be_read_back(path: Path) -> None:
    save_custom_gesture("Three up", THREE_UP, path)
    assert load_custom_gestures(path) == [CustomGesture(name="Three up", fingers=THREE_UP)]


def test_a_second_gesture_is_appended_not_replaced(path: Path) -> None:
    save_custom_gesture("Three up", THREE_UP, path)
    save_custom_gesture("Rock on", ROCK_ON, path)
    names = [g.name for g in load_custom_gestures(path)]
    assert names == ["Three up", "Rock on"]


def test_a_name_already_in_use_by_a_custom_gesture_is_rejected(path: Path) -> None:
    save_custom_gesture("Three up", THREE_UP, path)
    with pytest.raises(CustomGestureError):
        save_custom_gesture("three up", ROCK_ON, path)  # case-insensitive


def test_a_builtin_gesture_name_cannot_be_reused(path: Path) -> None:
    with pytest.raises(CustomGestureError):
        save_custom_gesture("Peace", THREE_UP, path)


def test_a_shape_already_used_by_a_builtin_gesture_is_rejected(path: Path) -> None:
    fist = (False, False, False, False, False)
    with pytest.raises(GestureConflictError) as excinfo:
        save_custom_gesture("My fist", fist, path)
    assert excinfo.value.existing_name == "fist"


def test_a_shape_already_used_by_a_custom_gesture_is_rejected(path: Path) -> None:
    save_custom_gesture("Three up", THREE_UP, path)
    with pytest.raises(GestureConflictError) as excinfo:
        save_custom_gesture("Also three up", THREE_UP, path)
    assert excinfo.value.existing_name == "Three up"


def test_an_empty_name_is_rejected(path: Path) -> None:
    with pytest.raises(CustomGestureError):
        save_custom_gesture("   ", THREE_UP, path)


def test_removing_a_gesture_leaves_the_others(path: Path) -> None:
    save_custom_gesture("Three up", THREE_UP, path)
    save_custom_gesture("Rock on", ROCK_ON, path)
    remaining = remove_custom_gesture("three up", path)  # case-insensitive
    assert [g.name for g in remaining] == ["Rock on"]
    assert [g.name for g in load_custom_gestures(path)] == ["Rock on"]


def test_removing_an_unknown_gesture_raises(path: Path) -> None:
    with pytest.raises(CustomGestureError):
        remove_custom_gesture("Nope", path)


def test_rules_from_maps_shape_to_name() -> None:
    gestures = [CustomGesture(name="Three up", fingers=THREE_UP)]
    assert rules_from(gestures) == {THREE_UP: "Three up"}


def test_all_rules_merges_builtin_and_custom() -> None:
    gestures = [CustomGesture(name="Three up", fingers=THREE_UP)]
    merged = all_rules(gestures)
    assert merged[THREE_UP] == "Three up"
    assert merged == {**BUILTIN_GESTURES, THREE_UP: "Three up"}


def test_a_name_with_special_characters_round_trips(path: Path) -> None:
    tricky = 'Say "hi" \\ backslash'
    save_custom_gesture(tricky, THREE_UP, path)
    assert load_custom_gestures(path)[0].name == tricky


def test_invalid_toml_raises_a_readable_error(path: Path) -> None:
    path.write_text("not [ valid toml", encoding="utf-8")
    with pytest.raises(CustomGestureError):
        load_custom_gestures(path)


def test_a_gesture_missing_fingers_raises(path: Path) -> None:
    path.write_text('[[gesture]]\nname = "Oops"\n', encoding="utf-8")
    with pytest.raises(CustomGestureError):
        load_custom_gestures(path)
