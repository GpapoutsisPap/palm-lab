"""The colour palettes in Settings > Appearance > Colours.

The colours themselves live in app.css. Python only needs each palette's
page background (--mica), to colour the window frame and title bar to match
before the page has drawn; tests/test_palettes.py checks the two agree.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    label: str
    light_background: str
    dark_background: str


DEFAULT_PALETTE = "windows"

# In the order Settings shows them. "windows" keeps the Windows accent colour.
PALETTES: dict[str, Palette] = {
    "windows": Palette("Windows", "#F3F3F3", "#202020"),
    "sunset": Palette("Sunset", "#F3E9E1", "#2F261F"),
    "neon": Palette("Neon", "#E2EFE7", "#202F26"),
    "ocean": Palette("Ocean", "#E0EEF1", "#1E2A2D"),
    "grape": Palette("Grape", "#EBE7F3", "#27242F"),
    "rose": Palette("Rose", "#F2E5EC", "#2E2328"),
    "graphite": Palette("Graphite", "#E8E9EB", "#242526"),
}


def background(palette: str, dark: bool) -> str:
    """The page background (and window frame) for a palette, falling back to the default."""
    chosen = PALETTES.get(palette, PALETTES[DEFAULT_PALETTE])
    return chosen.dark_background if dark else chosen.light_background
