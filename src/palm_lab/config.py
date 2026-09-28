"""Where palm-lab keeps its user configuration, and what it writes on first run."""

import os
import sys
from pathlib import Path

APP_NAME = "palm-lab"
BINDINGS_FILENAME = "bindings.toml"

DEFAULT_BINDINGS_TOML = """\
# palm-lab gesture bindings.
#
# Each [[binding]] maps one gesture to a list of actions, run in order with a
# short gap between them. A failing action does not stop the ones after it.
#
# Gestures:     peace, fist, open_palm, thumbs_up
# Action types: launch    - start an application (a known name or a full path)
#               open_url  - open a URL in the default browser
#               hotkey    - send a keystroke (not implemented yet)
#
# Known launch names: spotify, notepad, notes, calculator, explorer

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
# name = "Open notes"
# step_delay_seconds = 0.4
#
#   [[binding.action]]
#   type = "launch"
#   target = "notes"
"""


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
