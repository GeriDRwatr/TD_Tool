[Setup]
AppName=TDTool
AppVersion=1.0
AppPublisher=TDTool
DefaultDirName={autopf}\TDTool
DefaultGroupName=TDTool
OutputDir=installer_output
OutputBaseFilename=TDTool_Setup_v1.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\TDTool.exe
; Requires admin so we can write to HKLM
PrivilegesRequired=admin

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english";   MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Створити ярлик на робочому столі";   GroupDescription: "Додаткові параметри"
Name: "setdefault";  Description: "Встановити як стандартний переглядач PDF"; GroupDescription: "Асоціація файлів"; Flags: unchecked

[Files]
Source: "dist\TDTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TDTool";          Filename: "{app}\TDTool.exe"
Name: "{commondesktop}\TDTool";  Filename: "{app}\TDTool.exe"; Tasks: desktopicon

; ── Registry ──────────────────────────────────────────────────────────────────
; All keys go to HKLM so the registration is visible to all users
; and Windows shows TDTool in "Open with" for everyone.

[Registry]
; ProgId — describes the file type handler
Root: HKLM; Subkey: "SOFTWARE\Classes\TDTool.PDF";                           ValueType: string; ValueName: "";                  ValueData: "PDF Document";                             Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\Classes\TDTool.PDF\DefaultIcon";               ValueType: string; ValueName: "";                  ValueData: "{app}\TDTool.exe,0"
Root: HKLM; Subkey: "SOFTWARE\Classes\TDTool.PDF\shell\open";                ValueType: string; ValueName: "FriendlyAppName";    ValueData: "TDTool"
Root: HKLM; Subkey: "SOFTWARE\Classes\TDTool.PDF\shell\open\command";        ValueType: string; ValueName: "";                  ValueData: """{app}\TDTool.exe"" ""%1"""

; Link ProgId to .pdf extension — this is what adds the entry to "Open with"
Root: HKLM; Subkey: "SOFTWARE\Classes\.pdf\OpenWithProgids";                       ValueType: string; ValueName: "TDTool.PDF";   ValueData: ""

; App capabilities — required for "Default apps" Settings page
Root: HKLM; Subkey: "SOFTWARE\TDTool\Capabilities";                          ValueType: string; ValueName: "ApplicationName";        ValueData: "TDTool";           Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\TDTool\Capabilities";                          ValueType: string; ValueName: "ApplicationDescription";  ValueData: "PDF Viewer & Editor"
Root: HKLM; Subkey: "SOFTWARE\TDTool\Capabilities\FileAssociations";         ValueType: string; ValueName: ".pdf";               ValueData: "TDTool.PDF"
Root: HKLM; Subkey: "SOFTWARE\RegisteredApplications";                             ValueType: string; ValueName: "TDTool";        ValueData: "SOFTWARE\TDTool\Capabilities"

[Run]
Filename: "{app}\TDTool.exe"; Description: "Запустити TDTool"; Flags: nowait postinstall skipifsilent

[Code]
procedure SHChangeNotify(wEventId: Integer; uFlags: Cardinal;
                         dwItem1: Cardinal; dwItem2: Cardinal);
  external 'SHChangeNotify@shell32.dll stdcall';

var
  ErrorCode: Integer;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // Refresh Windows shell so "Open with" list updates immediately
    SHChangeNotify($08000000, $0000, 0, 0);

    // If user chose "Set as default", open Windows Settings → Default apps
    if WizardIsTaskSelected('setdefault') then
      ShellExecAsOriginalUser('open', 'ms-settings:defaultapps', '', '', SW_SHOW,
                              ewNoWait, ErrorCode);
  end;
end;
