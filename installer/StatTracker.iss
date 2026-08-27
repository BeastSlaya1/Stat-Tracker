; Stat Tracker — Windows installer script (Inno Setup)
;
; This builds a real installer: installs into Program Files, adds a Start
; Menu shortcut (and optional Desktop shortcut), and registers a proper
; uninstaller that shows up in Settings -> Apps (or classic Control Panel
; "Programs and Features") exactly like any normally-installed app — the
; thing this whole script exists to give you, instead of "unzip a folder
; and double-click the exe inside it."
;
; ── One-time setup ──────────────────────────────────────────────────────
; 1. Install Inno Setup (free): https://jrsoftware.org/isdl.php
; 2. Build the app first, same as always:
;      flet clean
;      flet build windows --project "Stat Tracker"
;    This script expects the result at build\windows\ (relative to this
;    .iss file's own folder — see SourceExeDir below). If your build
;    output lands somewhere else, adjust that one line.
;
; ── Building the installer ──────────────────────────────────────────────
; Either open this file in the Inno Setup Compiler (IDE) and press
; Compile (Ctrl+F9), or from the command line. The exact path to ISCC.exe
; varies — Inno Setup 7 can land in a per-machine location (needs admin)
; or a per-user one, depending on how it was installed. If unsure, find
; it directly: run `where /r C:\ ISCC.exe` in cmd. Common locations:
;      "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" installer\StatTracker.iss
;      "C:\Program Files\Inno Setup 7\ISCC.exe" installer\StatTracker.iss
;      "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" installer\StatTracker.iss
; Output lands in installer\Output\StatTracker-Setup.exe — THAT single file
; is what you hand to someone. They run it, click through a normal
; Windows install wizard, and get a real Start Menu entry + working
; uninstaller. No zip, no loose folder of DLLs.

#define MyAppName "Stat Tracker"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "St Charles College"
#define MyAppExeName "Stat Tracker.exe"
; Path to the flet build output, relative to this .iss file's own folder
; (installer\StatTracker.iss -> ..\build\windows is the project's build\windows\)
#define SourceExeDir "..\build\windows"

[Setup]
; A fixed GUID identifies this app to Windows across versions/reinstalls —
; do not change this once you've shipped a version, or Windows will treat
; future updates as a totally different, separately-listed app instead of
; upgrading in place.
AppId={{A6D9B2E4-6C3F-4E2D-9B0A-1F8C7D5E4A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-machine install (Program Files, needs admin) — the standard choice
; for something that should behave like a normal installed application.
; Switch to "lowest" + DefaultDirName={autopf}\... -> {localappdata}\...
; instead if you'd rather it install per-user with no admin prompt.
PrivilegesRequired=admin
; The app itself (flet build windows) is a 64-bit executable, so the
; installer should be too — this directive is new in Inno Setup 7 (it
; doesn't exist in 6, where installers defaulted to 32-bit regardless of
; what they contained). Building a matching x64 installer also makes
; ArchitecturesAllowed/ArchitecturesInstallIn64BitMode default correctly
; on their own, so nothing else needs to change here.
SetupArchitecture=x64
OutputDir=Output
OutputBaseFilename=StatTracker-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Shown in Settings -> Apps and Programs & Features, same as any app:
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Everything flet build produced — the exe, its DLLs, Lib, site-packages,
; the lot — copied as-is into the install folder. This is exactly the
; "loose folder full of DLLs" from before; the installer's whole job is
; to put it somewhere proper and manage it as one unit instead of you
; zipping/unzipping it by hand.
Source: "{#SourceExeDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

; No [UninstallDelete] section needed: match data now saves to
; %LOCALAPPDATA%\Stat Tracker (see storage.py's _data_dir()), outside the
; install folder entirely — exactly so an uninstall of the *program*
; doesn't touch saved match history, and a reinstall/update picks the
; same data back up automatically. If you ever want an uninstall to also
; wipe saved data, add it back pointing at that folder specifically, not
; {app}.
