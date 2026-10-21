"""Two-hand gestures: two one-hand shapes held up at the same time.

A two-hand setup is stored under a single gesture key, so everything that
already works with gesture names (bindings, the trigger, the on/off switch,
the Activity list) works with it unchanged. The key lists both shapes in
sorted order, so it doesn't matter which hand makes which: a fist and a
peace sign is "fist + peace" either way round.
"""

COMBO_JOIN = " + "
COMBO_MARK = "+"  # so gesture names can never contain it


def combo_key(first: str, second: str) -> str:
    """The key for a pair of shapes, the same whichever hand makes which."""
    return COMBO_JOIN.join(sorted((first, second)))


def combo_parts(key: str) -> tuple[str, str] | None:
    """The two shapes in a two-hand key, or None for a one-hand gesture."""
    parts = key.split(COMBO_JOIN)
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1]


def is_combo(key: str) -> bool:
    return combo_parts(key) is not None
