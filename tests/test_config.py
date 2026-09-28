"""Tests for the configuration location and first-run defaults."""

import sys
from pathlib import Path

import pytest

from palm_lab import config
from palm_lab.actions.models import parse_bindings


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point palm-lab at a throwaway config directory for one test."""
    target = tmp_path / "palm-lab"
    monkeypatch.setenv("PALM_LAB_CONFIG_DIR", str(target))
    return target


def test_override_wins_over_the_platform_default(config_home: Path) -> None:
    """PALM_LAB_CONFIG_DIR takes precedence, which is what makes this testable."""
    assert config.config_dir() == config_home


def test_windows_default_follows_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows the config lives under %APPDATA%."""
    monkeypatch.delenv("PALM_LAB_CONFIG_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\someone\AppData\Roaming")
    assert config.config_dir().name == config.APP_NAME
    assert "Roaming" in str(config.config_dir())


def test_posix_default_follows_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Elsewhere it follows XDG_CONFIG_HOME."""
    monkeypatch.delenv("PALM_LAB_CONFIG_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/somewhere/config")
    assert config.config_dir() == Path("/somewhere/config") / config.APP_NAME


def test_bindings_path_sits_inside_the_config_directory(config_home: Path) -> None:
    """The bindings file is named consistently inside the config directory."""
    assert config.bindings_path() == config_home / config.BINDINGS_FILENAME


def test_first_run_creates_a_default_file(config_home: Path) -> None:
    """A fresh install gets a starting bindings file, and is told it was made."""
    assert not config_home.exists()
    path, created = config.ensure_bindings_file()
    assert created
    assert path.exists()
    assert path.parent == config_home


def test_the_written_default_is_valid(config_home: Path) -> None:
    """The shipped default must parse, or first run is broken for everyone."""
    path, _ = config.ensure_bindings_file()
    bindings = parse_bindings(path.read_text(encoding="utf-8"))
    assert bindings
    assert all(b.actions for b in bindings)


def test_an_existing_file_is_never_overwritten(config_home: Path) -> None:
    """Second run must not clobber whatever the user has configured."""
    path, _ = config.ensure_bindings_file()
    path.write_text(
        '[[binding]]\ngesture="fist"\nname="Mine"\n'
        '[[binding.action]]\ntype="launch"\ntarget="notepad"\n',
        encoding="utf-8",
    )
    again, created = config.ensure_bindings_file()
    assert not created
    assert again == path
    assert "Mine" in path.read_text(encoding="utf-8")


def test_nested_directories_are_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole path is built, not just the last directory."""
    deep = tmp_path / "a" / "b" / "palm-lab"
    monkeypatch.setenv("PALM_LAB_CONFIG_DIR", str(deep))
    path, created = config.ensure_bindings_file()
    assert created
    assert path.exists()


def test_default_file_is_written_as_utf8(config_home: Path) -> None:
    """Written config must decode as UTF-8; anything else breaks the build."""
    path, _ = config.ensure_bindings_file()
    path.read_bytes().decode("utf-8")


def test_windows_falls_back_when_appdata_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Windows install with no APPDATA still resolves to a sensible path."""
    monkeypatch.delenv("PALM_LAB_CONFIG_DIR", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    assert config.config_dir().parts[-3:] == ("AppData", "Roaming", config.APP_NAME)


def test_not_frozen_when_running_from_source() -> None:
    """The test suite itself runs from source, never from a build."""
    assert not config.is_frozen()


def test_model_is_found_beside_the_source_when_not_frozen() -> None:
    """From a checkout, the model sits in the package's assets folder."""
    expected = Path(config.__file__).parent / "assets" / config.MODEL_FILENAME
    assert config.model_path() == expected


def test_model_is_found_in_the_bundle_when_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inside a PyInstaller build, bundled files live under sys._MEIPASS."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert config.is_frozen()
    assert config.model_path() == tmp_path / "palm_lab" / "assets" / config.MODEL_FILENAME


def test_captures_go_to_the_test_suite_from_a_checkout() -> None:
    """While developing, new captures land where the tests will pick them up."""
    assert config.fixture_dir().parts[-2:] == ("tests", "fixtures")


def test_captures_go_to_the_profile_when_frozen(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A packaged app has no tests folder, so captures go to the config dir."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert config.fixture_dir() == config_home / config.CAPTURES_DIRNAME
