"""Shared test helpers for loading landmark fixtures."""

import json
from pathlib import Path

from palm_lab.landmarks import Point, normalise

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(path: Path) -> list[Point]:
    """Load one fixture file and return its normalised landmarks."""
    raw = json.loads(path.read_text())
    return normalise([Point(**p) for p in raw])


def fixture_paths(gesture: str | None = None) -> list[Path]:
    """Return fixture paths, optionally filtered to one gesture."""
    pattern = f"{gesture}_*.json" if gesture else "*.json"
    return sorted(FIXTURE_DIR.glob(pattern))


def gesture_of(path: Path) -> str:
    """Recover the gesture label from a fixture filename."""
    return path.stem.rsplit("_", 3)[0]


def raw_hand(gesture: str) -> list[Point]:
    """Un-normalised landmarks from a recorded fixture, as a detector returns them."""
    # The first capture of each gesture is one the classifier gets right.
    path = fixture_paths(gesture)[0]
    return [Point(**p) for p in json.loads(path.read_text())]


def three_fingers_up() -> list[Point]:
    """A shape none of the four built-ins use, for capture happy-path tests.

    Built from the open_palm fixture with the thumb folded onto the index
    knuckle and the pinky tip pulled in toward the wrist, leaving index,
    middle and ring extended.
    """
    points = list(raw_hand("open_palm"))
    wrist = points[0]
    points[4] = points[5]
    pinky_pip = points[18]
    points[20] = Point(
        wrist.x + (pinky_pip.x - wrist.x) * 0.3,
        wrist.y + (pinky_pip.y - wrist.y) * 0.3,
        wrist.z + (pinky_pip.z - wrist.z) * 0.3,
    )
    return points
