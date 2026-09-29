"""Map hand shape features to named gestures.

A gesture is nothing more than which of the five fingers are extended: a
fixed point in a 32-shape space, not a landmark pattern to match against.
That is what makes a *custom* gesture (see palm_lab.custom_gestures) cheap to
add later -- recording one is just reading this same five-tuple back.
"""

from collections.abc import Mapping

from palm_lab.features import HandFeatures

FingerTuple = tuple[bool, bool, bool, bool, bool]

BUILTIN_GESTURES: dict[FingerTuple, str] = {
    # (thumb, index, middle, ring, pinky)
    (False, True, True, False, False): "peace",
    (False, False, False, False, False): "fist",
    (True, True, True, True, True): "open_palm",
    (True, False, False, False, False): "thumbs_up",
}


class GestureConflictError(ValueError):
    """A finger shape already belongs to another gesture."""

    def __init__(self, fingers: FingerTuple, existing_name: str) -> None:
        self.fingers = fingers
        self.existing_name = existing_name
        super().__init__(f"That shape is already used by {existing_name!r}.")


def classify(features: HandFeatures, rules: Mapping[FingerTuple, str] | None = None) -> str | None:
    """Return the gesture name for these features, or None if unrecognised.

    `rules` defaults to the four built-in gestures; pass a merged mapping
    (see palm_lab.custom_gestures.all_rules) to also recognise custom ones.
    """
    active = BUILTIN_GESTURES if rules is None else rules
    return active.get(features.as_tuple())
