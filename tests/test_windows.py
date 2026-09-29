"""Tests for the Windows integrations, with the registry faked out."""

import sys

import pytest

from palm_lab import windows
from palm_lab.windows import (
    ACCENT_KEY,
    DEFAULT_ACCENT_PALETTE,
    PERSONALIZE_KEY,
    accent_palette,
    apps_use_light_theme,
    colorref,
    palette_from_bytes,
)

# Windows' own default AccentPalette value: eight RGBA colours.
DEFAULT_BYTES = bytes.fromhex("99ebff004cc2ff000091f8000078d4000067c000003e9200001a6800f7630c00")


def registry(values: dict[tuple[str, str], object]) -> windows.RegistryReader:
    return lambda key, name: values.get((key, name))


def test_theme_reads_the_app_mode() -> None:
    assert apps_use_light_theme(registry({(PERSONALIZE_KEY, "AppsUseLightTheme"): 0})) == 0
    assert apps_use_light_theme(registry({(PERSONALIZE_KEY, "AppsUseLightTheme"): 1})) == 1
    assert apps_use_light_theme(registry({})) is None


def test_the_default_palette_decodes_to_windows_blue() -> None:
    assert palette_from_bytes(DEFAULT_BYTES) == DEFAULT_ACCENT_PALETTE


def test_accent_follows_the_user_colour() -> None:
    purple = bytes.fromhex("e3c6ff00c79bff00a970ff008a4df5006b36d1004c24a8002e157a00")
    palette = accent_palette(registry({(ACCENT_KEY, "AccentPalette"): purple}))
    assert palette[3] == "#8A4DF5"
    assert len(palette) == 7


@pytest.mark.parametrize("value", [None, b"short", "not bytes"])
def test_accent_falls_back_to_the_default(value: object) -> None:
    assert accent_palette(registry({(ACCENT_KEY, "AccentPalette"): value})) == (
        DEFAULT_ACCENT_PALETTE
    )


def test_colorref_is_blue_green_red() -> None:
    assert colorref("#F3F3F3") == 0xF3F3F3
    assert colorref("#0078D4") == 0xD47800


@pytest.mark.skipif(sys.platform == "win32", reason="does real work on Windows")
def test_everything_is_harmless_off_windows() -> None:
    assert windows.read_registry(PERSONALIZE_KEY, "AppsUseLightTheme") is None
    assert windows.set_caption_colour(0, "#202020") is False
    windows.set_app_id()
    windows.show_error("title", "message")


@pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows registry")
def test_the_real_registry_can_be_read() -> None:
    assert apps_use_light_theme() in (0, 1, None)
    assert len(accent_palette()) == 7
