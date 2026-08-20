"""Map hand shape features to named gestures."""

from palm_lab.features import HandFeatures

GESTURE_RULES: dict[tuple[bool, bool, bool, bool, bool], str] = {
    # (thumb, index, middle, ring, pinky)
    (False, True, True, False, False): "peace",
    (False, False, False, False, False): "fist",
    (True, True, True, True, True): "open_palm",
    (True, False, False, False, False): "thumbs_up",
}


def classify(features: HandFeatures) -> str | None:
    """Return the gesture name for these features, or None if unrecognised."""
    return GESTURE_RULES.get(features.as_tuple())
