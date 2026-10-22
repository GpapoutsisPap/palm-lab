"""Tune finger detection to one person's hand.

palm-lab decides a finger is "up" by comparing one measurement against a
cut-off (see palm_lab.features). The standard cut-offs suit most hands, but
fingers that never quite curl, or never quite straighten, sit close to them
and flicker between up and down.

Tuning measures the hand twice, held open and as a fist, and puts each
cut-off halfway between that person's two sets of readings: between the
lowest open readings and the highest fist readings (the 10th and 90th
percentiles, so one stray frame doesn't count). Using the near edges rather
than the typical values matters most for the thumb, whose open position
varies a lot. A finger whose readings barely differ keeps the standard
cut-off, because halfway between two nearly equal numbers is a guess, not a
measurement.

The thumb is not tuned. Its measurement can't be split by an open hand and a
fist alone: in the recorded hands, a peace sign's tucked thumb (0.43 to 0.63
from the index knuckle) overlaps an open hand's (0.46 and up), which is why
the thumb needs a second, sidedness check in palm_lab.features. Tuning it
from these two poses made recognition worse, so it keeps the standard rule.
"""

import statistics
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from palm_lab.config import config_dir
from palm_lab.features import (
    FINGERS,
    STANDARD_PROFILE,
    HandMeasurement,
    HandProfile,
)

PROFILE_FILENAME = "hand.toml"

# Tuned cut-offs are kept inside these, so one odd reading can't make a
# finger count as always up or always down.
FINGER_RANGE = (0.8, 1.2)
# The smallest open-minus-fist difference worth tuning on. Recorded hands
# differ by about 0.7.
MIN_FINGER_GAP = 0.25
# Fewer fingers than this changing between the two poses means they were
# probably not an open hand and a fist.
MIN_TUNED_FINGERS = 2
MIN_SAMPLES = 5


class HandProfileError(ValueError):
    """Measurements that can't be tuned on, or an unreadable hand file."""


@dataclass(frozen=True)
class TuneResult:
    """A tuned profile, and which parts kept the standard cut-off."""

    profile: HandProfile
    kept_standard: tuple[str, ...]  # fingers that barely changed between the poses


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    return min(max(value, low), high)


def _between(open_values: list[float], fist_values: list[float]) -> tuple[float, float]:
    """(gap between typical readings, cut-off between the near edges)."""
    gap = statistics.median(open_values) - statistics.median(fist_values)
    open_low = statistics.quantiles(open_values, n=10, method="inclusive")[0]
    fist_high = statistics.quantiles(fist_values, n=10, method="inclusive")[-1]
    return gap, (open_low + fist_high) / 2


def tune(open_hand: Sequence[HandMeasurement], fist: Sequence[HandMeasurement]) -> TuneResult:
    """Build a profile from an open hand's and a fist's measurements.

    Percentiles and medians, not means or extremes, so a few frames caught
    mid-movement don't drag the result. Raises HandProfileError when there
    are too few samples, or when the two poses don't look like an open hand
    and a fist.
    """
    if len(open_hand) < MIN_SAMPLES or len(fist) < MIN_SAMPLES:
        raise HandProfileError("Not enough of your hand was seen. Try again.")

    thresholds: list[float] = []
    kept: list[str] = []
    for index, name in enumerate(FINGERS):
        gap, cut = _between(
            [m.finger_ratios[index] for m in open_hand], [m.finger_ratios[index] for m in fist]
        )
        if gap >= MIN_FINGER_GAP:
            thresholds.append(_clamp(cut, FINGER_RANGE))
        else:
            thresholds.append(STANDARD_PROFILE.finger_thresholds[index])
            kept.append(name)

    if len(FINGERS) - len(kept) < MIN_TUNED_FINGERS:
        raise HandProfileError(
            "Your open hand and your fist looked almost the same. "
            "Spread your fingers wide for the open hand, and curl them tight for the fist."
        )

    profile = HandProfile(
        finger_thresholds=(thresholds[0], thresholds[1], thresholds[2], thresholds[3]),
    )
    return TuneResult(profile=profile, kept_standard=tuple(kept))


# The file ---------------------------------------------------------------------


def hand_profile_path() -> Path:
    return config_dir() / PROFILE_FILENAME


def load_hand_profile(path: Path | None = None) -> HandProfile | None:
    """The saved tuning, or None if the hand hasn't been tuned."""
    path = path or hand_profile_path()
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise HandProfileError(f"The hand tuning file is not valid TOML: {exc}") from exc

    def number(key: str, bounds: tuple[float, float]) -> float:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise HandProfileError(f"The hand tuning file needs a number for {key!r}.")
        if not bounds[0] <= value <= bounds[1]:
            raise HandProfileError(
                f"{key!r} in the hand tuning file must be between {bounds[0]} and {bounds[1]}."
            )
        return float(value)

    fingers = [number(name, FINGER_RANGE) for name in FINGERS]
    return HandProfile(finger_thresholds=(fingers[0], fingers[1], fingers[2], fingers[3]))


def save_hand_profile(profile: HandProfile, path: Path | None = None) -> None:
    """Write the tuning atomically."""
    path = path or hand_profile_path()
    lines = [
        "# palm-lab's tuning to your hand, written by the setup guide.",
        "# Each finger counts as up when its tip is this many times farther from",
        "# the wrist than its middle joint (standard: 1.0).",
        "# Delete this file, or use Settings > Reset tuning, to go back to standard.",
    ]
    for name, value in zip(FINGERS, profile.finger_thresholds, strict=True):
        lines.append(f"{name} = {round(value, 3)!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def reset_hand_profile(path: Path | None = None) -> None:
    """Go back to the standard cut-offs."""
    (path or hand_profile_path()).unlink(missing_ok=True)
