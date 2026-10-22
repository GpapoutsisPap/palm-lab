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
    "sunset": Palette("Sunset", "#FCE4D2", "#1E1220"),
    "neon": Palette("Neon", "#DAF5CF", "#070D09"),
    "ocean": Palette("Ocean", "#D2EDF5", "#071A26"),
    "grape": Palette("Grape", "#E6DBFB", "#160F24"),
    "rose": Palette("Rose", "#FADDE9", "#200C16"),
    "graphite": Palette("Graphite", "#DADFE6", "#111316"),
}


def background(palette: str, dark: bool) -> str:
    """The page background (and window frame) for a palette, falling back to the default."""
    chosen = PALETTES.get(palette, PALETTES[DEFAULT_PALETTE])
    return chosen.dark_background if dark else chosen.light_background
