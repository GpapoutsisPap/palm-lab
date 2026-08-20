# 2. Pin the project to Python 3.12

Date: 2026-08-20

## Status

Accepted

## Context

MediaPipe and its dependency numpy ship compiled C++ extensions rather than
pure Python. This means they require a prebuilt binary wheel for each
combination of Python version and platform, and those wheels are published
some time after a new Python release.

Installing the project on Python 3.13 fails for this reason. No matching wheel
exists, so pip falls back to building numpy from source, which requires a C
compiler that a typical Windows machine does not have. The failure surfaces as
a Meson build error listing missing compilers, which does not obviously point
at the underlying version mismatch. This was discovered by hitting it rather
than from any documentation.

## Decision

The project targets Python 3.12 exclusively for now.

This is enforced in three places: `requires-python = ">=3.12"` in
`pyproject.toml`, `python-version: "3.12"` in the CI workflow, and the local
development virtual environment, which is created with `uv venv --python 3.12`.

We will revisit this once MediaPipe publishes Windows wheels for a later Python
version. Until then, a newer interpreter is not a supported configuration.

## Consequences

Local development, CI, and the declared package metadata all agree on a single
Python version, which removes a class of bugs that only appear in one
environment. Installs are reproducible across machines.

The cost is that the project cannot use language features introduced after
3.12, and contributors whose system Python is newer must install 3.12
specifically before they can work on it. This adds a step to onboarding that
belongs in the contributing guide.

This constraint is inherited from a dependency rather than chosen, so it is
likely to become stale. If it is not revisited, the project will drift further
behind current Python for no reason other than inattention.
