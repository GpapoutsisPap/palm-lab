# 10. Version and release from git tags

Date: 2026-09-29

## Status

Accepted. Replaces the "releases are built by hand" consequence of ADR-0009.

## Context

palm-lab now has an installer, but nothing published it: someone wanting to
try the app had to install Python and build it. The version number was also
written twice, in `pyproject.toml` and `src/palm_lab/version.py`, so the two
could drift apart, and no commit was marked as a release.

## Decision

- **One place for the version.** `src/palm_lab/version.py` holds it.
  `pyproject.toml` reads it through hatchling's `dynamic = ["version"]`, and
  the Settings page, the executables' file properties and the installer
  already read the same file.
- **Semantic Versioning.** MAJOR.MINOR.PATCH, starting from 0.x while the app
  is young: a feature raises MINOR, a fix raises PATCH, and 1.0.0 waits until
  others have used it.
- **A changelog written for users.** `CHANGELOG.md` follows Keep a Changelog.
  Each version's section becomes its release notes.
- **Git tags mark releases.** A tag `vX.Y.Z` on `main` is a release.
- **GitHub Actions publishes them.** Pushing a tag runs
  `.github/workflows/release.yml` on a Windows runner: it checks the tag
  against `version.py` and extracts the notes (`scripts/release_notes.py`),
  runs the tests, downloads the hand model, installs Inno Setup, builds the
  installer and creates the GitHub Release with it attached.

A test fails when `version.py` names a version with no changelog section, so
a forgotten entry is caught in CI rather than at release time.

Building by hand and uploading was the alternative. It needs no setup, but
depends on one PC having Inno Setup and the model, and makes it easy to
publish an installer that does not match any commit.

## Consequences

A release is a version bump, a changelog entry and one pushed tag, and every
release is built the same way from exactly the tagged commit.

Releases are still unsigned, so SmartScreen warns on first run (ADR-0009).

A mistaken tag can be deleted (`git push origin :refs/tags/vX.Y.Z`) along with
its Release, but a version that people have downloaded should not be reused:
fix it in the next PATCH version instead.
