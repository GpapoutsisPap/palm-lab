; Inno Setup script for the palm-lab installer.
;
; Build with:  uv run python scripts/build.py --installer
; Needs:       Inno Setup 6.3 or later  (winget install JRSoftware.InnoSetup)
; Output:      dist/palm-lab-setup-X.Y.Z.exe
;
; The installer copies the PyInstaller folder into the user's own programs
; folder (no administrator rights needed), adds palm-lab to the Start menu,
; optionally to the desktop, and registers an uninstaller in Settings > Apps.
; User settings in %APPDATA%\palm-lab are left alone on uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Never change AppId: Windows uses it to recognise upgrades of the same app.
AppId={{46C3D0B9-0D22-4408-AA16-990A8F7DF4DF}
AppName=palm-lab
AppVersion={#AppVersion}
AppVerName=palm-lab {#AppVersion}
AppPublisher=Giwrgos Papoutsis
AppPublisherURL=https://github.com/GpapoutsisPap/palm-lab
AppSupportURL=https://github.com/GpapoutsisPap/palm-lab/issues
AppUpdatesURL=https://github.com/GpapoutsisPap/palm-lab/releases
DefaultDirName={autopf}\palm-lab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=palm-lab-setup-{#AppVersion}
SetupIconFile=..\src\palm_lab\assets\palm-lab.ico
UninstallDisplayIcon={app}\palm-lab.exe
UninstallDisplayName=palm-lab
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; palm-lab can keep running in the notification area. Its single-instance
; mutex (src/palm_lab/single_instance.py) lets setup see that and ask to close
; it before updating or uninstalling.
AppMutex=GpapoutsisPap.palm-lab

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\palm-lab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; The AppUserModelID matches the one the app sets for itself, so a pinned
; taskbar icon and the running window are recognised as the same app.
Name: "{autoprograms}\palm-lab"; Filename: "{app}\palm-lab.exe"; AppUserModelID: "GpapoutsisPap.palm-lab"
Name: "{autodesktop}\palm-lab"; Filename: "{app}\palm-lab.exe"; AppUserModelID: "GpapoutsisPap.palm-lab"; Tasks: desktopicon

[UninstallDelete]
; Shortcuts the app itself can make from Settings. The installer's own Start
; menu and desktop entries are removed without being listed here.
Type: files; Name: "{userstartup}\palm-lab.lnk"
Type: files; Name: "{userdesktop}\palm-lab.lnk"

[Run]
Filename: "{app}\palm-lab.exe"; Description: "{cm:LaunchProgram,palm-lab}"; Flags: nowait postinstall skipifsilent
