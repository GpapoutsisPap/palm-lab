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
