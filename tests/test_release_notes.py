"""Tests for scripts/release_notes.py, which the release workflow depends on."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from palm_lab.version import __version__

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_notes.py"

CHANGELOG = """# Changelog

## [Unreleased]

## [0.3.0] - 2026-10-01

### Added

- Something new.

## [0.2.0] - 2026-09-29

### Fixed

- Something broken.

[Unreleased]: https://example.com/compare/v0.3.0...HEAD
[0.3.0]: https://example.com/compare/v0.2.0...v0.3.0
"""


@pytest.fixture(scope="module")
def notes() -> ModuleType:
    """Load scripts/release_notes.py, which is not part of the installed package."""
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_version_section_is_extracted_without_its_heading(notes: ModuleType) -> None:
    assert notes.notes_for("0.3.0", CHANGELOG) == "### Added\n\n- Something new."


def test_the_last_section_stops_before_the_link_list(notes: ModuleType) -> None:
    assert notes.notes_for("0.2.0", CHANGELOG) == "### Fixed\n\n- Something broken."


def test_a_version_with_no_section_is_refused(notes: ModuleType) -> None:
    with pytest.raises(notes.ReleaseError, match=r"no '## \[9.9.9\]'"):
        notes.notes_for("9.9.9", CHANGELOG)


def test_an_empty_section_is_refused(notes: ModuleType) -> None:
    with pytest.raises(notes.ReleaseError, match="empty"):
        notes.notes_for("0.3.0", "## [0.3.0] - 2026-10-01\n\n## [0.2.0]\n\n- x\n")


def test_a_tag_is_turned_into_a_version(notes: ModuleType) -> None:
    assert notes.version_from_tag("v0.2.0") == "0.2.0"


@pytest.mark.parametrize("tag", ["0.2.0", "v0.2", "v0.2.0-beta", "release-0.2.0"])
def test_a_badly_formed_tag_is_refused(notes: ModuleType, tag: str) -> None:
    with pytest.raises(notes.ReleaseError, match="should look like"):
        notes.version_from_tag(tag)


def test_a_tag_that_disagrees_with_the_app_version_is_refused(notes: ModuleType) -> None:
    """Otherwise the Release and the About box would show different numbers."""
    with pytest.raises(notes.ReleaseError, match="does not match"):
        notes.release_notes("v0.3.0", CHANGELOG, "0.2.0")


def test_the_version_is_read_from_version_py(notes: ModuleType) -> None:
    assert notes.app_version() == __version__


def test_the_current_version_has_release_notes(notes: ModuleType) -> None:
    """Bumping version.py without a CHANGELOG entry fails here, before a release."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert notes.release_notes(f"v{__version__}", changelog, __version__)


def test_the_command_prints_notes_or_explains_why_not(
    notes: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    assert notes.main([f"v{__version__}"]) == 0
    assert capsys.readouterr().out.strip()

    assert notes.main(["v99.0.0"]) == 1
    assert "does not match" in capsys.readouterr().err

    assert notes.main([]) == 2
