; Inno Setup script for Media Downloader. Build it with scripts/build_installer.py, which
; passes the version and builds what this script picks up from build\.
; Decisions: docs/decisions/0018 (where the external programs go) and the stage 5 plan.

#ifndef AppVersion
  #error Run scripts/build_installer.py: it passes AppVersion and VersionNumbers
#endif

#define AppExe "MediaDownloader.exe"
; backend/app/main.py creates it; AppMutex below and the update wait in [Code] check it.
#define AppMutexName "MediaDownloaderAppMutex"
; The external programs live outside the install folder, so app updates leave a yt-dlp
; the user updated alone. backend/app/infrastructure/binaries/ looks in the same place.
#define BinDir "{localappdata}\media-downloader\bin"

[Setup]
AppId={{8868B185-9E8C-45CE-BE13-008F638FA2E1}
AppName=Media Downloader
AppVersion={#AppVersion}
AppPublisher=kdwjzh
AppPublisherURL=https://github.com/kdwjzh/media-downloader
VersionInfoVersion={#VersionNumbers}
; Per-user install into %LOCALAPPDATA%\Programs, no administrator rights.
PrivilegesRequired=lowest
DefaultDirName={autopf}\Media Downloader
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
#ifdef TestBuild
; A test build asks 127.0.0.1 for updates (docs/decisions/0019): never upload it.
OutputBaseFilename=MediaDownloader-Setup-{#AppVersion}-TEST
#else
OutputBaseFilename=MediaDownloader-Setup-{#AppVersion}
#endif
; Lists every file compiled into setup; scripts/build_installer.py checks the test marker
; is not in it. Kept in build\ so output\ holds only the files to upload.
OutputManifestFile={#SourcePath}..\build\installer-manifest.txt
SetupIconFile=..\brand\icons\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName=Media Downloader
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
; The app creates this mutex (backend/app/main.py). Setup and the uninstaller ask the user
; to close the app instead of closing it for them: that could cut a download short.
AppMutex={#AppMutexName}
CloseApplications=no
; Cancelling halfway cannot be undone: Inno's rollback does not bring back replaced files or
; the _internal folder [InstallDelete] removed, so the app would not start (ADR 0019).
AllowCancelDuringInstall=no
; Follow the Windows display language, like the app does.
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "zhtw"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"

[CustomMessages]
en.WebView2Missing=Media Downloader needs the Microsoft Edge WebView2 Runtime, and it was not found on this computer.%n%nDownload it from Microsoft: https://developer.microsoft.com/microsoft-edge/webview2/%n%nInstall Media Downloader anyway?
zhtw.WebView2Missing=Media Downloader 需要 Microsoft Edge WebView2 Runtime，這台電腦上找不到。%n%n請到微軟網站下載：https://developer.microsoft.com/microsoft-edge/webview2/%n%n仍要繼續安裝 Media Downloader 嗎？
en.DeleteData=Also delete your settings, download history and log files?%n%nChoose No to keep them for a later reinstall.
zhtw.DeleteData=要一併刪除設定、下載歷史紀錄與記錄檔嗎？%n%n選「否」會保留，之後重新安裝還能使用。

[InstallDelete]
; An upgrade must not leave files of the previous version behind.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\build\dist\MediaDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}\licenses"; DestName: "MediaDownloader-LICENSE.txt"; Flags: ignoreversion
; No ignoreversion: Inno compares the file versions and keeps an existing yt-dlp.exe that
; is as new or newer (the user updated it), replacing only an older one.
Source: "..\build\bin\yt-dlp.exe"; DestDir: "{#BinDir}"
; FFmpeg and Deno are pinned: always the version this release was tested with.
Source: "..\build\bin\ffmpeg.exe"; DestDir: "{#BinDir}"; Flags: ignoreversion
Source: "..\build\bin\deno.exe"; DestDir: "{#BinDir}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Media Downloader"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,Media Downloader}"; Flags: nowait postinstall skipifsilent

[Run]
; An update the app started (/UPDATE=1 with /SILENT): open the new version when done.
Filename: "{app}\{#AppExe}"; Flags: nowait skipifnotsilent; Check: IsAppUpdate

[UninstallDelete]
; The programs belong to the app; yt-dlp.exe.old (left by a yt-dlp update) is not tracked.
Type: filesandordirs; Name: "{#BinDir}"
; Installers the app downloaded to update itself.
Type: filesandordirs; Name: "{localappdata}\media-downloader\updates"
Type: dirifempty; Name: "{localappdata}\media-downloader"

[Code]
const
  WebView2Key = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2(RootKey: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, WebView2Key, 'pv', Version)
    and (Version <> '') and (Version <> '0.0.0.0');
end;

// The app starts setup with /UPDATE=1 (backend/app/infrastructure/app_installer.py).
function IsAppUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

function InitializeSetup: Boolean;
var
  Waited: Integer;
begin
  Result := True;
  if IsAppUpdate then
  begin
    // The app closes right after starting us. Setup checks AppMutex once, after this
    // function, and would otherwise ask the user to close an app that is already closing.
    // After 10 s it asks after all: the app is stuck, and the user can close it.
    Waited := 0;
    while CheckForMutexes('{#AppMutexName}') and (Waited < 10000) do
    begin
      Sleep(200);
      Waited := Waited + 200;
    end;
    Exit; // the app ran, so WebView2 is there
  end;
  // A machine-wide WebView2 is registered in the 32-bit view; a per-user one under HKCU.
  if not (HasWebView2(HKLM32) or HasWebView2(HKCU)) then
    Result := MsgBox(CustomMessage('WebView2Missing'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Settings and history are kept unless the user says otherwise; a silent uninstall keeps them.
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    if MsgBox(CustomMessage('DeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\media-downloader'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\media-downloader'), True, True, True);
    end;
end;
