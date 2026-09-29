"""Print the release notes for a version tag, taken from CHANGELOG.md.

Usage:   uv run python scripts/release_notes.py v0.2.0

The release workflow runs this before building anything. It stops the release
if the tag does not match the version in src/palm_lab/version.py, or if
CHANGELOG.md has no section for that version, so a release can never go out
with the wrong number in the app or without saying what changed.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_FILE = ROOT / "src" / "palm_lab" / "version.py"


class ReleaseError(Exception):
    """The tag, the version and the changelog do not agree."""


def app_version(version_file: Path = VERSION_FILE) -> str:
    match = re.search(r'__version__ = "([^"]+)"', version_file.read_text(encoding="utf-8"))
    if match is None:
        raise ReleaseError(f"No __version__ found in {version_file}")
    return match.group(1)


def version_from_tag(tag: str) -> str:
    """Turn a tag like v0.2.0 into 0.2.0. Tags must be v + MAJOR.MINOR.PATCH."""
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
    if match is None:
        raise ReleaseError(f"Tag {tag!r} should look like v1.2.3")
    return match.group(1)


def notes_for(version: str, changelog: str) -> str:
    """The body of the '## [version]' section, without its heading."""
    heading = re.search(rf"^## \[{re.escape(version)}\].*$", changelog, re.MULTILINE)
    if heading is None:
        raise ReleaseError(f"CHANGELOG.md has no '## [{version}]' section")
    rest = changelog[heading.end() :]
    # The section runs until the next version heading or the link list at the end.
    end = re.search(r"^(## \[|\[[^\]]+\]: )", rest, re.MULTILINE)
    body = (rest[: end.start()] if end else rest).strip()
    if not body:
        raise ReleaseError(f"The '## [{version}]' section of CHANGELOG.md is empty")
    return body


def release_notes(tag: str, changelog: str, version: str) -> str:
    tagged = version_from_tag(tag)
    if tagged != version:
        raise ReleaseError(
            f"Tag {tag} does not match version {version} in src/palm_lab/version.py. "
            "Update version.py, or tag the version it holds."
        )
    return notes_for(tagged, changelog)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    try:
        notes = release_notes(argv[0], CHANGELOG.read_text(encoding="utf-8"), app_version())
    except ReleaseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
