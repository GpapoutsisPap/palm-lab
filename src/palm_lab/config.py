"""Where palm-lab keeps its user configuration, and what it writes on first run."""

import os
import sys
from pathlib import Path

APP_NAME = "palm-lab"
BINDINGS_FILENAME = "bindings.toml"
MODEL_FILENAME = "hand_landmarker.task"
ICON_FILENAME = "palm-lab.ico"
CAPTURES_DIRNAME = "captures"
LOGS_DIRNAME = "logs"
PROJECT_URL = "https://github.com/GpapoutsisPap/palm-lab"

DEFAULT_BINDINGS_TOML = """\
# palm-lab gesture bindings.
#
# Each [[binding]] maps one gesture to a list of actions, run in order with a
# short gap between them. A failing action does not stop the ones after it.
#
# Gestures:     peace, fist, open_palm, thumbs_up
# Action types: launch    - start an application (a known name or a full path)
#               open_url  - open a URL in the default browser
#               hotkey    - press a key or combination
#
# Open app accepts any name from your Start menu (Steam, Discord, a game...),
# a program on your PATH, or a full path to an .exe.
# Hotkey examples:    media_play_pause, media_next, media_previous,
#                     volume_up, volume_down, volume_mute,
#                     ctrl+alt+t, win+d, alt+tab, f5

[[binding]]
gesture = "peace"
name = "Morning setup"

  [[binding.action]]
  type = "launch"
  target = "spotify"

  [[binding.action]]
  type = "open_url"
  target = "https://youtube.com"

# [[binding]]
# gesture = "fist"
# name = "Play or pause"
#
#   [[binding.action]]
#   type = "hotkey"
#   target = "media_play_pause"
"""


def is_frozen() -> bool:
    """True when running from a PyInstaller build rather than from source."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def package_dir() -> Path:
    """The palm_lab package folder, from source or inside a build.

    In a PyInstaller build, bundled files are unpacked under sys._MEIPASS, which
    has nothing to do with where this source file used to live.
    """
    if is_frozen():
        # getattr, because the attribute only exists inside a build.
        return Path(getattr(sys, "_MEIPASS", "")) / "palm_lab"
    return Path(__file__).parent


def resource_dir() -> Path:
    """Directory holding bundled read-only files such as the hand model."""
    return package_dir() / "assets"


def ui_static_dir() -> Path:
    """Directory holding the window's HTML, CSS and JavaScript."""
    return package_dir() / "ui" / "static"


def model_path() -> Path:
    """Full path to the hand landmarker model, from source or a build."""
    return resource_dir() / MODEL_FILENAME


def icon_path() -> Path:
    """The app icon, used for the window and for shortcuts made from source."""
    return resource_dir() / ICON_FILENAME


def fixture_dir() -> Path:
    """Where `palm-lab capture` saves landmark fixtures.

    From a source checkout, captures go straight into the test suite's
    fixtures. A packaged app has no test suite, so they go to a captures folder
    in the user's config directory instead.
    """
    repo_tests = Path(__file__).resolve().parents[2] / "tests"
    if not is_frozen() and repo_tests.is_dir():
        return repo_tests / "fixtures"
    return config_dir() / CAPTURES_DIRNAME


def config_dir() -> Path:
    """The directory holding this user's palm-lab configuration.

    %APPDATA%\\palm-lab on Windows, ~/.config/palm-lab elsewhere. Overridable
    with the PALM_LAB_CONFIG_DIR environment variable, which makes tests and
    portable installs possible without touching the real user profile.
    """
    override = os.environ.get("PALM_LAB_CONFIG_DIR")
    if override:
        return Path(override)

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_NAME


def log_dir() -> Path:
    """Where the windowed app writes what would otherwise go to a console."""
    return config_dir() / LOGS_DIRNAME


MODEL_PATH = model_path()


def bindings_path() -> Path:
    """Full path to the bindings file, whether or not it exists yet."""
    return config_dir() / BINDINGS_FILENAME


def ensure_bindings_file() -> tuple[Path, bool]:
    """Return the bindings path, creating a commented default if absent.

    The second element is True when a file was just created, so the caller can
    tell the user where to look.
    """
    path = bindings_path()
    if path.exists():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_BINDINGS_TOML, encoding="utf-8")
    return path, True
