"""What each action piece's target may be, checked when bindings are saved.

Every piece keeps the same simple shape in bindings.toml, a type and a text
target, so the file stays easy to edit by hand:

    type = "volume"        target = "30"          (set to 30%)
    type = "wait"          target = "1.5"         (seconds)
    type = "settings"      target = "bluetooth"   (a Windows Settings page)

These functions turn a target into what the runner needs, or raise
ValueError with a message that names the problem. They do no Windows calls,
so they're tested on every platform. The lists of choices (OPTIONS) also
fill the suggestions in the window's editor.
"""

from dataclasses import dataclass

WAIT_RANGE = (0.1, 60.0)
MAX_TEXT_CHARS = 2000


def parse_wait(target: str) -> float:
    """Seconds to wait, like "2" or "1.5"."""
    try:
        seconds = float(target.strip().removesuffix("s").strip())
    except ValueError:
        raise ValueError(f"wait {target!r} must be a number of seconds") from None
    low, high = WAIT_RANGE
    if not low <= seconds <= high:
        raise ValueError(f"wait must be between {low:g} and {high:g} seconds")
    return seconds


def check_text(target: str) -> str:
    """Text to type. Any characters, any language; just not a whole essay."""
    if len(target) > MAX_TEXT_CHARS:
        raise ValueError(f"text to type is limited to {MAX_TEXT_CHARS} characters")
    return target


# Volume ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VolumeCommand:
    """Set the speakers to a level, or mute or unmute the speakers or microphone."""

    microphone: bool = False
    level: int | None = None  # 0..100, speakers only
    mute: bool | None = None


VOLUME_WORDS = {
    "mute": VolumeCommand(mute=True),
    "unmute": VolumeCommand(mute=False),
    "mic_mute": VolumeCommand(microphone=True, mute=True),
    "mic_unmute": VolumeCommand(microphone=True, mute=False),
}


def parse_volume(target: str) -> VolumeCommand:
    """ "30" or "30%" sets the speakers to 30%; a word mutes or unmutes."""
    text = target.strip().lower()
    if text in VOLUME_WORDS:
        return VOLUME_WORDS[text]
    try:
        level = int(text.removesuffix("%").strip())
    except ValueError:
        words = ", ".join(VOLUME_WORDS)
        raise ValueError(
            f"volume {target!r} must be a level from 0 to 100, or one of: {words}"
        ) from None
    if not 0 <= level <= 100:
        raise ValueError("volume must be between 0 and 100")
    return VolumeCommand(level=level)


# Windows -------------------------------------------------------------------------

SYSTEM_COMMANDS = {
    "lock": "Lock the PC",
    "show_desktop": "Show the desktop",
    "screenshot": "Take a screenshot",
}


def parse_system(target: str) -> str:
    command = target.strip().lower()
    if command not in SYSTEM_COMMANDS:
        raise ValueError(
            f"{target!r} is not something palm-lab can do to Windows "
            f"(expected one of: {', '.join(SYSTEM_COMMANDS)})"
        )
    return command


# Windows 11 Settings pages that open with an ms-settings: link, from Microsoft
# Learn's "Launch the Windows Settings app" list. Pages Windows 11 removed
# (tabletmode, backup, defaultbrowsersettings) are left out.
SETTINGS_PAGES = {
    "sound": "Sound",
    "apps-volume": "Volume mixer",
    "sound-devices": "Sound devices",
    "display": "Display",
    "nightlight": "Night light",
    "bluetooth": "Bluetooth & devices",
    "network-wifi": "Wi-Fi",
    "network-status": "Network & internet",
    "notifications": "Notifications",
    "quiethours": "Focus and Do not disturb",
    "powersleep": "Power & sleep",
    "batterysaver": "Battery saver",
    "defaultapps": "Default apps",
    "appsfeatures": "Installed apps",
    "startupapps": "Startup apps",
    "privacy-webcam": "Camera privacy",
    "privacy-microphone": "Microphone privacy",
    "windowsupdate": "Windows Update",
    "personalization-background": "Background",
    "personalization-colors": "Colours",
    "taskbar": "Taskbar",
    "mousetouchpad": "Mouse",
    "keyboard": "Keyboard",
    "clipboard": "Clipboard",
    "storagesense": "Storage",
    "dateandtime": "Date & time",
    "about": "About this PC",
}
SETTINGS_SCHEME = "ms-settings:"


def settings_uri(target: str) -> str:
    """A page name from the list, or a full ms-settings: link for any other page."""
    text = target.strip()
    if text.lower() in SETTINGS_PAGES:
        return SETTINGS_SCHEME + text.lower()
    if text.lower().startswith(SETTINGS_SCHEME) and len(text) > len(SETTINGS_SCHEME):
        return text
    raise ValueError(
        f"{target!r} is not a Settings page: pick one from the list, "
        "or write a full ms-settings: link"
    )


# Folders -------------------------------------------------------------------------

# Windows' own names for these folders (Known Folder IDs, KnownFolders.h). Asking
# Windows finds them even when OneDrive or the user has moved them elsewhere.
KNOWN_FOLDERS = {
    "downloads": ("Downloads", "374DE290-123F-4565-9164-39C4925E467B"),
    "documents": ("Documents", "FDD39AD0-238F-46AF-ADB4-6C85480369C7"),
    "desktop": ("Desktop", "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"),
    "pictures": ("Pictures", "33E28130-4E1E-4676-835A-98395C3BC3BB"),
    "music": ("Music", "4BD8D571-6D19-48D3-BE97-422220080E43"),
    "videos": ("Videos", "18989B1D-99B5-455B-841C-AB7C74E4DDFC"),
}


def check_path(target: str) -> str:
    """A known folder's name, or a path to a folder or file. Existence is checked when run."""
    text = target.strip()
    if not text:
        raise ValueError("a folder or file to open is needed")
    return text


# The window's suggestions -------------------------------------------------------------

OPTIONS: dict[str, list[tuple[str, str]]] = {
    "volume": [
        *((str(level), f"{level}%") for level in (0, 25, 50, 75, 100)),
        ("mute", "Mute speakers"),
        ("unmute", "Unmute speakers"),
        ("mic_mute", "Mute microphone"),
        ("mic_unmute", "Unmute microphone"),
    ],
    "system": list(SYSTEM_COMMANDS.items()),
    "settings": list(SETTINGS_PAGES.items()),
    "open_path": [(key, label) for key, (label, _) in KNOWN_FOLDERS.items()],
}
