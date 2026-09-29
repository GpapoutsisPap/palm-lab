"""Small Windows integrations: theme, accent colour, title bar and app identity.

Every function here is safe to call on any platform. Off Windows they do
nothing or return a sensible default, so the rest of the app never has to
check which system it is on.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
ACCENT_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"

# Identifies palm-lab to the taskbar, so its windows group under its own icon
# instead of under python.exe when running from source.
APP_ID = "GpapoutsisPap.palm-lab"

# DwmSetWindowAttribute: title bar background colour (Windows 11 and later).
DWMWA_CAPTION_COLOR = 35

# Windows' default blue, lightest to darkest: Light3, Light2, Light1, Accent,
# Dark1, Dark2, Dark3. Used when the system palette cannot be read.
DEFAULT_ACCENT_PALETTE = (
    "#99EBFF",
    "#4CC2FF",
    "#0091F8",
    "#0078D4",
    "#0067C0",
    "#003E92",
    "#001A68",
)

RegistryReader = Callable[[str, str], object]


def read_registry(key: str, name: str) -> object:
    """A value from HKEY_CURRENT_USER, or None if it is missing or not on Windows."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            value, _ = winreg.QueryValueEx(handle, name)
    except OSError:
        return None
    return value


def apps_use_light_theme(read: RegistryReader = read_registry) -> int | None:
    """Windows' app mode: 1 for light, 0 for dark, None if unknown."""
    value = read(PERSONALIZE_KEY, "AppsUseLightTheme")
    return value if isinstance(value, int) else None


def palette_from_bytes(data: bytes) -> tuple[str, ...] | None:
    """Decode AccentPalette: seven RGBA colours, lightest first, as #RRGGBB."""
    if len(data) < 28:
        return None
    return tuple(f"#{data[i]:02X}{data[i + 1]:02X}{data[i + 2]:02X}" for i in range(0, 28, 4))


def accent_palette(read: RegistryReader = read_registry) -> tuple[str, ...]:
    """The user's accent colour in the seven shades Windows derives from it."""
    value = read(ACCENT_KEY, "AccentPalette")
    palette = palette_from_bytes(value) if isinstance(value, bytes) else None
    return palette or DEFAULT_ACCENT_PALETTE


def colorref(hex_colour: str) -> int:
    """Convert #RRGGBB to the 0x00BBGGRR integer Windows uses for colours."""
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return (blue << 16) | (green << 8) | red


def set_caption_colour(hwnd: int, hex_colour: str) -> bool:
    """Colour a window's title bar. Returns False where that is unsupported."""
    if sys.platform != "win32":
        return False
    import ctypes

    value = ctypes.c_int(colorref(hex_colour))
    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(value), ctypes.sizeof(value)
    )
    return bool(result == 0)


def set_app_id(app_id: str = APP_ID) -> None:
    """Give this process its own taskbar identity."""
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def show_error(title: str, message: str) -> None:
    """A plain Windows error dialog, for when there is no window or console."""
    if sys.platform != "win32":
        return
    import ctypes

    mb_iconerror = 0x10
    ctypes.windll.user32.MessageBoxW(None, message, title, mb_iconerror)


def open_folder(path: Path) -> None:
    """Show a folder in File Explorer (or the desktop's file manager elsewhere)."""
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", str(path)])
