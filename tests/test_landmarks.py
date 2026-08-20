"""Tests for landmark normalisation."""

import pytest
from conftest import fixture_paths, load_fixture

from palm_lab.landmarks import MIDDLE_MCP, WRIST, Point, distance, normalise

TOLERANCE = 1e-9


def test_wrist_moves_to_origin() -> None:
    """After normalisation the wrist sits at (0, 0, 0)."""
    hand = load_fixture(fixture_paths("peace")[0])
    wrist = hand[WRIST]
    assert abs(wrist.x) < TOLERANCE
    assert abs(wrist.y) < TOLERANCE
    assert abs(wrist.z) < TOLERANCE


def test_hand_scale_becomes_one() -> None:
    """Wrist-to-middle-knuckle distance is exactly 1.0 after scaling."""
    hand = load_fixture(fixture_paths("peace")[0])
    assert distance(hand[WRIST], hand[MIDDLE_MCP]) == pytest.approx(1.0)


def test_normalisation_is_scale_invariant() -> None:
    """Scaling the input hand does not change the normalised output."""
    hand = load_fixture(fixture_paths("fist")[0])
    doubled = normalise([Point(p.x * 2, p.y * 2, p.z * 2) for p in hand])
    for a, b in zip(hand, doubled, strict=True):
        assert distance(a, b) < TOLERANCE


def test_normalisation_is_translation_invariant() -> None:
    """Moving the hand in frame does not change the normalised output."""
    hand = load_fixture(fixture_paths("fist")[0])
    shifted = normalise([Point(p.x + 0.3, p.y - 0.2, p.z) for p in hand])
    for a, b in zip(hand, shifted, strict=True):
        assert distance(a, b) < TOLERANCE


def test_rejects_wrong_landmark_count() -> None:
    """A hand without exactly 21 landmarks is rejected."""
    with pytest.raises(ValueError, match="21 landmarks"):
        normalise([Point(0.0, 0.0, 0.0)])


def test_rejects_degenerate_hand() -> None:
    """A hand with zero size cannot be scaled."""
    flat = [Point(0.0, 0.0, 0.0) for _ in range(21)]
    with pytest.raises(ValueError, match="Degenerate"):
        normalise(flat)
