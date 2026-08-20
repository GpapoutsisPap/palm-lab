"""Normalise raw hand landmarks into a position- and scale-invariant form."""

from dataclasses import dataclass
from math import sqrt

WRIST = 0
MIDDLE_MCP = 9


@dataclass(frozen=True)
class Point:
    """A single landmark in 3D space."""

    x: float
    y: float
    z: float


def distance(a: Point, b: Point) -> float:
    """Euclidean distance between two points."""
    return sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def normalise(hand: list[Point]) -> list[Point]:
    """Return landmarks translated to the wrist and scaled by hand size.

    The same gesture produces near-identical output regardless of where the
    hand sits in frame or how far it is from the camera.
    """
    if len(hand) != 21:
        raise ValueError(f"Expected 21 landmarks, got {len(hand)}")

    wrist = hand[WRIST]
    translated = [Point(p.x - wrist.x, p.y - wrist.y, p.z - wrist.z) for p in hand]

    scale = distance(translated[WRIST], translated[MIDDLE_MCP])
    if scale == 0:
        raise ValueError("Degenerate hand: wrist and middle knuckle coincide")

    return [Point(p.x / scale, p.y / scale, p.z / scale) for p in translated]
