<p align="center">
  <img src="packaging/icon.svg" width="96" alt="">
</p>

<h1 align="center">palm-lab</h1>

<p align="center">Run shortcuts on your Windows PC by showing a hand gesture to your webcam.</p>

---

Hold up a peace sign and your browser, notes and music open. Make a fist to
pause what's playing. palm-lab watches your camera, recognises four gestures,
and runs the actions you snap together for each one, all on your own computer.

## Features

- **Four gestures:** peace sign, fist, open palm and thumbs up.
- **Actions that snap together:** open an app from your Start menu, open a
  website, or press keys (media keys, volume, any combination). Drag action
  pieces into a gesture, reorder them, and test them without the camera.
- **Live view:** see what the camera sees, the hand it found, and what ran.
- **Feels at home on Windows 11:** light and dark themes, your accent colour,
  a Start menu entry and an optional desktop shortcut.
- **For programmers:** gestures live in a plain TOML file, and everything the
  window does is also available from the command line.
- **Private:** frames never leave your PC. Hand tracking runs locally with
  Google's MediaPipe.

## Install

Download `palm-lab-setup-X.Y.Z.exe` from the
[releases page](https://github.com/GpapoutsisPap/palm-lab/releases) once a
release is published (until then, build it yourself as below) and run it. No
administrator rights are needed. The app is not code-signed yet, so
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

## Command line

| Command | What it does |
| --- | --- |
| `palm-lab` | Open the window (the default) |
| `palm-lab doctor` | Check the model, libraries and hand detection |
| `palm-lab config` | Show where configuration lives and what is bound |
| `palm-lab shortcut [--start-menu] [--remove]` | Add or remove the desktop and Start menu shortcuts |
| `palm-lab run` | Watch the camera in a plain preview window |
| `palm-lab capture GESTURE` | Save landmark samples for testing |

In an installed copy, use `palm-lab-cli.exe` for these.

## Development

```powershell
uv run pytest        # tests, with coverage
uv run ruff check .  # lint
uv run mypy          # strict type checking
```

Design decisions are recorded in [docs/adr](docs/adr). The window is plain
HTML, CSS and JavaScript in `src/palm_lab/ui/static`, shown by
[pywebview](https://pywebview.flowrl.com/) and talking to Python through
`src/palm_lab/ui/api.py`.

## Licence

MIT, see [LICENSE](LICENSE). palm-lab builds on other open-source work, listed
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
