"""Print thumb geometry for every fixture, grouped by gesture.

Reports the signed cross product used by `_is_thumb_extended`, oriented so
that positive means "reads as extended". Values near zero are the ambiguous
ones: the thumb tip is sitting close to the palm line, where the sign is
decided by landmark noise rather than by hand shape.
"""

import json
from collections import defaultdict
from pathlib import Path

from palm_lab.features import (
    INDEX_MCP,
    PINKY_MCP,
    THUMB_TIP,
    _cross_sign,
)
from palm_lab.landmarks import WRIST, Point, distance, normalise

FIXTURE_DIR = Path(__file__).parents[1] / "tests" / "fixtures"
EXPECTED_EXTENDED = {"open_palm", "thumbs_up"}


def signed_offset(hand: list[Point]) -> float:
    """Positive when the thumb reads as extended, negative when tucked."""
    palm = _cross_sign(hand[INDEX_MCP], hand[PINKY_MCP], hand[WRIST])
    thumb = _cross_sign(hand[INDEX_MCP], hand[PINKY_MCP], hand[THUMB_TIP])
    return thumb if palm > 0 else -thumb


def main() -> None:
    by_gesture: defaultdict[str, list[tuple[float, float]]] = defaultdict(list)

    for path in sorted(FIXTURE_DIR.glob("*.json")):
        raw = json.loads(path.read_text())
        hand = normalise([Point(**p) for p in raw])
        offset = signed_offset(hand)
        dist = distance(hand[INDEX_MCP], hand[THUMB_TIP])
        by_gesture[path.stem.rsplit("_", 3)[0]].append((offset, dist))

    for gesture, entries in sorted(by_gesture.items()):
        entries.sort()
        extended = gesture in EXPECTED_EXTENDED
        wrong = sum(1 for offset, _ in entries if (offset > 0) != extended)
        label = "extended" if extended else "tucked"
        print(f"{gesture}  (expect {label})  n={len(entries)}  wrong={wrong}")
        print("  cross: " + ", ".join(f"{o:+.3f}" for o, _ in entries))
        print("  dist:  " + ", ".join(f"{d:.3f}" for _, d in entries))
        print()


if __name__ == "__main__":
    main()
