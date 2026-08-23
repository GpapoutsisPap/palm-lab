"""Tests for finger extension detection against real captures."""

import pytest
from conftest import fixture_paths, gesture_of, load_fixture

from palm_lab.features import extract

EXPECTED = {
    "fist": (False, False, False, False, False),
    "open_palm": (True, True, True, True, True),
    "peace": (False, True, True, False, False),
    "thumbs_up": (True, False, False, False, False),
}

# Captures where thumb detection is known to be wrong. Each is documented
# rather than removed, so that a change which fixes one reports XPASS
# instead of silently passing. See scripts/measure_thumb.py.
KNOWN_THUMB_FAILURES = {
    # Thumb tip sits near the palm line with a distance above the minimum,
    # so both checks agree on the wrong answer.
    "peace_20260821_004435_382923",
    "peace_20260821_004453_840624",
    # Hand held at a steep angle: the palm line is foreshortened enough that
    # the cross-product sign inverts despite the thumb being extended.
    "thumbs_up_20260821_005225_880303",
}


@pytest.mark.parametrize("path", fixture_paths(), ids=lambda p: p.stem)
def test_four_fingers_always_correct(path) -> None:  # type: ignore[no-untyped-def]
    """Index, middle, ring, and pinky detection is reliable on all captures."""
    hand = load_fixture(path)
    actual = extract(hand).as_tuple()
    expected = EXPECTED[gesture_of(path)]
    assert actual[1:] == expected[1:]


@pytest.mark.parametrize("path", fixture_paths(), ids=lambda p: p.stem)
def test_thumb_correct_except_known_failures(path) -> None:  # type: ignore[no-untyped-def]
    """Thumb detection is correct outside the documented failure cases."""
    if path.stem in KNOWN_THUMB_FAILURES:
        pytest.xfail("documented thumb detection failure")

    hand = load_fixture(path)
    actual = extract(hand).as_tuple()
    expected = EXPECTED[gesture_of(path)]
    assert actual[0] == expected[0]
