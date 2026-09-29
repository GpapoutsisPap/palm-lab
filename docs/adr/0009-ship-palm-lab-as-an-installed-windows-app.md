# 9. Ship palm-lab as an installed Windows app

Date: 2026-09-28

## Status

Accepted. Supersedes the console-window decision in ADR-0006.

## Context

ADR-0006 packaged palm-lab as a PyInstaller folder whose executable opened a
console window next to the app, so that errors stayed visible while packaging
was new. The window now works, and a console behind it, a generic Python icon
in the taskbar and a folder to unzip all make it look unfinished. People
expect to install an app, find it in the Start menu or on the desktop, see its
own icon, and uninstall it from Settings.

## Decision

### Two programs from one build

The PyInstaller build makes two executables that share one folder of
libraries, so the second costs almost nothing:

- `palm-lab.exe` is the app, with no console window. What it would print goes
  to `%APPDATA%\palm-lab\logs\palm-lab.log` (started afresh past 1 MB), and a
  failure to start shows a Windows error dialog naming that file.
- `palm-lab-cli.exe` has a console, for `doctor`, `config`, `capture` and
  `shortcut`.

Both carry the app icon and version information, so Task Manager and the
file's Properties show "palm-lab" and its version.

### Identity

- The icon is a white hand rising from an indigo tile. Its source is
  `packaging/icon.svg`; `src/palm_lab/assets/palm-lab.ico` holds it at 16 to
  256 px, rendered from the SVG, and is used for the executables, the window,
  the installer and shortcuts.
- The app sets an explicit AppUserModelID (`GpapoutsisPap.palm-lab`), and the
  installer gives its shortcuts the same one, so a pinned taskbar icon and the
  running window are recognised as the same app, even when run from source.
- The title bar is coloured to match the window through
  `DwmSetWindowAttribute`, and follows Windows switching between light and
  dark.

### Installer

The installer is built with Inno Setup (`packaging/palm-lab.iss`, run by
`scripts/build.py --installer`). It installs per user into
`%LOCALAPPDATA%\Programs\palm-lab`, so no administrator rights are needed,
adds a Start menu entry, offers a desktop shortcut, and registers an
uninstaller under Settings > Apps. Settings in `%APPDATA%\palm-lab` survive
uninstalling and upgrades. The AppId in the script must never change, because
Windows uses it to recognise upgrades.

Inno Setup was chosen over WiX and MSIX: it is free, a single script,
well-known for per-user installs, and needs no signing certificate to produce
a working installer. MSIX would give cleaner updates but requires signing.

### Shortcuts from inside the app

Settings has Desktop shortcut and Start menu switches, and
`palm-lab-cli shortcut` does the same from a terminal. Shortcuts are made
with Windows' own `WScript.Shell` object through PowerShell, with folders
asked from Windows, so a Desktop moved into OneDrive is found. Paths travel in
environment variables rather than inside the script, so no name can break it.
From source, the shortcut runs `pythonw -m palm_lab`; from a build, the .exe.
They use the same file names as the installer's, so each sees the other's.

## Consequences

palm-lab installs, starts and uninstalls like any other Windows app, from its
own icon, without a console.

The executables and installer are unsigned, so Windows SmartScreen warns the
first time until a code-signing certificate is bought.

Building the installer needs Inno Setup on the build machine. CI still does
not build the executables or the installer; releases are built by hand.

Errors in the windowed app are no longer on screen; the log file and the
error dialog replace the console, and `palm-lab-cli.exe` remains for
diagnosis.
