"""Tests for tuning finger detection to one person's hand."""

from dataclasses import replace
from pathlib import Path

import pytest
from conftest import fixture_paths, gesture_of, load_fixture

from palm_lab.features import (
    STANDARD_PROFILE,
    HandMeasurement,
    HandProfile,
    extract,
    features_from,
    measure,
)
from palm_lab.gestures import classify
from palm_lab.hand_profile import (
    FINGER_RANGE,
    HandProfileError,
    load_hand_profile,
    reset_hand_profile,
    save_hand_profile,
    tune,
)


def readings(gesture: str) -> list[HandMeasurement]:
    return [measure(load_fixture(path)) for path in fixture_paths(gesture)]


def stiff(reading: HandMeasurement, by: float = 0.33) -> HandMeasurement:
    """The same hand, as if its fingers never fully curl."""
    return replace(reading, finger_ratios=tuple(r + by for r in reading.finger_ratios))  # type: ignore[arg-type]


def accuracy(profile: HandProfile) -> float:
    paths = fixture_paths()
    right = sum(classify(extract(load_fixture(p), profile)) == gesture_of(p) for p in paths)
    return right / len(paths)


# Measuring ----------------------------------------------------------------------


def test_the_standard_profile_matches_the_old_rules() -> None:
    """Splitting measuring from deciding must not change any answer."""
    for path in fixture_paths():
        hand = load_fixture(path)
        assert features_from(measure(hand)) == extract(hand)


def test_straight_fingers_measure_above_one_and_curled_ones_below() -> None:
    (palm, *_), (fist, *_) = readings("open_palm"), readings("fist")
    assert all(r > 1 for r in palm.finger_ratios)
    assert all(r < 1 for r in fist.finger_ratios)


# Tuning --------------------------------------------------------------------------


def test_tuning_on_recorded_hands_is_at_least_as_accurate_as_standard() -> None:
    result = tune(readings("open_palm"), readings("fist"))
    assert result.kept_standard == ()
    assert accuracy(result.profile) >= accuracy(STANDARD_PROFILE)


def test_cut_offs_land_between_open_and_fist() -> None:
    result = tune(readings("open_palm"), readings("fist"))
    for threshold in result.profile.finger_thresholds:
        assert 0.9 < threshold < 1.1  # this hand straddles the standard 1.0


def test_the_thumb_keeps_its_standard_rule() -> None:
    """Open hand and fist can't separate a tucked thumb; see hand_profile's docstring."""
    result = tune(readings("open_palm"), readings("fist"))
    assert result.profile.thumb_distance == STANDARD_PROFILE.thumb_distance


def test_a_hand_whose_fingers_never_fully_curl_is_read_right_once_tuned() -> None:
    """The case tuning exists for: a stiff fist reads as fingers up at the standard cut-off."""
    open_hand = readings("open_palm")
    fist = [stiff(r) for r in readings("fist")]
    misread = sum(classify(features_from(r)) != "fist" for r in fist)
    assert misread > 0
    profile = tune(open_hand, fist).profile
    assert all(classify(features_from(r, profile)) == "fist" for r in fist)
    assert all(classify(features_from(r, profile)) == "open_palm" for r in open_hand)


def test_cut_offs_stay_within_safe_limits() -> None:
    open_hand = [stiff(r, by=1.0) for r in readings("open_palm")]
    fist = [stiff(r, by=1.0) for r in readings("fist")]
    profile = tune(open_hand, fist).profile
    assert all(t == FINGER_RANGE[1] for t in profile.finger_thresholds)


def test_a_finger_that_barely_changes_keeps_the_standard_cut_off() -> None:
    open_hand = readings("open_palm")
    fist = [
        replace(r, finger_ratios=(*r.finger_ratios[:3], open_hand[0].finger_ratios[3]))
        for r in readings("fist")
    ]
    result = tune(open_hand, fist)
    assert result.kept_standard == ("pinky",)
    assert result.profile.finger_thresholds[3] == 1.0


def test_the_same_pose_twice_is_refused() -> None:
    """Holding an open hand for both steps would otherwise tune nonsense."""
    with pytest.raises(HandProfileError, match="almost the same"):
        tune(readings("open_palm"), readings("open_palm"))


def test_too_few_frames_are_refused() -> None:
    with pytest.raises(HandProfileError, match="Not enough"):
        tune(readings("open_palm")[:2], readings("fist"))


# The file -------------------------------------------------------------------------


def test_no_file_means_not_tuned(tmp_path: Path) -> None:
    assert load_hand_profile(tmp_path / "hand.toml") is None


def test_a_saved_profile_loads_back(tmp_path: Path) -> None:
    path = tmp_path / "hand.toml"
    profile = HandProfile(finger_thresholds=(0.95, 1.0, 1.05, 1.1))
    save_hand_profile(profile, path)
    assert load_hand_profile(path) == profile
    assert "Reset tuning" in path.read_text(encoding="utf-8")


def test_reset_goes_back_to_standard(tmp_path: Path) -> None:
    path = tmp_path / "hand.toml"
    save_hand_profile(STANDARD_PROFILE, path)
    reset_hand_profile(path)
    reset_hand_profile(path)  # twice is harmless
    assert load_hand_profile(path) is None


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("index = ", "not valid TOML"),
        ("index = 1.0\nmiddle = 1.0\nring = 1.0\n", "'pinky'"),
        ("index = 3.0\nmiddle = 1.0\nring = 1.0\npinky = 1.0\n", "between"),
        ('index = "1"\nmiddle = 1.0\nring = 1.0\npinky = 1.0\n', "'index'"),
    ],
    ids=["bad-toml", "missing", "out-of-range", "not-a-number"],
)
def test_a_broken_file_is_reported(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "hand.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(HandProfileError, match=message):
        load_hand_profile(path)
