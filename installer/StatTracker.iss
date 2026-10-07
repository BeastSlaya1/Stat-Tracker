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
#define MyAppVersion "4.0.23"
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
 ; Offer current-user or all-users installation on every interactive run.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousPrivileges=no
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

[Messages]
ConfirmUninstall=Remove %1 and its local saved matches, settings and sign-in data?%n%nFor an all-users installation, local Stat Tracker data is removed for all Windows users. Synced online matches and exported reports are kept.

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Everything flet build produced — the exe, its DLLs, Lib, site-packages,
; the lot — copied as-is into the install folder. This is exactly the
; "loose folder full of DLLs" from before; the installer's whole job is
; to put it somewhere proper and manage it as one unit instead of you
; zipping/unzipping it by hand.
Source: "uninstall-data.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceExeDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Scope, Params: String;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    if IsAdminInstallMode then Scope := 'AllUsers' else Scope := 'CurrentUser';
    Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{app}\uninstall-data.ps1') + '" -Scope ' + Scope;
    if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    begin
      Log('Some Stat Tracker local data could not be removed.');
      if not UninstallSilent then
        MsgBox('Some Stat Tracker local data could not be removed. Close Stat Tracker in all Windows sessions and check its app-data folders. Linked or inaccessible folders are retained.', mbInformation, MB_OK);
    end;
  end;
end;
