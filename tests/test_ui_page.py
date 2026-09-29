"""Tests for assembling the window's page."""

import re
from pathlib import Path

import pytest

from palm_lab import config
from palm_lab.ui.app import (
    DARK_BACKGROUND,
    LIGHT_BACKGROUND,
    load_page,
    window_background,
)


def write_static(folder: Path, html: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(html, encoding="utf-8")
    (folder / "app.css").write_text("body { color: red; }", encoding="utf-8")
    (folder / "app.js").write_text("console.log('hi');", encoding="utf-8")
    return folder


def test_css_and_js_are_inlined(tmp_path: Path) -> None:
    html = '<head><link rel="stylesheet" href="app.css"></head><script src="app.js"></script>'
    page = load_page(write_static(tmp_path, html))
    assert "<style>\nbody { color: red; }\n</style>" in page
    assert "<script>\nconsole.log('hi');\n</script>" in page
    assert "app.css" not in page and "app.js" not in page


def test_a_page_without_the_expected_tags_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must reference app.css and app.js"):
        load_page(write_static(tmp_path, "<html></html>"))


def test_the_real_page_assembles() -> None:
    """The shipped index.html, app.css and app.js load and inline cleanly."""
    page = load_page(config.ui_static_dir())
    assert page.startswith("<!doctype html>")
    assert "<style>" in page and "<script>" in page


def test_every_element_the_script_uses_exists() -> None:
    """app.js looks elements up by id; a renamed id would break the window."""
    static = config.ui_static_dir()
    script = (static / "app.js").read_text(encoding="utf-8")
    html = (static / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([\w-]+)"', html))
    used = set(re.findall(r'\$\("([\w-]+)"\)', script))
    assert used, "expected the script to look up elements"
    assert used <= ids, f"missing from index.html: {sorted(used - ids)}"


def test_static_files_are_ascii() -> None:
    """Non-ASCII text is written as escapes, so no encoding can garble it."""
    for name in ("index.html", "app.css", "app.js"):
        (config.ui_static_dir() / name).read_bytes().decode("ascii")


def test_window_background_follows_the_windows_theme() -> None:
    assert window_background(lambda: 0) == DARK_BACKGROUND
    assert window_background(lambda: 1) == LIGHT_BACKGROUND
    assert window_background(lambda: None) == LIGHT_BACKGROUND


def test_window_backgrounds_match_the_page() -> None:
    """The window frame and the page background must be the same colours."""
    css = (config.ui_static_dir() / "app.css").read_text(encoding="utf-8")
    light, dark = re.findall(r"--mica: (#[0-9A-Fa-f]{6});", css)
    assert (light, dark) == (LIGHT_BACKGROUND, DARK_BACKGROUND)
