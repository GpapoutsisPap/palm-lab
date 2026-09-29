"""Tests for the user's custom CSS file."""

from pathlib import Path

import pytest

from palm_lab.custom_css import (
    MAX_CUSTOM_CSS_BYTES,
    CustomCssError,
    custom_css_path,
    load_custom_css,
    save_custom_css,
)


def test_no_file_means_no_custom_css(tmp_path: Path) -> None:
    assert load_custom_css(tmp_path / "custom.css") == ""


def test_css_round_trips_exactly(tmp_path: Path) -> None:
    """Non-English text comes back as it was typed."""
    css = ':root {\n  --accent: #E3008C;\n}\n/* Ελληνικά */ .x::after { content: "✋"; }\n'
    path = save_custom_css(css, tmp_path / "deep" / "custom.css")
    assert load_custom_css(path) == css
    assert [p.name for p in path.parent.iterdir()] == ["custom.css"]


def test_windows_line_endings_from_notepad_become_plain_newlines(tmp_path: Path) -> None:
    """The window's text box works in \\n, whatever editor last saved the file."""
    path = tmp_path / "custom.css"
    path.write_bytes(b"body {\r\n  color: red;\r\n}\r\n")
    assert load_custom_css(path) == "body {\n  color: red;\n}\n"


def test_a_file_saved_by_notepad_with_a_bom_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "custom.css"
    path.write_bytes(b"\xef\xbb\xbfbody { color: red; }")
    assert load_custom_css(path) == "body { color: red; }"


def test_too_much_css_is_refused_on_save(tmp_path: Path) -> None:
    with pytest.raises(CustomCssError, match="at most"):
        save_custom_css("a" * (MAX_CUSTOM_CSS_BYTES + 1), tmp_path / "custom.css")
    assert not (tmp_path / "custom.css").exists()


def test_an_oversized_file_is_not_used(tmp_path: Path) -> None:
    path = tmp_path / "custom.css"
    path.write_text("a" * (MAX_CUSTOM_CSS_BYTES + 1), encoding="utf-8")
    with pytest.raises(CustomCssError, match="not used"):
        load_custom_css(path)


def test_it_lives_with_the_other_config_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PALM_LAB_CONFIG_DIR", str(tmp_path))
    assert custom_css_path() == tmp_path / "custom.css"
