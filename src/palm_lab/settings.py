"""User-adjustable settings: the camera, how gestures are timed, and sound."""

import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from palm_lab.config import config_dir
from palm_lab.state import DEFAULT_COOLDOWN_SECONDS, DEFAULT_DWELL_SECONDS

SETTINGS_FILENAME = "settings.toml"
MAX_CAMERA_INDEX = 9
DWELL_RANGE = (0.2, 5.0)
COOLDOWN_RANGE = (0.0, 60.0)


class SettingsError(ValueError):
    """Settings that are missing, the wrong type, or out of range."""


@dataclass(frozen=True)
class Settings:
    """Everything the settings panel can change."""

    camera_index: int = 0
    dwell_seconds: float = DEFAULT_DWELL_SECONDS
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    sounds: bool = True

    def as_dict(self) -> dict[str, float | int | bool]:
        return asdict(self)


def settings_path() -> Path:
    return config_dir() / SETTINGS_FILENAME


def _number(data: Mapping[str, object], key: str, default: float) -> float:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SettingsError(f"'{key}' must be a number")
    return float(value)


def settings_from_data(data: Mapping[str, object]) -> Settings:
    """Validate settings from a file or the UI. Missing keys keep defaults."""
    unknown = sorted(set(data) - {"camera_index", "dwell_seconds", "cooldown_seconds", "sounds"})
    if unknown:
        raise SettingsError(f"Unknown setting {unknown[0]!r}")

    camera = data.get("camera_index", 0)
    if isinstance(camera, bool) or not isinstance(camera, int):
        raise SettingsError("'camera_index' must be a whole number")
    if not 0 <= camera <= MAX_CAMERA_INDEX:
        raise SettingsError(f"'camera_index' must be between 0 and {MAX_CAMERA_INDEX}")

    dwell = _number(data, "dwell_seconds", DEFAULT_DWELL_SECONDS)
    if not DWELL_RANGE[0] <= dwell <= DWELL_RANGE[1]:
        low, high = DWELL_RANGE
        raise SettingsError(f"'dwell_seconds' must be between {low} and {high}")

    cooldown = _number(data, "cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
    if not COOLDOWN_RANGE[0] <= cooldown <= COOLDOWN_RANGE[1]:
        low, high = COOLDOWN_RANGE
        raise SettingsError(f"'cooldown_seconds' must be between {low} and {high}")

    sounds = data.get("sounds", True)
    if not isinstance(sounds, bool):
        raise SettingsError("'sounds' must be true or false")

    return Settings(
        camera_index=camera, dwell_seconds=dwell, cooldown_seconds=cooldown, sounds=sounds
    )


def load_settings(path: Path | None = None) -> Settings:
    """Read settings, returning defaults if the file does not exist yet."""
    path = path or settings_path()
    if not path.exists():
        return Settings()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(f"Settings file is not valid TOML: {exc}") from exc
    return settings_from_data(data)


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    """Write settings atomically and return where they went."""
    path = path or settings_path()
    text = (
        "# palm-lab settings, written by the palm-lab window.\n"
        f"camera_index = {settings.camera_index}\n"
        f"dwell_seconds = {settings.dwell_seconds!r}\n"
        f"cooldown_seconds = {settings.cooldown_seconds!r}\n"
        f"sounds = {'true' if settings.sounds else 'false'}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return path
