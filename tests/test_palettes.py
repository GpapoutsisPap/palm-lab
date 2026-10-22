"""Tests for the colour palettes: Python and the stylesheet agree, and every one stays readable."""

import re
from pathlib import Path

import pytest

from palm_lab import config
from palm_lab.palettes import DEFAULT_PALETTE, PALETTES, background
from palm_lab.ui.app import load_page, window_background

CSS = (config.ui_static_dir() / "app.css").read_text(encoding="utf-8")
GLOW_STRENGTH = {"light": 0.16, "dark": 0.20}  # --glow-strength


def tokens(selector: str) -> dict[str, str]:
    """The colour variables set in the CSS block that starts with this selector."""
    start = CSS.index(selector + " {")
    block = CSS[start : CSS.index("}", start)]
    return dict(re.findall(r"--([\w-]+): (#[0-9A-Fa-f]{6});", block))


def light_block(palette: str) -> dict[str, str]:
    return tokens(f':where([data-palette="{palette}"])')


def dark_block(palette: str) -> dict[str, str]:
    return tokens(
        f':where([data-theme="dark"][data-palette="{palette}"], '
        f'[data-theme="dark"] [data-palette="{palette}"])'
    )


def mix(top: str, base: str, share: float) -> str:
    """The colour you see with `share` of top over base (how the glow lands on the page)."""
    a, b = (tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) for c in (top, base))
    return "#" + "".join(
        f"{round(x * share + y * (1 - share)):02X}" for x, y in zip(a, b, strict=True)
    )


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio between two #RRGGBB colours."""

    def luminance(colour: str) -> float:
        def channel(value: int) -> float:
            c = value / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


COLOURED = [name for name in PALETTES if name != DEFAULT_PALETTE]


def test_there_is_a_default_and_a_handful_of_palettes() -> None:
    assert DEFAULT_PALETTE == "windows"
    assert {"sunset", "neon"} <= set(PALETTES)
    assert len({p.label for p in PALETTES.values()}) == len(PALETTES)


@pytest.mark.parametrize("palette", COLOURED)
def test_the_window_frame_matches_the_page(palette: str) -> None:
    """Python colours the title bar before the page draws, so they must agree."""
    assert light_block(palette)["mica"] == PALETTES[palette].light_background
    assert dark_block(palette)["mica"] == PALETTES[palette].dark_background
    assert window_background(theme="dark", palette=palette) == background(palette, dark=True)


@pytest.mark.parametrize("palette", COLOURED)
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_palette_stays_readable(palette: str, theme: str) -> None:
    t = light_block(palette) if theme == "light" else dark_block(palette)
    glow = mix(t["glow"], t["layer"], GLOW_STRENGTH[theme])  # the page's top corner
    # Body text, on everything it sits on: cards, the page, and the sidebar's gradient.
    for surface in ("card", "mica", "backdrop-end"):
        assert contrast(t["text-1"], t[surface]) >= 7.0, surface
    for surface in ("mica", "backdrop-end", "layer", "card-2"):
        assert contrast(t["text-2"], t[surface]) >= 4.5, surface
    assert contrast(t["text-2"], glow) >= 4.5
    for surface in ("card", "layer"):  # hints only, as faint as the Windows default
        assert contrast(t["text-3"], t[surface]) >= 3.0, surface
    assert contrast(t["title"], t["layer"]) >= 4.5
    assert contrast(t["title"], glow) >= 4.5
    # The accent.
    assert contrast(t["on-accent"], t["accent"]) >= 4.5  # text on accent buttons
    for surface in ("card", "layer", "mica"):
        assert contrast(t["accent-text"], t[surface]) >= 4.5, surface  # links, accent text
    for surface in ("card", "layer"):
        assert contrast(t["accent"], t[surface]) >= 3.0, surface  # switches, rings, focus


def test_palettes_look_different_from_each_other() -> None:
    """No two palettes share a page background or an accent, in either theme."""
    for block in (light_block, dark_block):
        for key in ("mica", "layer", "accent", "title"):
            values = [block(palette)[key] for palette in COLOURED]
            assert len(set(values)) == len(values), key


@pytest.mark.parametrize("palette", COLOURED)
def test_light_and_dark_set_the_same_colours(palette: str) -> None:
    assert set(light_block(palette)) == set(dark_block(palette))


def test_the_pieces_keep_their_colours_in_every_palette() -> None:
    """Each kind of piece stays recognisable whatever the palette."""
    for palette in COLOURED:
        assert not any(name.startswith("piece-") for name in light_block(palette))


def test_the_page_starts_in_the_saved_palette() -> None:
    page = load_page(config.ui_static_dir(), theme="dark", palette="sunset")
    assert '<html data-palette="sunset" data-theme="dark" lang="en">' in page


def test_an_unknown_palette_is_not_written_into_the_page(tmp_path: Path) -> None:
    page = load_page(config.ui_static_dir(), palette='x" onload="alert(1)')
    assert "data-palette" not in page.split(">", 2)[1]


def test_an_unknown_palette_falls_back_to_the_default_background() -> None:
    assert background("nope", dark=False) == PALETTES[DEFAULT_PALETTE].light_background
