#define AppName "ONEVO Local Connector"
#define AppVersion "1.1.12"
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
DirExistsWarning=no
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
SetupIconFile=assets\onevo.ico
; --- FIX: auto-detect & force-close any process locking these files
;     (the running service child exe, or a manually-launched/orphaned
;     copy) instead of failing with "file in use" and forcing a manual
;     uninstall. ---
CloseApplications=force
CloseApplicationsFilter={#AppExeName},{#AppServiceExe}
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\onevo-connector.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "tools\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "tools\WinSW-x64.exe"; DestDir: "{app}"; DestName: "{#AppServiceExe}"; Flags: ignoreversion
Source: "winsw\onevo-connector-service.xml"; DestDir: "{app}"; DestName: "onevo-connector-service.xml"; Flags: ignoreversion
Source: "assets\onevo.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\ONEVO\Connector\data"; Permissions: users-modify
Name: "{commonappdata}\ONEVO\Connector\media"; Permissions: users-modify
Name: "{app}\bin"

[Icons]
Name: "{group}\ONEVO Connector Status"; Filename: "http://localhost:8099/"; IconFilename: "{app}\assets\onevo.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ONEVO Connector Status"; Filename: "http://localhost:8099/"; IconFilename: "{app}\assets\onevo.ico"

[Run]
; In-place updates preserve the existing service registration. Unregistering and
; immediately registering it again creates a race when a tray update overlaps a
; manually started installer and can leave the connector with no service.
Filename: "{app}\{#AppServiceExe}"; Parameters: "install"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Installing Windows service..."; Check: not ExistingService
Filename: "{sys}\sc.exe"; Parameters: "config ONEVOConnector start= demand"; Flags: runhidden waituntilterminated; Check: PausedMarkerExists
Filename: "{app}\{#AppServiceExe}"; Parameters: "start"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Activating connector and starting monitoring..."; Check: not PausedMarkerExists
Filename: "{app}\{#AppExeName}"; Parameters: "--tray"; WorkingDir: "{app}"; Flags: runasoriginaluser runhidden nowait; StatusMsg: "Starting ONEVO system tray..."

[UninstallRun]
Filename: "{app}\{#AppExeName}"; Parameters: "--tray-uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopTray"
Filename: "{app}\{#AppExeName}"; Parameters: "--notify-uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "NotifyCloud"
Filename: "{app}\{#AppServiceExe}"; Parameters: "stop"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{app}\{#AppServiceExe}"; Parameters: "uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "UninstallSvc"

[UninstallDelete]
; A real uninstall means a clean slate. In-place upgrades never run this
; section, so connector identity and source data remain safe during updates.
Type: filesandordirs; Name: "{commonappdata}\ONEVO\Connector"

[Code]
var
  IdentityPage: TInputQueryWizardPage;
  SourcePage: TInputOptionWizardPage;
  RtspPage: TInputQueryWizardPage;
  OnvifPage: TInputQueryWizardPage;
  FilePage: TInputFileWizardPage;
  AddRtspButton, AddOnvifButton, AddVideoButton: TNewButton;
  RtspRemoveButtons: array[0..7] of TNewButton;
  OnvifRemoveButtons: array[0..4] of TNewButton;
  VideoRemoveButtons: array[0..7] of TNewButton;
  RtspActive: array[0..7] of Boolean;
  OnvifActive: array[0..4] of Boolean;
  VideoActive: array[0..7] of Boolean;
  RtspCount, OnvifCount, VideoCount: Integer;
  SourceSetupSkipped, NavigatingFromSourceChoice: Boolean;
  ExistingInstall: Boolean;
  PreviousConfigFound, PreserveExistingConfig, FreshInstallCleanup, UpdateMode: Boolean;
  InstalledVersion: String;

function JsonEscape(Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

function ReadVersionPart(var Value: String): Integer;
var
  DotPos: Integer;
  Part: String;
begin
  DotPos := Pos('.', Value);
  if DotPos > 0 then begin
    Part := Copy(Value, 1, DotPos - 1);
    Delete(Value, 1, DotPos);
  end else begin
    Part := Value;
    Value := '';
  end;
  Result := StrToIntDef(Part, 0);
end;

function CompareVersions(Left, Right: String): Integer;
var
  I, L, R: Integer;
begin
  Result := 0;
  for I := 1 to 4 do begin
    L := ReadVersionPart(Left);
    R := ReadVersionPart(Right);
    if L < R then begin Result := -1; Exit; end;
    if L > R then begin Result := 1; Exit; end;
  end;
end;

function ReadInstalledVersion(var Version: String): Boolean;
var
  Key: String;
begin
  Key := 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{A7C3E91F-4B2D-4E8A-9F01-0E0C0C001100}_is1';
  Result :=
    RegQueryStringValue(HKLM64, Key, 'DisplayVersion', Version) or
    RegQueryStringValue(HKLM32, Key, 'DisplayVersion', Version) or
    RegQueryStringValue(HKCU, Key, 'DisplayVersion', Version);
end;

function CmdLineParamExists(Value: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then begin
      Result := True;
      Exit;
    end;
end;

function InitializeSetup(): Boolean;
var
  Choice: Integer;
begin
  UpdateMode := CmdLineParamExists('/UPDATE');
  ExistingInstall := ReadInstalledVersion(InstalledVersion) or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ONEVOConnector');
  PreviousConfigFound :=
    FileExists(ExpandConstant('{commonappdata}\ONEVO\Connector\config.json'));
  PreserveExistingConfig := ExistingInstall and PreviousConfigFound;
  FreshInstallCleanup := (not ExistingInstall) and PreviousConfigFound;

  if (InstalledVersion <> '') and
     (CompareVersions(InstalledVersion, '{#AppVersion}') > 0) then begin
    MsgBox(
      'ONEVO Connector ' + InstalledVersion + ' is already installed.' + #13#10 +
      'This installer is version {#AppVersion}. Downgrading is not supported.',
      mbError, MB_OK);
    Result := False;
    Exit;
  end;

  if ExistingInstall and not UpdateMode then begin
    if InstalledVersion = '' then InstalledVersion := 'an earlier version';
    Choice := MsgBox(
      'ONEVO Connector ' + InstalledVersion + ' is already installed.' + #13#10 +
      'Update it to version {#AppVersion}?' + #13#10#13#10 +
      'Your existing connector identity and camera data will be preserved.',
      mbConfirmation, MB_OKCANCEL);
    if Choice <> IDOK then begin
      Result := False;
      Exit;
    end;
  end else if PreviousConfigFound then begin
    MsgBox(
      'A previous ONEVO configuration was found, but the application is not installed.' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Setup will remove the incomplete data and start a new configuration. ' +
      'You will enter the setup code, connector name, and camera sources again.',
      mbInformation, MB_OK);
  end;
  Result := True;
end;

function ExistingService(): Boolean;
begin
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ONEVOConnector');
end;

function PausedMarkerExists(): Boolean;
begin
  Result := FileExists(
    ExpandConstant('{commonappdata}\ONEVO\Connector\data\monitoring.paused'));
end;

// --- FIX: robustly ensure NOTHING is holding onevo-connector.exe /
// onevo-connector-service.exe / the single-instance lock file before
// we start overwriting files. This runs even if the service was never
// registered, was left in a broken state, or the exe was launched by
// hand for testing - so re-running Setup always "just updates"
// instead of requiring a manual uninstall first. ---
function TryConnectorHealth(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(
    'powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri ''http://127.0.0.1:8099/health'' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

function WaitForConnectorHealth(MaxSeconds: Integer): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to MaxSeconds do
  begin
    if TryConnectorHealth() then
    begin
      Result := True;
      Exit;
    end;
    Sleep(1000);
  end;
end;

procedure WaitAndOpenStatus();
var
  ResultCode: Integer;
begin
  if WaitForConnectorHealth(60) then
    ShellExec('open', 'http://localhost:8099/', '', '', SW_SHOW, ewNoWait, ResultCode)
  else
    MsgBox(
      'The ONEVO connector service did not respond on http://localhost:8099/ within 60 seconds.' + #13#10 + #13#10 +
      'Check Windows Services for "ONEVO Local Connector".' + #13#10 +
      'Review logs in the install folder:' + #13#10 +
      ExpandConstant('{app}\onevo-connector-service.out.log') + #13#10 +
      'Saved config:' + #13#10 +
      ExpandConstant('{commonappdata}\ONEVO\Connector\config.json') + #13#10 + #13#10 +
      'If activation failed, open http://localhost:8099/setup after generating a new setup code.',
      mbError, MB_OK);
end;

function ValidateRtspUrls(Value: String): Boolean;
var
  S, Part: String;
  P: Integer;
  Found: Boolean;
begin
  Result := False;
  S := Trim(Value);
  if S = '' then Exit;
  Found := False;
  repeat
    P := Pos(';', S);
    if P > 0 then begin
      Part := Trim(Copy(S, 1, P - 1));
      Delete(S, 1, P);
    end else begin
      Part := Trim(S);
      S := '';
    end;
    if Part = '' then Continue;
    Found := True;
    if Pos('rtsp://', Lowercase(Part)) <> 1 then Exit;
  until S = '';
  Result := Found;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  ServiceExe, LockPath: String;
begin
  Result := '';
  ServiceExe := ExpandConstant('{app}\{#AppServiceExe}');

  // 1) Ask the interactive tray process to release its icon and files.
  if FileExists(ExpandConstant('{app}\{#AppExeName}')) then begin
    Exec(ExpandConstant('{app}\{#AppExeName}'), '--tray-exit',
      ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
  end;

  // 2) Politely ask WinSW to stop the service (this stops the
  //    "onevo-connector.exe --service" child process it manages).
  if FileExists(ServiceExe) then
    Exec(ServiceExe, 'stop', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 3) Safety net: force-kill any copy of either exe that is running
  //    but NOT tracked by the service anymore (manual launch, crash,
  //    orphaned process). taskkill exiting with "not found" is fine -
  //    we ignore ResultCode on purpose.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExeName} /T',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppServiceExe} /T',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 4) Give Windows a moment to fully release file handles before the
  //    installer tries to overwrite the exe.
  Sleep(1500);

  // 5) Clear stale service/tray lock files after both processes exited.
  //    started below acquires it cleanly, instead of silently failing
  //    to start because the old process's lock hadn't been cleaned up.
  LockPath := ExpandConstant('{commonappdata}\ONEVO\Connector\data\connector.lock');
  if FileExists(LockPath) then
    DeleteFile(LockPath);
  LockPath := ExpandConstant('{commonappdata}\ONEVO\Connector\data\tray.lock');
  if FileExists(LockPath) then
    DeleteFile(LockPath);
end;

function CurrentSourceHasValue: Boolean;
var
  I, Base: Integer;
begin
  Result := False;
  if WizardForm.CurPageID = RtspPage.ID then begin
    for I := 0 to RtspCount - 1 do
      if RtspActive[I] and (Trim(RtspPage.Values[I]) <> '') then begin
        Result := True;
        Exit;
      end;
  end else if WizardForm.CurPageID = OnvifPage.ID then begin
    for I := 0 to OnvifCount - 1 do begin
      Base := I * 4;
      if OnvifActive[I] and (Trim(OnvifPage.Values[Base]) <> '') then begin
        Result := True;
        Exit;
      end;
    end;
  end else if WizardForm.CurPageID = FilePage.ID then begin
    for I := 0 to VideoCount - 1 do
      if VideoActive[I] and (Trim(FilePage.Values[I]) <> '') then begin
        Result := True;
        Exit;
      end;
  end;
end;

procedure UpdateSourceNextCaption;
begin
  if (WizardForm.CurPageID = RtspPage.ID) or
     (WizardForm.CurPageID = OnvifPage.ID) or
     (WizardForm.CurPageID = FilePage.ID) then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

procedure SourceValueChanged(Sender: TObject);
begin
  UpdateSourceNextCaption;
end;

procedure RemoveRtspField(Sender: TObject);
var
  I: Integer;
begin
  for I := 0 to RtspCount - 1 do
    if Sender = RtspRemoveButtons[I] then begin
      RtspActive[I] := False;
      RtspPage.Values[I] := '';
      RtspPage.Edits[I].Visible := False;
      RtspPage.PromptLabels[I].Visible := False;
      RtspRemoveButtons[I].Visible := False;
      UpdateSourceNextCaption;
      Exit;
    end;
end;

procedure ConfigureRtspRow(Index: Integer);
begin
  RtspPage.Edits[Index].Width := ScaleX(330);
  RtspRemoveButtons[Index] := TNewButton.Create(WizardForm);
  RtspRemoveButtons[Index].Parent := RtspPage.Surface;
  RtspRemoveButtons[Index].Caption := 'Remove';
  RtspRemoveButtons[Index].Left := ScaleX(340);
  RtspRemoveButtons[Index].Top := RtspPage.Edits[Index].Top - ScaleY(1);
  RtspRemoveButtons[Index].Width := ScaleX(75);
  RtspRemoveButtons[Index].Height := ScaleY(24);
  RtspRemoveButtons[Index].OnClick := @RemoveRtspField;
  RtspRemoveButtons[Index].Visible := Index > 0;
  RtspPage.Edits[Index].OnChange := @SourceValueChanged;
  RtspActive[Index] := True;
end;

procedure AddRtspField(Sender: TObject);
var
  I: Integer;
begin
  for I := 0 to RtspCount - 1 do
    if not RtspActive[I] then begin
      RtspActive[I] := True;
      RtspPage.Edits[I].Visible := True;
      RtspPage.PromptLabels[I].Visible := True;
      RtspRemoveButtons[I].Visible := True;
      UpdateSourceNextCaption;
      Exit;
    end;
  if RtspCount >= 8 then begin
    MsgBox('Add further cameras later at http://localhost:8099/.', mbInformation, MB_OK);
    Exit;
  end;
  RtspCount := RtspCount + 1;
  RtspPage.Add('RTSP URL ' + IntToStr(RtspCount) + ':', False);
  ConfigureRtspRow(RtspCount - 1);
  AddRtspButton.Top := RtspPage.Edits[RtspCount - 1].Top + ScaleY(32);
  UpdateSourceNextCaption;
end;

procedure RemoveOnvifFields(Sender: TObject);
var
  I, Base, J: Integer;
begin
  for I := 0 to OnvifCount - 1 do
    if Sender = OnvifRemoveButtons[I] then begin
      OnvifActive[I] := False;
      Base := I * 4;
      for J := 0 to 3 do begin
        OnvifPage.Values[Base + J] := '';
        OnvifPage.Edits[Base + J].Visible := False;
        OnvifPage.PromptLabels[Base + J].Visible := False;
      end;
      OnvifRemoveButtons[I].Visible := False;
      UpdateSourceNextCaption;
      Exit;
    end;
end;

procedure ConfigureOnvifRow(Index: Integer);
var
  Base: Integer;
begin
  Base := Index * 4;
  OnvifRemoveButtons[Index] := TNewButton.Create(WizardForm);
  OnvifRemoveButtons[Index].Parent := OnvifPage.Surface;
  OnvifRemoveButtons[Index].Caption := 'Remove camera';
  OnvifRemoveButtons[Index].Left := ScaleX(300);
  OnvifRemoveButtons[Index].Top := OnvifPage.Edits[Base + 3].Top + ScaleY(28);
  OnvifRemoveButtons[Index].Width := ScaleX(115);
  OnvifRemoveButtons[Index].Height := ScaleY(24);
  OnvifRemoveButtons[Index].OnClick := @RemoveOnvifFields;
  OnvifRemoveButtons[Index].Visible := Index > 0;
  OnvifPage.Edits[Base].OnChange := @SourceValueChanged;
  OnvifActive[Index] := True;
end;

procedure AddOnvifFields(Sender: TObject);
var
  I, Base, J: Integer;
begin
  for I := 0 to OnvifCount - 1 do
    if not OnvifActive[I] then begin
      OnvifActive[I] := True;
      Base := I * 4;
      for J := 0 to 3 do begin
        OnvifPage.Edits[Base + J].Visible := True;
        OnvifPage.PromptLabels[Base + J].Visible := True;
      end;
      OnvifPage.Values[Base + 1] := '80';
      OnvifPage.Values[Base + 2] := 'admin';
      OnvifRemoveButtons[I].Visible := True;
      UpdateSourceNextCaption;
      Exit;
    end;
  if OnvifCount >= 5 then begin
    MsgBox('Add further cameras later at http://localhost:8099/.', mbInformation, MB_OK);
    Exit;
  end;
  OnvifCount := OnvifCount + 1;
  OnvifPage.Add('Camera ' + IntToStr(OnvifCount) + ' host / IP:', False);
  OnvifPage.Add('Camera ' + IntToStr(OnvifCount) + ' port:', False);
  OnvifPage.Add('Camera ' + IntToStr(OnvifCount) + ' username:', False);
  OnvifPage.Add('Camera ' + IntToStr(OnvifCount) + ' password:', True);
  Base := (OnvifCount - 1) * 4;
  OnvifPage.Values[Base + 1] := '80';
  OnvifPage.Values[Base + 2] := 'admin';
  ConfigureOnvifRow(OnvifCount - 1);
  AddOnvifButton.Top := OnvifRemoveButtons[OnvifCount - 1].Top + ScaleY(30);
  UpdateSourceNextCaption;
end;

procedure RemoveVideoField(Sender: TObject);
var
  I: Integer;
begin
  for I := 0 to VideoCount - 1 do
    if Sender = VideoRemoveButtons[I] then begin
      VideoActive[I] := False;
      FilePage.Values[I] := '';
      FilePage.Edits[I].Visible := False;
      FilePage.Buttons[I].Visible := False;
      FilePage.PromptLabels[I].Visible := False;
      VideoRemoveButtons[I].Visible := False;
      UpdateSourceNextCaption;
      Exit;
    end;
end;

procedure ConfigureVideoRow(Index: Integer);
begin
  FilePage.Edits[Index].Width := ScaleX(280);
  FilePage.Buttons[Index].Left := ScaleX(290);
  VideoRemoveButtons[Index] := TNewButton.Create(WizardForm);
  VideoRemoveButtons[Index].Parent := FilePage.Surface;
  VideoRemoveButtons[Index].Caption := 'Remove';
  VideoRemoveButtons[Index].Left := ScaleX(385);
  VideoRemoveButtons[Index].Top := FilePage.Edits[Index].Top - ScaleY(1);
  VideoRemoveButtons[Index].Width := ScaleX(75);
  VideoRemoveButtons[Index].Height := ScaleY(24);
  VideoRemoveButtons[Index].OnClick := @RemoveVideoField;
  VideoRemoveButtons[Index].Visible := Index > 0;
  FilePage.Edits[Index].OnChange := @SourceValueChanged;
  VideoActive[Index] := True;
end;

procedure AddVideoField(Sender: TObject);
var
  I: Integer;
begin
  for I := 0 to VideoCount - 1 do
    if not VideoActive[I] then begin
      VideoActive[I] := True;
      FilePage.Edits[I].Visible := True;
      FilePage.Buttons[I].Visible := True;
      FilePage.PromptLabels[I].Visible := True;
      VideoRemoveButtons[I].Visible := True;
      UpdateSourceNextCaption;
      Exit;
    end;
  if VideoCount >= 8 then begin
    MsgBox('Add further videos later at http://localhost:8099/.', mbInformation, MB_OK);
    Exit;
  end;
  VideoCount := VideoCount + 1;
  FilePage.Add('MP4 video ' + IntToStr(VideoCount) + ':', 'MP4 video (*.mp4)|*.mp4', '.mp4');
  ConfigureVideoRow(VideoCount - 1);
  AddVideoButton.Top := FilePage.Edits[VideoCount - 1].Top + ScaleY(32);
  UpdateSourceNextCaption;
end;

procedure SourceTypeClicked(Sender: TObject);
begin
  if (WizardForm.CurPageID <> SourcePage.ID) or
     (SourcePage.SelectedValueIndex < 0) then Exit;
  SourceSetupSkipped := False;
  NavigatingFromSourceChoice := True;
  WizardForm.NextButton.OnClick(WizardForm.NextButton);
  NavigatingFromSourceChoice := False;
end;

procedure InitializeWizard;
begin
  SourceSetupSkipped := False;
  NavigatingFromSourceChoice := False;
  WizardForm.CancelButton.Visible := False;

  IdentityPage := CreateInputQueryPage(wpSelectDir,
    'Connect to ONEVO', 'Enter the connector identity',
    'Generate a one-time setup code in the ONEVO dashboard and enter it here.');
  IdentityPage.Add('Setup code:', False);
  IdentityPage.Add('Connector name:', False);
  IdentityPage.Values[1] := 'ONEVO Store Connector';

  SourcePage := CreateInputOptionPage(IdentityPage.ID,
    'Camera source', 'Choose the input type',
    'Choose one source type. You can add one or several sources of that type.', True, False);
  SourcePage.Add('RTSP camera URL(s)');
  SourcePage.Add('ONVIF camera(s)');
  SourcePage.Add('Local MP4 test video(s) (continuous loop)');
  SourcePage.SelectedValueIndex := -1;
  SourcePage.CheckListBox.OnClickCheck := @SourceTypeClicked;

  RtspPage := CreateInputQueryPage(SourcePage.ID,
    'RTSP cameras', 'Enter one or more RTSP URLs',
    'Enter one URL per field. Use Add RTSP Link for more cameras.');
  RtspCount := 1;
  RtspPage.Add('RTSP URL 1:', False);
  ConfigureRtspRow(0);
  AddRtspButton := TNewButton.Create(WizardForm);
  AddRtspButton.Parent := RtspPage.Surface;
  AddRtspButton.Caption := '+ Add RTSP Link';
  AddRtspButton.Left := 0;
  AddRtspButton.Top := RtspPage.Edits[0].Top + ScaleY(32);
  AddRtspButton.Width := ScaleX(150);
  AddRtspButton.Height := ScaleY(26);
  AddRtspButton.OnClick := @AddRtspField;

  OnvifPage := CreateInputQueryPage(RtspPage.ID,
    'ONVIF cameras', 'Enter one or more ONVIF camera hosts',
    'Enter each camera separately. Use Add ONVIF Camera for more cameras.');
  OnvifCount := 1;
  OnvifPage.Add('Camera 1 host / IP:', False);
  OnvifPage.Add('Camera 1 port:', False);
  OnvifPage.Add('Camera 1 username:', False);
  OnvifPage.Add('Camera 1 password:', True);
  OnvifPage.Values[1] := '80';
  OnvifPage.Values[2] := 'admin';
  ConfigureOnvifRow(0);
  AddOnvifButton := TNewButton.Create(WizardForm);
  AddOnvifButton.Parent := OnvifPage.Surface;
  AddOnvifButton.Caption := '+ Add ONVIF Camera';
  AddOnvifButton.Left := 0;
  AddOnvifButton.Top := OnvifRemoveButtons[0].Top + ScaleY(30);
  AddOnvifButton.Width := ScaleX(150);
  AddOnvifButton.Height := ScaleY(26);
  AddOnvifButton.OnClick := @AddOnvifFields;

  FilePage := CreateInputFilePage(OnvifPage.ID,
    'Local videos', 'Choose one or more MP4 videos',
    'Each selected video is copied separately and continuously looped.');
  VideoCount := 1;
  FilePage.Add('MP4 video 1:', 'MP4 video (*.mp4)|*.mp4', '.mp4');
  ConfigureVideoRow(0);
  AddVideoButton := TNewButton.Create(WizardForm);
  AddVideoButton.Parent := FilePage.Surface;
  AddVideoButton.Caption := '+ Add Local Video';
  AddVideoButton.Left := 0;
  AddVideoButton.Top := FilePage.Edits[0].Top + ScaleY(32);
  AddVideoButton.Width := ScaleX(150);
  AddVideoButton.Height := ScaleY(26);
  AddVideoButton.OnClick := @AddVideoField;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if UpdateMode and
     ((PageID = IdentityPage.ID) or (PageID = SourcePage.ID) or
      (PageID = RtspPage.ID) or (PageID = OnvifPage.ID) or
      (PageID = FilePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if PreserveExistingConfig and
     ((PageID = IdentityPage.ID) or (PageID = SourcePage.ID) or
      (PageID = RtspPage.ID) or (PageID = OnvifPage.ID) or
      (PageID = FilePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if SourceSetupSkipped and
     ((PageID = RtspPage.ID) or (PageID = OnvifPage.ID) or (PageID = FilePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if (PageID = RtspPage.ID) and (SourcePage.SelectedValueIndex <> 0) then Result := True;
  if (PageID = OnvifPage.ID) and (SourcePage.SelectedValueIndex <> 1) then Result := True;
  if (PageID = FilePage.ID) and (SourcePage.SelectedValueIndex <> 2) then Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  I, Base, Port, ValidCount: Integer;
begin
  Result := True;
  if CurPageID = IdentityPage.ID then begin
    if (Trim(IdentityPage.Values[0]) = '') or (Trim(IdentityPage.Values[1]) = '') then begin
      MsgBox('Setup code and connector name are required.', mbError, MB_OK);
      Result := False;
    end;
  end;
  if CurPageID = SourcePage.ID then begin
    if not NavigatingFromSourceChoice then begin
      SourceSetupSkipped := True;
      SourcePage.SelectedValueIndex := -1;
    end;
  end;
  if CurPageID = RtspPage.ID then begin
    ValidCount := 0;
    for I := 0 to RtspCount - 1 do begin
      if RtspActive[I] and (Trim(RtspPage.Values[I]) <> '') then begin
        ValidCount := ValidCount + 1;
        if Pos('rtsp://', Lowercase(Trim(RtspPage.Values[I]))) <> 1 then begin
        MsgBox('RTSP URL ' + IntToStr(I + 1) + ' must start with rtsp://.', mbError, MB_OK);
        Result := False;
        Exit;
        end;
      end;
    end;
    if ValidCount = 0 then begin
      MsgBox('Enter at least one RTSP URL, or go Back and choose Skip camera setup.',
        mbError, MB_OK);
      Result := False;
      SourceSetupSkipped := True;
      Result := True;
      Exit;
    end;
  end;
  if (CurPageID = RtspPage.ID) and (not SourceSetupSkipped) and
     (not ValidateRtspUrls(RtspPage.Values[0])) then begin
    MsgBox('Enter one or more valid rtsp:// URLs separated by semicolons.', mbError, MB_OK);
    Result := False;
  end;
  if CurPageID = OnvifPage.ID then begin
    ValidCount := 0;
    for I := 0 to OnvifCount - 1 do begin
      Base := I * 4;
      if OnvifActive[I] and (Trim(OnvifPage.Values[Base]) <> '') then begin
        ValidCount := ValidCount + 1;
        Port := StrToIntDef(Trim(OnvifPage.Values[Base + 1]), 0);
        if (Port < 1) or (Port > 65535) then begin
          MsgBox('Enter a valid port for ONVIF camera ' + IntToStr(I + 1) + '.', mbError, MB_OK);
          Result := False;
          Exit;
        end;
      end;
    end;
    if ValidCount = 0 then begin
      MsgBox('Enter at least one ONVIF camera, or go Back and choose Skip camera setup.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
  if CurPageID = FilePage.ID then begin
    ValidCount := 0;
    for I := 0 to VideoCount - 1 do begin
      if VideoActive[I] and (Trim(FilePage.Values[I]) <> '') then begin
        ValidCount := ValidCount + 1;
        if not FileExists(FilePage.Values[I]) then begin
        MsgBox('Select an existing MP4 video for entry ' + IntToStr(I + 1) + '.', mbError, MB_OK);
        Result := False;
        Exit;
        end;
      end;
    end;
    if ValidCount = 0 then begin
      MsgBox('Select at least one MP4 video, or go Back and choose Skip camera setup.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = SourcePage.ID then begin
    if PreserveExistingConfig then
      WizardForm.NextButton.Caption := 'Keep existing'
    else
      WizardForm.NextButton.Caption := 'Skip';
    SourcePage.SelectedValueIndex := -1;
  end else if (CurPageID = RtspPage.ID) or
              (CurPageID = OnvifPage.ID) or
              (CurPageID = FilePage.ID) then
    UpdateSourceNextCaption
  else if CurPageID = wpFinished then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonFinish)
  else if CurPageID = wpReady then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall)
  else
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, UpdatePath, MediaPath, Json, SourcesJson, ItemJson: String;
  I, Base: Integer;
begin
  if CurStep <> ssInstall then Exit;
  if UpdateMode then Exit;
    ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector'));
    ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector\data'));
    ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector\media'));

  if FreshInstallCleanup then
    DelTree(ExpandConstant('{commonappdata}\ONEVO\Connector'), True, True, True);

  ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector'));
  ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector\data'));
  ForceDirectories(ExpandConstant('{commonappdata}\ONEVO\Connector\media'));

  ConfigPath := ExpandConstant('{commonappdata}\ONEVO\Connector\config.json');
  UpdatePath := ExpandConstant('{commonappdata}\ONEVO\Connector\source-update.json');

  SourcesJson := '';
  if not SourceSetupSkipped then begin
    if SourcePage.SelectedValueIndex = 0 then begin
      for I := 0 to RtspCount - 1 do begin
        if RtspActive[I] and (Trim(RtspPage.Values[I]) <> '') then begin
          ItemJson := '{"name":"Camera ' + IntToStr(I + 1) +
            '","rtsp_url":"' + JsonEscape(Trim(RtspPage.Values[I])) + '"}';
          if SourcesJson <> '' then SourcesJson := SourcesJson + ',';
          SourcesJson := SourcesJson + ItemJson;
        end;
      end;
    end else if SourcePage.SelectedValueIndex = 1 then begin
      for I := 0 to OnvifCount - 1 do begin
        Base := I * 4;
        if OnvifActive[I] and (Trim(OnvifPage.Values[Base]) <> '') then begin
          ItemJson := '{"name":"ONVIF Camera ' + IntToStr(I + 1) +
            '","onvif_host":"' + JsonEscape(Trim(OnvifPage.Values[Base])) +
            '","onvif_port":' + IntToStr(StrToIntDef(Trim(OnvifPage.Values[Base + 1]), 80)) +
            ',"onvif_user":"' + JsonEscape(Trim(OnvifPage.Values[Base + 2])) +
            '","onvif_pass":"' + JsonEscape(OnvifPage.Values[Base + 3]) + '"}';
          if SourcesJson <> '' then SourcesJson := SourcesJson + ',';
          SourcesJson := SourcesJson + ItemJson;
        end;
      end;
    end else if SourcePage.SelectedValueIndex = 2 then begin
      for I := 0 to VideoCount - 1 do begin
        if VideoActive[I] and (Trim(FilePage.Values[I]) <> '') then begin
          MediaPath := ExpandConstant('{commonappdata}\ONEVO\Connector\media\installer-video-' +
            IntToStr(I + 1) + '.mp4');
          if not CopyFile(FilePage.Values[I], MediaPath, False) then
            RaiseException('Could not copy MP4 video ' + IntToStr(I + 1) + '.');
          ItemJson := '{"name":"Local Video ' + IntToStr(I + 1) +
            '","source_file":"' + JsonEscape(MediaPath) + '","loop":true}';
          if SourcesJson <> '' then SourcesJson := SourcesJson + ',';
          SourcesJson := SourcesJson + ItemJson;
        end;
      end;
    end;
  end;

  if PreserveExistingConfig then begin
    // "Keep existing" means no camera mutation. If the user selected a source
    // type, write a narrow source overlay; the service applies it while
    // preserving connector/store identity and credentials.
    if SourceSetupSkipped or (SourcesJson = '') then Exit;
    Json := '{"sources":[' + SourcesJson + ']}' + #13#10;
    SaveStringToFile(UpdatePath, Json, False);
    Exit;
  end;

  Json := '{' + #13#10 +
    '  "setup_complete": false,' + #13#10 +
    '  "setup_code": "' + JsonEscape(Trim(IdentityPage.Values[0])) + '",' + #13#10 +
    '  "connector_name": "' + JsonEscape(Trim(IdentityPage.Values[1])) + '",' + #13#10 +
    '  "sources": [' + SourcesJson + ']' + #13#10 +
    '}' + #13#10;
  SaveStringToFile(ConfigPath, Json, False);
end;
