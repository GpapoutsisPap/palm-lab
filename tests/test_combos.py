"""Tests for naming two-hand gestures."""

import pytest

from palm_lab.combos import combo_key, combo_parts, is_combo


def test_which_hand_makes_which_shape_does_not_matter() -> None:
    assert combo_key("peace", "fist") == combo_key("fist", "peace") == "fist + peace"


def test_both_hands_can_make_the_same_shape() -> None:
    assert combo_parts(combo_key("fist", "fist")) == ("fist", "fist")


def test_a_key_splits_back_into_its_shapes() -> None:
    assert combo_parts("Three up + peace") == ("Three up", "peace")


@pytest.mark.parametrize("key", ["peace", "", " + peace", "a + b + c"])
def test_anything_else_is_not_a_two_hand_key(key: str) -> None:
    assert combo_parts(key) is None
    assert not is_combo(key)
