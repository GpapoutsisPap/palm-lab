<p align="center">
  <img src="packaging/icon.svg" width="96" alt="">
</p>

<h1 align="center">palm-lab</h1>

<p align="center">Run shortcuts on your Windows PC by showing a hand gesture to your webcam.</p>

---

Hold up a peace sign and your browser, notes and music open. Make a fist to
pause what's playing. palm-lab watches your camera, recognises your gestures,
and runs the actions you snap together for each one, all on your own computer.

## Features

- **Four gestures built in:** peace sign, fist, open palm and thumbs up.
- **Add your own:** hold a new hand shape up twice, name it, and it gets its
  own icon. palm-lab tells you straight away if you already use that shape.
- **Actions that snap together:** open an app from your Start menu, open a
  website, or press keys (media keys, volume, any combination). Drag action
  pieces into a gesture, reorder them, and test them without the camera.
- **Live view:** see what the camera sees, the hand it found, how far through
  a hold you are, and what ran, or why nothing did.
- **Pause:** stop gestures for 15 minutes to a few hours, with the camera off,
  from the window or the icon by the clock.
- **Make it yours:** light or dark theme, and your own CSS to restyle
  anything, typed right in Settings.
- **Always ready:** close the window and palm-lab can keep running by the
  clock, and it can start with Windows so your gestures work from sign-in.
- **Feels at home on Windows 11:** light and dark themes, your accent colour,
  a Start menu entry and an optional desktop shortcut.
- **For programmers:** gestures live in a plain TOML file, and everything the
  window does is also available from the command line.
- **Private:** frames never leave your PC. Hand tracking runs locally with
  Google's MediaPipe.

## Install

Download `palm-lab-setup-X.Y.Z.exe` from the
[latest release](https://github.com/GpapoutsisPap/palm-lab/releases/latest)
and run it. No administrator rights are needed. The app is not code-signed yet, so
Windows SmartScreen may ask you to confirm the first time.

A webcam is needed. A phone works too, through an app such as DroidCam.

## Build from source

Requires Windows 10 or 11, Python 3.12 and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/GpapoutsisPap/palm-lab
cd palm-lab
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run palm-lab doctor          # checks everything, and says how to get the hand model
uv run palm-lab                 # opens the window
```

Build the app and its installer (the installer needs
[Inno Setup](https://jrsoftware.org/isinfo.php): `winget install JRSoftware.InnoSetup`):

```powershell
uv run python scripts/build.py --installer
```

The programs land in `dist\palm-lab\` and the installer in `dist\`.

## Custom CSS

Settings > Appearance > Custom CSS restyles the window with your own CSS.
Changes show as you type and are saved to `custom.css` in palm-lab's settings
folder (`palm-lab config` prints where), which you can also edit in any
editor. Sharing a theme is sharing that file.

Most looks come from changing a few variables:

```css
:root {
  --accent: #E3008C;        /* buttons, switches, highlights */
  --radius: 10px;           /* corner rounding */
  --font: "Comic Sans MS";  /* body text */
}

/* Only in the dark theme */
:root[data-theme="dark"] {
  --mica: #101030;          /* window background */
  --card: #1A1A40;
}
```

| Variables | What they colour |
| --- | --- |
| `--mica`, `--layer`, `--card`, `--card-hover`, `--flyout` | Backgrounds, from the window to cards and pop-ups |
| `--text-1`, `--text-2`, `--text-3` | Text, from main to faint |
| `--accent`, `--accent-text`, `--on-accent` | The accent, text in it, and text on it |
| `--stroke`, `--divider`, `--control`, `--control-stroke` | Borders, dividers and input boxes |
| `--success`, `--caution`, `--critical` | Status colours |
| `--piece-launch`, `--piece-web`, `--piece-keys`, `--piece-hat` | The action pieces |
| `--radius`, `--radius-overlay`, `--radius-piece` | Corner rounding |
| `--font`, `--font-display`, `--font-mono` | Fonts |

Anything else can be targeted by class, such as `.gesture`, `.card`, `.nav`
or `.piece`; with `palm-lab ui --debug`, right-click > Inspect shows them.

If your CSS hides the window's controls, press **Ctrl+Shift+X** to turn it
off, or start palm-lab with `palm-lab ui --no-custom-css`.

## Command line

| Command | What it does |
| --- | --- |
| `palm-lab` | Open the window (the default) |
| `palm-lab ui --background` | Start hidden by the clock with tracking on |
| `palm-lab ui --no-custom-css` | Open without your custom CSS, to fix it |
| `palm-lab doctor` | Check the model, libraries and hand detection |
| `palm-lab config` | Show where configuration lives and what is bound |
| `palm-lab shortcut [--start-menu] [--startup] [--remove]` | Add or remove the desktop, Start menu and Start with Windows shortcuts |
| `palm-lab run` | Watch the camera in a plain preview window |
| `palm-lab capture GESTURE` | Save landmark samples for testing |

In an installed copy, use `palm-lab-cli.exe` for these.

## Development

```powershell
uv run pytest        # tests, with coverage
uv run ruff check .  # lint
uv run mypy          # strict type checking
```

Design decisions are recorded in [docs/adr](docs/adr), and what changed in
each version in [CHANGELOG.md](CHANGELOG.md). The window is plain
HTML, CSS and JavaScript in `src/palm_lab/ui/static`, shown by
[pywebview](https://pywebview.flowrl.com/) and talking to Python through
`src/palm_lab/ui/api.py`.

## Releasing

The version number lives in one place, `src/palm_lab/version.py`. Settings
shows it, and the executables, the installer and the package all read it.

1. Change `__version__` in `src/palm_lab/version.py`, following
   [Semantic Versioning](https://semver.org/): a new feature raises the middle
   number (0.2.0 to 0.3.0), a fix raises the last (0.2.0 to 0.2.1).
2. In [CHANGELOG.md](CHANGELOG.md), move the notes under `[Unreleased]` into a
   new `## [X.Y.Z] - YYYY-MM-DD` section, and add its link at the bottom.
3. Merge that into `main`, then tag the merge and push the tag:

   ```powershell
   git checkout main
   git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

The [Release workflow](.github/workflows/release.yml) then builds the
installer on Windows and publishes it on the releases page, with the
changelog section as its notes. It stops without publishing if the tag does
not match `version.py` or the changelog has no section for it.

## Licence

MIT, see [LICENSE](LICENSE). palm-lab builds on other open-source work, listed
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
