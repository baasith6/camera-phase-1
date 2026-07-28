#define AppName "ONEVO Local Connector"
#define AppVersion "1.1.0"
#define AppPublisher "ONEVO"
#define AppExeName "onevo-connector.exe"
#define AppServiceExe "onevo-connector-service.exe"
#define AppId "{{A7C3E91F-4B2D-4E8A-9F01-0E0C0C001100}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ONEVO\Connector
DefaultGroupName=ONEVO
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ONEVO-Connector-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\onevo-connector.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "tools\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "tools\WinSW-x64.exe"; DestDir: "{app}"; DestName: "{#AppServiceExe}"; Flags: ignoreversion
Source: "winsw\onevo-connector-service.xml"; DestDir: "{app}"; DestName: "onevo-connector-service.xml"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\ONEVO\Connector\data"; Permissions: users-modify
Name: "{commonappdata}\ONEVO\Connector\media"; Permissions: users-modify
Name: "{app}\bin"

[Icons]
Name: "{group}\ONEVO Connector Status"; Filename: "http://localhost:8099/"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ONEVO Connector Status"; Filename: "http://localhost:8099/"

[Run]
Filename: "{app}\{#AppServiceExe}"; Parameters: "uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; Check: ExistingService
Filename: "{app}\{#AppServiceExe}"; Parameters: "install"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Installing Windows service..."
Filename: "{app}\{#AppServiceExe}"; Parameters: "start"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Activating connector and starting monitoring..."
Filename: "http://localhost:8099/"; Description: "Open connector status"; Flags: postinstall shellexec skipifsilent nowait

[UninstallRun]
Filename: "{app}\{#AppServiceExe}"; Parameters: "stop"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{app}\{#AppServiceExe}"; Parameters: "uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "UninstallSvc"

[Code]
var
  IdentityPage: TInputQueryWizardPage;
  SourcePage: TInputOptionWizardPage;
  RtspPage: TInputQueryWizardPage;
  OnvifPage: TInputQueryWizardPage;
  FilePage: TInputFileWizardPage;

function JsonEscape(Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

function ExistingService(): Boolean;
begin
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ONEVOConnector');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  ServiceExe: String;
begin
  Result := '';
  ServiceExe := ExpandConstant('{app}\{#AppServiceExe}');
  if FileExists(ServiceExe) then
    Exec(ServiceExe, 'stop', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure InitializeWizard;
begin
  IdentityPage := CreateInputQueryPage(wpSelectDir,
    'Connect to ONEVO', 'Enter the connector identity',
    'Generate a one-time setup code in the ONEVO dashboard and enter it here.');
  IdentityPage.Add('Setup code:', False);
  IdentityPage.Add('Connector name:', False);
  IdentityPage.Values[1] := 'ONEVO Store Connector';

  SourcePage := CreateInputOptionPage(IdentityPage.ID,
    'Camera source', 'Choose the input type',
    'Configure RTSP cameras, ONVIF cameras, or a continuously looping MP4 video.', True, False);
  SourcePage.Add('RTSP camera URL(s)');
  SourcePage.Add('ONVIF camera(s)');
  SourcePage.Add('Local MP4 test video (continuous loop)');
  SourcePage.SelectedValueIndex := 0;

  RtspPage := CreateInputQueryPage(SourcePage.ID,
    'RTSP cameras', 'Enter one or more RTSP URLs',
    'For multiple cameras, separate URLs with semicolons (;).');
  RtspPage.Add('RTSP URL(s):', False);

  OnvifPage := CreateInputQueryPage(RtspPage.ID,
    'ONVIF cameras', 'Enter one or more ONVIF camera hosts',
    'Separate multiple IP addresses or hostnames with semicolons. Each host may optionally include :port.');
  OnvifPage.Add('Host(s):', False);
  OnvifPage.Add('Default ONVIF port:', False);
  OnvifPage.Add('Username:', False);
  OnvifPage.Add('Password:', True);
  OnvifPage.Values[1] := '80';
  OnvifPage.Values[2] := 'admin';

  FilePage := CreateInputFilePage(OnvifPage.ID,
    'Test video', 'Choose an MP4 video',
    'The connector will copy and continuously loop this video.');
  FilePage.Add('MP4 file:', 'MP4 video (*.mp4)|*.mp4', '.mp4');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (PageID = RtspPage.ID) and (SourcePage.SelectedValueIndex <> 0) then Result := True;
  if (PageID = OnvifPage.ID) and (SourcePage.SelectedValueIndex <> 1) then Result := True;
  if (PageID = FilePage.ID) and (SourcePage.SelectedValueIndex <> 2) then Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = IdentityPage.ID then begin
    if (Trim(IdentityPage.Values[0]) = '') or (Trim(IdentityPage.Values[1]) = '') then begin
      MsgBox('Setup code and connector name are required.', mbError, MB_OK);
      Result := False;
    end;
  end;
  if (CurPageID = RtspPage.ID) and
     (Pos('rtsp://', Lowercase(Trim(RtspPage.Values[0]))) <> 1) then begin
    MsgBox('Enter one or more valid rtsp:// URLs separated by semicolons.', mbError, MB_OK);
    Result := False;
  end;
  if CurPageID = OnvifPage.ID then begin
    if Trim(OnvifPage.Values[0]) = '' then begin
      MsgBox('Enter one or more ONVIF camera IP addresses or hostnames.', mbError, MB_OK);
      Result := False;
    end;
    if StrToIntDef(Trim(OnvifPage.Values[1]), 0) = 0 then begin
      MsgBox('Enter a valid ONVIF port.', mbError, MB_OK);
      Result := False;
    end;
  end;
  if (CurPageID = FilePage.ID) and not FileExists(FilePage.Values[0]) then begin
    MsgBox('Select an existing MP4 video.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, MediaPath, Json, RtspText, OnvifText, OnvifUser,
  OnvifPass, SourceFile: String;
  OnvifPort: Integer;
begin
  if CurStep <> ssInstall then Exit;

  ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector'));
  ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector\data'));
  ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector\media'));

  RtspText := '';
  OnvifText := '';
  OnvifUser := '';
  OnvifPass := '';
  OnvifPort := 80;
  SourceFile := '';
  if SourcePage.SelectedValueIndex = 0 then
    RtspText := Trim(RtspPage.Values[0])
  else if SourcePage.SelectedValueIndex = 1 then begin
    OnvifText := Trim(OnvifPage.Values[0]);
    OnvifPort := StrToIntDef(Trim(OnvifPage.Values[1]), 80);
    OnvifUser := Trim(OnvifPage.Values[2]);
    OnvifPass := OnvifPage.Values[3];
  end
  else begin
    MediaPath := ExpandConstant('{commonappdata}\ONEVO\Connector\media\installer-video.mp4');
    if not CopyFile(FilePage.Values[0], MediaPath, False) then
      RaiseException('Could not copy the selected MP4 video.');
    SourceFile := MediaPath;
  end;

  ConfigPath := ExpandConstant('{commonappdata}\ONEVO\Connector\config.json');
  Json := '{' + #13#10 +
    '  "setup_complete": false,' + #13#10 +
    '  "setup_code": "' + JsonEscape(Trim(IdentityPage.Values[0])) + '",' + #13#10 +
    '  "connector_name": "' + JsonEscape(Trim(IdentityPage.Values[1])) + '",' + #13#10 +
    '  "rtsp_text": "' + JsonEscape(RtspText) + '",' + #13#10 +
    '  "onvif_text": "' + JsonEscape(OnvifText) + '",' + #13#10 +
    '  "onvif_port": ' + IntToStr(OnvifPort) + ',' + #13#10 +
    '  "onvif_user": "' + JsonEscape(OnvifUser) + '",' + #13#10 +
    '  "onvif_pass": "' + JsonEscape(OnvifPass) + '",' + #13#10 +
    '  "source_file": "' + JsonEscape(SourceFile) + '",' + #13#10 +
    '  "loop_file": true,' + #13#10 +
    '  "sources": []' + #13#10 +
    '}' + #13#10;
  SaveStringToFile(ConfigPath, Json, False);
end;
