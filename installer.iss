; BillSmart 1.0.0 — Inno Setup 6 script (Windows x64)
; Build:  powershell -ExecutionPolicy Bypass -File .\build.ps1 -Installer
; Output: installer-output\BillSmart-Setup-1.0.0.exe
; Uninstall: Control Panel > Programs > Programs and Features > BillSmart > Uninstall
;            (shop data in %APPDATA%\BillSmart is preserved on uninstall)

#define AppVersion "1.0.0"
#define AppName "BillSmart"
#define AppPublisher "BillSmart"
#define AppExe "BillSmart.exe"

[Setup]
AppId={{3F2A1B4C-9D7E-4A6B-8C3F-BILLSMART100}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer-output
OutputBaseFilename=BillSmart-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
; Shop data lives in %APPDATA%\BillSmart and is intentionally NOT removed.
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} - Billing and Inventory for Retail
SetupIconFile=assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\BillSmart\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// WebView2 (Edge) is required by the BillSmart window. It ships with Windows 10 1803+ / 11;
// warn with a download link if the runtime key is missing.
function NeedsWebView2(): Boolean;
begin
  Result :=
    (not RegKeyExists(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\ClientState\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')) and
    (not RegKeyExists(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\ClientState\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')) and
    (not RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\ClientState\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'));
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if NeedsWebView2() then
    MsgBox(
      'BillSmart uses the Microsoft Edge WebView2 runtime, which was not detected.' + #13#10 +
      'If the app shows a blank window, install WebView2 from:' + #13#10 +
      'https://developer.microsoft.com/microsoft-edge/webview2/',
      mbInformation, MB_OK);
end;
