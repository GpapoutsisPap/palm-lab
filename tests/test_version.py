import re

from palm_lab.version import __version__

SEMVER_PATTERN = r"\d+\.\d+\.\d+"


def test_version_is_a_string() -> None:
    """The version must be a string, not a number or tuple."""
    assert isinstance(__version__, str)


def test_version_follows_semver() -> None:
    """The version must look like MAJOR.MINOR.PATCH."""
    assert re.fullmatch(SEMVER_PATTERN, __version__)