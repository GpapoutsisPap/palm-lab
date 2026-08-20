"""Print thumb-to-index-knuckle distance for every fixture, grouped by gesture."""

import json
from collections import defaultdict
from pathlib import Path

from palm_lab.features import INDEX_MCP, THUMB_TIP
from palm_lab.landmarks import Point, distance, normalise

FIXTURE_DIR = Path(__file__).parents[1] / "tests" / "fixtures"


def main() -> None:
    by_gesture: defaultdict[str, list[float]] = defaultdict(list)

    for path in sorted(FIXTURE_DIR.glob("*.json")):
        raw = json.loads(path.read_text())
        hand = normalise([Point(**p) for p in raw])
        value = distance(hand[INDEX_MCP], hand[THUMB_TIP])
        gesture = path.stem.rsplit("_", 3)[0]
        by_gesture[gesture].append(value)

    for gesture, values in sorted(by_gesture.items()):
        values.sort()
        formatted = ", ".join(f"{v:.3f}" for v in values)
        print(f"{gesture:12s} n={len(values):2d}  min={min(values):.3f}  max={max(values):.3f}")
        print(f"{'':12s} {formatted}")
        print()


if __name__ == "__main__":
    main()
