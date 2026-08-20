"""Tests for finger extension detection against real captures."""

import pytest
from conftest import fixture_paths, load_fixture

from palm_lab.features import extract

EXPECTED = {
    "fist": (False, False, False, False, False),
    "open_palm": (True, True, True, True, True),
    "peace": (False, True, True, False, False),
    "thumbs_up": (True, False, False, False, False),
}

# Captures where the thumb drifted outward far enough to cross the
# extension threshold. See scripts/measure_thumb.py for the distribution.
KNOWN_THUMB_FAILURES = {
    "peace_20260821_004435_382923",
    "peace_20260821_004453_840624",
}


@pytest.mark.parametrize("path", fixture_paths(), ids=lambda p: p.stem)
def test_four_fingers_always_correct(path) -> None:  # type: ignore[no-untyped-def]
    """Index, middle, ring, and pinky detection is reliable on all captures."""
    from conftest import gesture_of

    hand = load_fixture(path)
    actual = extract(hand).as_tuple()
    expected = EXPECTED[gesture_of(path)]
    assert actual[1:] == expected[1:]


@pytest.mark.parametrize("path", fixture_paths(), ids=lambda p: p.stem)
def test_thumb_correct_except_known_failures(path) -> None:  # type: ignore[no-untyped-def]
    """Thumb detection is correct outside the documented overlap cases."""
    from conftest import gesture_of

    if path.stem in KNOWN_THUMB_FAILURES:
        pytest.xfail("thumb drifted into the overlap band")

    hand = load_fixture(path)
    actual = extract(hand).as_tuple()
    expected = EXPECTED[gesture_of(path)]
    assert actual[0] == expected[0]
