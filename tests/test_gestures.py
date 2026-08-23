"""End-to-end tests: landmarks in, gesture name out."""

import pytest
from conftest import fixture_paths, gesture_of, load_fixture

from palm_lab.features import extract
from palm_lab.gestures import classify

MINIMUM_ACCURACY = 0.90


@pytest.mark.parametrize("gesture", ["fist", "open_palm"])
def test_gesture_classifies_perfectly(gesture: str) -> None:
    """These three gestures are correctly identified on every capture."""
    for path in fixture_paths(gesture):
        assert classify(extract(load_fixture(path))) == gesture


def test_overall_accuracy_meets_floor() -> None:
    """The full pipeline stays above the accuracy floor across all captures."""
    paths = fixture_paths()
    correct = sum(classify(extract(load_fixture(p))) == gesture_of(p) for p in paths)
    accuracy = correct / len(paths)
    assert accuracy >= MINIMUM_ACCURACY, (
        f"Accuracy dropped to {accuracy:.1%} ({correct}/{len(paths)})"
    )


def test_unrecognised_shape_returns_none() -> None:
    """A finger combination with no rule returns None rather than raising."""
    from palm_lab.features import HandFeatures

    odd = HandFeatures(thumb=False, index=False, middle=True, ring=False, pinky=True)
    assert classify(odd) is None
