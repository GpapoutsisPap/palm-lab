"""Tests for finding installed applications by name."""

from pathlib import Path

import pytest

from palm_lab.actions.apps import KNOWN_APPS, installed_apps, resolve_app, start_menu_dirs
from palm_lab.actions.errors import AppNotFoundError


def no_path(name: str) -> str | None:
    return None


@pytest.fixture
def start_menu(tmp_path: Path) -> Path:
    """A fake Start menu laid out like a real one."""
    root = tmp_path / "Programs"
    for relative in (
        "Steam/Steam.lnk",
        "Steam/Uninstall Steam.lnk",
        "Discord Inc/Discord.lnk",
        "Visual Studio Code/Visual Studio Code.lnk",
        "Visual Studio Code/Visual Studio Code Readme.lnk",
        "Games/Counter-Strike 2.url",
        "Games/Assassin's Creed Unity.url",
        "Microsoft Office/Word.lnk",
        "Microsoft Office/WordPad.lnk",
        "Tools/notes.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return root


@pytest.fixture
def apps(start_menu: Path) -> dict[str, Path]:
    found = installed_apps([start_menu])
    # NTFS reserves ':' for alternate data streams, so a shortcut file can
    # never actually have one on disk -- but a game's own title can, and
    # resolve_app must still find it when typed exactly. Simulate the
    # Start menu entry without trying to write an illegal filename.
    found["Assassin's Creed: Unity"] = start_menu / "Games" / "Assassin's Creed Unity.url"
    return found


# Scanning ---------------------------------------------------------------------


def test_shortcuts_are_found_in_nested_folders(apps: dict[str, Path]) -> None:
    assert {"Steam", "Discord", "Counter-Strike 2", "Word"} <= set(apps)


def test_uninstallers_and_readmes_are_not_offered(apps: dict[str, Path]) -> None:
    assert "Uninstall Steam" not in apps
    assert "Visual Studio Code Readme" not in apps


def test_only_shortcuts_count(apps: dict[str, Path]) -> None:
    assert "notes" not in apps


def test_start_menu_folders_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = tmp_path / "pd" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    shared.mkdir(parents=True)
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "pd"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "missing"))
    assert start_menu_dirs() == [shared]


# Resolving ----------------------------------------------------------------------


def test_built_in_names_win(apps: dict[str, Path]) -> None:
    """Steam's own protocol works even if its shortcut was deleted."""
    assert resolve_app("Steam", apps, no_path) == KNOWN_APPS["steam"]


def test_exact_start_menu_name_ignores_case(apps: dict[str, Path]) -> None:
    assert resolve_app("discord", apps, no_path) == str(apps["Discord"])


def test_a_game_with_a_colon_is_still_found_by_name(apps: dict[str, Path]) -> None:
    title = "Assassin's Creed: Unity"
    assert resolve_app(title, apps, no_path) == str(apps[title])


def test_paths_and_urls_pass_through(apps: dict[str, Path]) -> None:
    for target in (r"C:\Games\thing.exe", "steam://rungameid/730", "tool.exe"):
        assert resolve_app(target, apps, no_path) == target


def test_programs_on_path_are_found(apps: dict[str, Path]) -> None:
    def which(name: str) -> str | None:
        return r"C:\Tools\code.cmd" if name == "code" else None

    assert resolve_app("code", apps, which) == r"C:\Tools\code.cmd"


def test_a_unique_partial_name_is_enough(apps: dict[str, Path]) -> None:
    assert resolve_app("counter", apps, no_path) == str(apps["Counter-Strike 2"])


def test_surrounding_spaces_are_ignored(apps: dict[str, Path]) -> None:
    assert resolve_app("  Discord ", apps, no_path) == str(apps["Discord"])


def test_an_ambiguous_name_asks_which(apps: dict[str, Path]) -> None:
    """ "word" is inside both Word and WordPad, but exactly matches Word."""
    assert resolve_app("word", apps, no_path) == str(apps["Word"])
    with pytest.raises(AppNotFoundError) as caught:
        resolve_app("wor", apps, no_path)
    assert caught.value.suggestions == ("Word", "WordPad")
    assert "Did you mean Word or WordPad?" in caught.value.user_message()


def test_a_typo_gets_a_close_suggestion(apps: dict[str, Path]) -> None:
    with pytest.raises(AppNotFoundError) as caught:
        resolve_app("Discrod", apps, no_path)
    assert caught.value.suggestions == ("Discord",)
    assert "Did you mean Discord?" in caught.value.user_message()


def test_nothing_close_explains_what_to_type(apps: dict[str, Path]) -> None:
    with pytest.raises(AppNotFoundError) as caught:
        resolve_app("zzzqqq", apps, no_path)
    assert caught.value.suggestions == ()
    assert "as it appears in the Start menu" in caught.value.user_message()
