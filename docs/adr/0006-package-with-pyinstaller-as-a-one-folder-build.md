# 6. Package with PyInstaller as a one-folder build

Date: 2026-09-28

## Status

Accepted

## Context

palm-lab has to run on Windows machines that do not have Python installed,
started by double-clicking rather than from a terminal. That means freezing
the interpreter, the package and every dependency into something that can be
shipped.

Most of the risk is in MediaPipe. It ships native libraries and internal data
files that import scanning does not find, and the usual failure is a build
that succeeds and then crashes on launch. The hand landmarker model also has
to travel with the app, and paths computed relative to the source files stop
being valid once the code is frozen.

The candidates were PyInstaller, Nuitka, cx_Freeze and Briefcase, each able to
produce either a single file or a folder.

## Decision

The app is built with PyInstaller, as a one-folder build with a console
window, using `packaging/palm-lab.spec` and `scripts/build.py`.

PyInstaller was chosen because it is the most widely used option, has
maintained hooks for OpenCV, and can collect an entire package with
`collect_all`, which is used for MediaPipe. Nuitka compiles to C and can
produce smaller, faster builds, but adds a C compiler to the toolchain and
much longer build times.

One folder rather than one file. A one-file build unpacks its whole contents
to a temporary folder on every launch, which at this size means a slow start
and a large antivirus scan each time. The folder is also what the installer
will package later.

The model is bundled into the build rather than downloaded on first run, so
the app works offline and has no first-run network step. At 7.8 MB it is a
small fraction of the total.

Bundled files are located through `sys._MEIPASS` when frozen, in `config.py`,
alongside every other path. Captures go to the user's config directory when
frozen, because there is no test suite to write them into. `palm-lab doctor`
loads the model and runs one detection on a blank image, which verifies the
native stack inside a build without needing a camera. The launcher keeps the
console open after a failed double-click launch, so the error can be read.

The console window is deliberate for now: while packaging is new, a visible
error is worth more than a clean look.

## Consequences

A build made on a clean development machine works: `palm-lab.exe doctor`
reports the model found in the bundle and hand detection running, with
MediaPipe 1.0.1 and OpenCV 4.11.

The build folder is 295 MB. Most of it is OpenCV, NumPy and MediaPipe. Two
OpenCV packages are currently installed side by side, `opencv-python` from
this project and `opencv-contrib-python` required by MediaPipe, both providing
`cv2`. Removing the duplicate is the obvious first step when reducing size.
`collect_all` also pulls in parts of MediaPipe that are never used, such as
its LLM converter, which produces harmless warnings during the build.

Builds are made by hand on a developer machine. CI does not build the
executable yet, and the model is not in the repository, so a CI build will
need to download it first.

The executable is unsigned, so Windows SmartScreen warns on first launch
until a code-signing certificate is bought.

GitHub's Python `.gitignore` template ignores every `*.spec` file. The build
recipe is exempted explicitly; without that exception it would silently never
be committed.

The console window will be replaced by a windowed build once the tray icon
exists, which needs another way to surface errors, such as a log file or a
notification.
