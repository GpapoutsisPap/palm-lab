# PyInstaller build recipe for palm-lab.
#
# Build with:  uv run python scripts/build.py
# Output:      dist/palm-lab/palm-lab.exe      the app, no console window
#              dist/palm-lab/palm-lab-cli.exe  the same app with a console, for
#                                              commands such as `doctor`
# Both programs share one folder of libraries, so the second costs almost
# nothing.

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).parent  # noqa: F821  (SPECPATH is injected by PyInstaller)
SRC = ROOT / "src"
ASSETS = SRC / "palm_lab" / "assets"
MODEL = ASSETS / "hand_landmarker.task"
ICON = ASSETS / "palm-lab.ico"
UI_STATIC = SRC / "palm_lab" / "ui" / "static"

VERSION = re.search(
    r'__version__ = "([^"]+)"', (SRC / "palm_lab" / "version.py").read_text(encoding="utf-8")
).group(1)
VERSION_TUPLE = tuple(int(part) for part in VERSION.split(".")) + (0,)


def version_info(filename):
    """What Windows shows in the file's Properties and in Task Manager."""
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=VERSION_TUPLE, prodvers=VERSION_TUPLE),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Giwrgos Papoutsis"),
                            StringStruct("FileDescription", "palm-lab"),
                            StringStruct("FileVersion", VERSION),
                            StringStruct("InternalName", filename.removesuffix(".exe")),
                            StringStruct("LegalCopyright", "Copyright (c) 2026 Giwrgos Papoutsis"),
                            StringStruct("OriginalFilename", filename),
                            StringStruct("ProductName", "palm-lab"),
                            StringStruct("ProductVersion", VERSION),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )


# MediaPipe ships native libraries and data files that PyInstaller's import
# scanning does not find on its own. Without this the build succeeds and the
# executable then crashes on launch.
mp_datas, mp_binaries, mp_hiddenimports = collect_all("mediapipe")

# pywebview drives the window through Microsoft's WebView2, loaded via a .NET
# bridge. Its loader DLLs and helper modules also need collecting explicitly.
wv_datas, wv_binaries, wv_hiddenimports = collect_all("webview")

# pystray (the notification-area icon) is LGPL-3.0: ship its licence texts,
# which live in its package metadata, alongside it.
tray_licences = copy_metadata("pystray")

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=[*mp_binaries, *wv_binaries],
    datas=[
        (str(MODEL), "palm_lab/assets"),
        (str(ICON), "palm_lab/assets"),
        (str(UI_STATIC), "palm_lab/ui/static"),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
        *mp_datas,
        *wv_datas,
        *tray_licences,
    ],
    # pystray picks its Windows backend at runtime, out of sight of the scanner.
    hiddenimports=[*mp_hiddenimports, *wv_hiddenimports, "pystray._win32"],
    excludes=["pytest", "mypy", "ruff", "pre_commit", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

app = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="palm-lab",
    console=False,
    icon=str(ICON),
    version=version_info("palm-lab.exe"),
    upx=False,
)

cli = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="palm-lab-cli",
    console=True,
    icon=str(ICON),
    version=version_info("palm-lab-cli.exe"),
    upx=False,
)

coll = COLLECT(  # noqa: F821
    app,
    cli,
    a.binaries,
    a.datas,
    name="palm-lab",
    upx=False,
)
