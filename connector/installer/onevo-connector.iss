#define AppName "ONEVO Local Connector"
#define AppVersion "1.1.18"
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
; Keep the standard Ready to Install page after the native camera-zone page.
DisableReadyPage=no
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
; The same signed application code is also available before file installation
; solely as the native wizard's RTSP/ONVIF/MP4 frame-capture helper.
Source: "..\dist\onevo-connector.exe"; Flags: dontcopy; DestName: "onevo-installer-helper.exe"
Source: "tools\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "tools\WinSW-x64.exe"; DestDir: "{app}"; DestName: "{#AppServiceExe}"; Flags: ignoreversion
Source: "winsw\onevo-connector-service.xml"; DestDir: "{app}"; DestName: "onevo-connector-service.xml"; Flags: ignoreversion
Source: "assets\onevo.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\ONEVO\Connector\data"; Permissions: users-modify
Name: "{commonappdata}\ONEVO\Connector\media"; Permissions: users-modify
Name: "{app}\bin"

[Icons]
Name: "{group}\ONEVO Connector Status"; Filename: "{app}\{#AppExeName}"; Parameters: "--open-admin"; WorkingDir: "{app}"; IconFilename: "{app}\assets\onevo.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ONEVO Connector Status"; Filename: "{app}\{#AppExeName}"; Parameters: "--open-admin"; WorkingDir: "{app}"; IconFilename: "{app}\assets\onevo.ico"

[Run]
; In-place updates preserve the existing service registration. Unregistering and
; immediately registering it again creates a race when a tray update overlaps a
; manually started installer and can leave the connector with no service.
Filename: "{app}\{#AppServiceExe}"; Parameters: "install"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Installing Windows service..."; Check: not ExistingService
Filename: "{sys}\sc.exe"; Parameters: "config ONEVOConnector start= demand"; Flags: runhidden waituntilterminated; Check: PausedMarkerExists
Filename: "{app}\{#AppServiceExe}"; Parameters: "start"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Activating connector and starting monitoring..."; Check: not PausedMarkerExists
Filename: "{app}\{#AppExeName}"; Parameters: "--tray"; WorkingDir: "{app}"; Flags: runasoriginaluser runhidden nowait; StatusMsg: "Starting ONEVO system tray..."
Filename: "http://localhost:8099/"; Flags: shellexec runasoriginaluser nowait; StatusMsg: "Opening ONEVO local dashboard..."; Check: OpenDashboardAfterFirstInstall

[UninstallRun]
Filename: "{app}\{#AppExeName}"; Parameters: "--tray-uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopTray"
Filename: "{app}\{#AppServiceExe}"; Parameters: "stop"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
; Stop heartbeat writes before marking the connector uninstalled. Otherwise a
; final heartbeat can race the notification and make the dashboard show
; Installed again after removal.
Filename: "{app}\{#AppExeName}"; Parameters: "--notify-uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "NotifyCloud"
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
  ZonePage: TWizardPage;
  ZoneCameraCombo, ZoneTypeCombo: TNewComboBox;
  ZoneNameEdit: TNewEdit;
  ZoneImage: TBitmapImage;
  ZoneBaseBitmap, ZoneRenderBitmap: TBitmap;
  ZoneLoadedFramePath: String;
  ZoneMouseTimerId: LongWord;
  ZoneList: TNewListBox;
  ZoneCameraLabel, ZoneNameLabel, ZoneTypeLabel, SavedZonesLabel: TNewStaticText;
  RefreshFrameButton, NewZoneButton, UndoPointButton,
    ClearPointsButton, SaveZoneButton, EditZoneButton,
    DeleteZoneButton: TNewButton;
  ZoneStatusLabel, PointCountLabel: TNewStaticText;
  AddRtspButton, AddOnvifButton, AddVideoButton: TNewButton;
  RtspRemoveButtons: array[0..7] of TNewButton;
  OnvifRemoveButtons: array[0..4] of TNewButton;
  VideoRemoveButtons: array[0..7] of TNewButton;
  RtspActive: array[0..7] of Boolean;
  OnvifActive: array[0..4] of Boolean;
  VideoActive: array[0..7] of Boolean;
  RtspCount, OnvifCount, VideoCount: Integer;
  SourceSetupSkipped, NavigatingFromSourceChoice: Boolean;
  ZoneFrameReady: Boolean;
  ZoneDragging: Boolean;
  ZoneDragStartX, ZoneDragStartY, ZoneDragCurrentX, ZoneDragCurrentY: Integer;
  ZonePointX, ZonePointY: array[0..31] of Integer;
  ZonePointCount: Integer;
  SavedZoneSource: array[0..31] of Integer;
  SavedZonePointCount: array[0..31] of Integer;
  SavedZonePointX, SavedZonePointY: array[0..1023] of Integer;
  SavedZoneName, SavedZoneType, SavedZonePolygon: array[0..31] of String;
  SavedZoneCount, EditingZoneIndex: Integer;
  ExistingInstall: Boolean;
  PreviousConfigFound, PairedStateFound, OrphanedRepair,
    PreserveExistingConfig, FreshInstallCleanup, UpdateMode: Boolean;
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
  PairedStateFound :=
    FileExists(ExpandConstant('{commonappdata}\ONEVO\Connector\data\connector.sqlite'));
  // /UPDATE is authoritative even when a broken/missing service registration
  // makes registry-based install detection fail. Never erase ProgramData during
  // an in-place tray update. A missing WinSW service can also happen after a
  // manual stop/partial uninstall; keep its paired credentials and repair the
  // service instead of treating the shop as a brand-new connector.
  OrphanedRepair := PreviousConfigFound and (not ExistingInstall) and PairedStateFound;
  PreserveExistingConfig := PreviousConfigFound and
    (ExistingInstall or UpdateMode or OrphanedRepair);
  FreshInstallCleanup := (not UpdateMode) and (not ExistingInstall) and
    PreviousConfigFound and (not OrphanedRepair);

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
  end else if OrphanedRepair then begin
    MsgBox(
      'A previous ONEVO connector pairing was found, but its Windows service is missing.' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Setup will repair the local service and keep the existing store, cameras, and zones.',
      mbInformation, MB_OK);
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

function OpenDashboardAfterFirstInstall(): Boolean;
begin
  Result := (not UpdateMode) and (not PreserveExistingConfig) and
    (not SourceSetupSkipped);
end;

// --- FIX: robustly ensure NOTHING is holding onevo-connector.exe /
// onevo-connector-service.exe / the single-instance lock file before
// we start overwriting files. This runs even if the service was never
// registered, was left in a broken state, or the exe was launched by
// hand for testing - so re-running Setup always "just updates"
// instead of requiring a manual uninstall first. ---
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

type
  TNativePoint = record
    X: Integer;
    Y: Integer;
  end;

function GetCursorPos(var Point: TNativePoint): Boolean;
  external 'GetCursorPos@user32.dll stdcall';
function ScreenToClient(Wnd: HWND; var Point: TNativePoint): Boolean;
  external 'ScreenToClient@user32.dll stdcall';
function GetAsyncKeyState(VKey: Integer): Integer;
  external 'GetAsyncKeyState@user32.dll stdcall';
function SetTimer(hWnd, NIdEvent, UElapse, TimerFunc: LongWord): LongWord;
  external 'SetTimer@user32.dll stdcall';

function ZoneTypeApiValue: String;
begin
  case ZoneTypeCombo.ItemIndex of
    0: Result := 'HighValue';
    1: Result := 'Shelf';
    2: Result := 'Checkout';
    3: Result := 'Exit';
    4: Result := 'BlindSpot';
  else
    Result := 'Staff';
  end;
end;

procedure SelectZoneType(Value: String);
begin
  if CompareText(Value, 'HighValue') = 0 then ZoneTypeCombo.ItemIndex := 0
  else if CompareText(Value, 'Shelf') = 0 then ZoneTypeCombo.ItemIndex := 1
  else if CompareText(Value, 'Checkout') = 0 then ZoneTypeCombo.ItemIndex := 2
  else if CompareText(Value, 'Exit') = 0 then ZoneTypeCombo.ItemIndex := 3
  else if CompareText(Value, 'BlindSpot') = 0 then ZoneTypeCombo.ItemIndex := 4
  else ZoneTypeCombo.ItemIndex := 5;
end;

function ActiveSourceCount: Integer;
var
  I: Integer;
begin
  Result := 0;
  if SourcePage.SelectedValueIndex = 0 then
    for I := 0 to RtspCount - 1 do
      if RtspActive[I] and (Trim(RtspPage.Values[I]) <> '') then Result := Result + 1
  else if SourcePage.SelectedValueIndex = 1 then
    for I := 0 to OnvifCount - 1 do
      if OnvifActive[I] and (Trim(OnvifPage.Values[I * 4]) <> '') then Result := Result + 1
  else if SourcePage.SelectedValueIndex = 2 then
    for I := 0 to VideoCount - 1 do
      if VideoActive[I] and (Trim(FilePage.Values[I]) <> '') then Result := Result + 1;
end;

procedure PopulateZoneCameras;
var
  I, N: Integer;
begin
  ZoneCameraCombo.Items.Clear;
  N := 0;
  if SourcePage.SelectedValueIndex = 0 then begin
    for I := 0 to RtspCount - 1 do
      if RtspActive[I] and (Trim(RtspPage.Values[I]) <> '') then begin
        N := N + 1;
        ZoneCameraCombo.Items.Add('Camera ' + IntToStr(N));
      end;
  end else if SourcePage.SelectedValueIndex = 1 then begin
    for I := 0 to OnvifCount - 1 do
      if OnvifActive[I] and (Trim(OnvifPage.Values[I * 4]) <> '') then begin
        N := N + 1;
        ZoneCameraCombo.Items.Add('ONVIF Camera ' + IntToStr(N));
      end;
  end else if SourcePage.SelectedValueIndex = 2 then begin
    for I := 0 to VideoCount - 1 do
      if VideoActive[I] and (Trim(FilePage.Values[I]) <> '') then begin
        N := N + 1;
        ZoneCameraCombo.Items.Add('Local Video ' + IntToStr(N));
      end;
  end;
  if ZoneCameraCombo.Items.Count > 0 then ZoneCameraCombo.ItemIndex := 0;
end;

function SourceOriginalIndex(CompactIndex: Integer): Integer;
var
  I, Seen: Integer;
begin
  Result := -1;
  Seen := -1;
  if SourcePage.SelectedValueIndex = 0 then begin
    for I := 0 to RtspCount - 1 do
      if RtspActive[I] and (Trim(RtspPage.Values[I]) <> '') then begin
        Seen := Seen + 1;
        if Seen = CompactIndex then begin Result := I; Exit; end;
      end;
  end else if SourcePage.SelectedValueIndex = 1 then begin
    for I := 0 to OnvifCount - 1 do
      if OnvifActive[I] and (Trim(OnvifPage.Values[I * 4]) <> '') then begin
        Seen := Seen + 1;
        if Seen = CompactIndex then begin Result := I; Exit; end;
      end;
  end else if SourcePage.SelectedValueIndex = 2 then begin
    for I := 0 to VideoCount - 1 do
      if VideoActive[I] and (Trim(FilePage.Values[I]) <> '') then begin
        Seen := Seen + 1;
        if Seen = CompactIndex then begin Result := I; Exit; end;
      end;
  end;
end;

function ZoneBaseFramePath: String;
begin
  Result := ExpandConstant('{tmp}\onevo-zone-frame-' +
    IntToStr(ZoneCameraCombo.ItemIndex) + '.bmp');
end;

procedure RenderZoneDrawing;
var
  I, X, Y: Integer;
begin
  if not ZoneFrameReady then Exit;
  if CompareText(ZoneLoadedFramePath, ZoneBaseFramePath) <> 0 then begin
    ZoneBaseBitmap.LoadFromFile(ZoneBaseFramePath);
    ZoneLoadedFramePath := ZoneBaseFramePath;
  end;
  // Draw into an off-screen bitmap and replace the visible image once. Loading
  // the BMP into ZoneImage on every mouse event caused a visible frame shake.
  ZoneRenderBitmap.Assign(ZoneBaseBitmap);
  ZoneRenderBitmap.Canvas.Pen.Color := $00D2FF;
  ZoneRenderBitmap.Canvas.Pen.Width := 3;
  ZoneRenderBitmap.Canvas.Brush.Color := $00D2FF;
  for I := 0 to ZonePointCount - 1 do begin
    X := ZonePointX[I];
    Y := ZonePointY[I];
    if I = 0 then ZoneRenderBitmap.Canvas.MoveTo(X, Y)
    else ZoneRenderBitmap.Canvas.LineTo(X, Y);
    ZoneRenderBitmap.Canvas.Ellipse(X - 5, Y - 5, X + 5, Y + 5);
  end;
  if ZonePointCount >= 3 then
    ZoneRenderBitmap.Canvas.LineTo(ZonePointX[0], ZonePointY[0]);
  ZoneImage.Bitmap.Assign(ZoneRenderBitmap);
  PointCountLabel.Caption := IntToStr(ZonePointCount) +
    ' point(s) - click and drag to draw a monitoring box';
end;

function WriteCaptureRequest(Path: String): Boolean;
var
  SourceIndex, Base: Integer;
  Json: String;
begin
  Result := False;
  SourceIndex := SourceOriginalIndex(ZoneCameraCombo.ItemIndex);
  if SourceIndex < 0 then Exit;
  if SourcePage.SelectedValueIndex = 0 then
    Json := '{"rtsp_url":"' + JsonEscape(Trim(RtspPage.Values[SourceIndex])) + '"}'
  else if SourcePage.SelectedValueIndex = 1 then begin
    Base := SourceIndex * 4;
    Json := '{"onvif_host":"' + JsonEscape(Trim(OnvifPage.Values[Base])) +
      '","onvif_port":' + IntToStr(StrToIntDef(Trim(OnvifPage.Values[Base + 1]), 80)) +
      ',"onvif_user":"' + JsonEscape(Trim(OnvifPage.Values[Base + 2])) +
      '","onvif_pass":"' + JsonEscape(OnvifPage.Values[Base + 3]) + '"}';
  end else
    Json := '{"source_file":"' + JsonEscape(FilePage.Values[SourceIndex]) + '"}';
  Result := SaveStringToFile(Path, Json, False);
end;

procedure RefreshZoneFrame(Sender: TObject);
var
  RequestPath, FramePath, HelperPath: String;
  ResultCode: Integer;
begin
  if ZoneCameraCombo.ItemIndex < 0 then Exit;
  ZoneStatusLabel.Caption := 'Capturing the latest frame...';
  WizardForm.Refresh;
  RequestPath := ExpandConstant('{tmp}\onevo-zone-source.json');
  FramePath := ZoneBaseFramePath;
  HelperPath := ExpandConstant('{tmp}\onevo-installer-helper.exe');
  if not FileExists(HelperPath) then ExtractTemporaryFile('onevo-installer-helper.exe');
  if (not WriteCaptureRequest(RequestPath)) or
     (not Exec(HelperPath,
       '--installer-capture "' + RequestPath + '" "' + FramePath + '"',
       ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, ResultCode)) or
     (ResultCode <> 0) or (not FileExists(FramePath)) then begin
    DeleteFile(RequestPath);
    ZoneFrameReady := False;
    ZoneImage.Visible := False;
    ZoneStatusLabel.Caption :=
      'Could not capture a frame. Check the camera/video details, then Refresh Frame.';
    Exit;
  end;
  DeleteFile(RequestPath);
  ZoneFrameReady := True;
  ZoneLoadedFramePath := '';
  ZoneImage.Visible := True;
  // Refreshing an existing saved zone must retain its rectangle so the new
  // frame remains an accurate preview of the saved monitoring area.
  if EditingZoneIndex < 0 then ZonePointCount := 0;
  ZoneStatusLabel.Caption :=
    'Frame ready. Click and drag to create a monitoring box.';
  RenderZoneDrawing;
end;

procedure ZoneCameraChanged(Sender: TObject);
begin
  ZoneFrameReady := FileExists(ZoneBaseFramePath);
  ZoneLoadedFramePath := '';
  ZonePointCount := 0;
  if ZoneFrameReady then begin
    ZoneImage.Visible := True;
    RenderZoneDrawing;
  end else begin
    ZoneImage.Visible := False;
    ZoneStatusLabel.Caption := 'Click Refresh Frame to capture this camera.';
  end;
end;

function GetZonePointer(var DisplayX, DisplayY: Integer; ClampToImage: Boolean): Boolean;
var
  Point: TNativePoint;
begin
  Result := False;
  if not GetCursorPos(Point) then Exit;
  if not ScreenToClient(ZonePage.Surface.Handle, Point) then Exit;
  DisplayX := Point.X - ZoneImage.Left;
  DisplayY := Point.Y - ZoneImage.Top;
  if not ClampToImage then begin
    if (DisplayX < 0) or (DisplayX >= ZoneImage.Width) or
       (DisplayY < 0) or (DisplayY >= ZoneImage.Height) then Exit;
  end else begin
    if DisplayX < 0 then DisplayX := 0;
    if DisplayY < 0 then DisplayY := 0;
    if DisplayX >= ZoneImage.Width then DisplayX := ZoneImage.Width - 1;
    if DisplayY >= ZoneImage.Height then DisplayY := ZoneImage.Height - 1;
  end;
  DisplayX := (DisplayX * 640) div ZoneImage.Width;
  DisplayY := (DisplayY * 360) div ZoneImage.Height;
  Result := True;
end;

procedure SetZoneRectangle(StartX, StartY, EndX, EndY: Integer);
var
  X1, Y1, X2, Y2, Temp: Integer;
begin
  X1 := StartX; Y1 := StartY; X2 := EndX; Y2 := EndY;
  if X1 > X2 then begin Temp := X1; X1 := X2; X2 := Temp; end;
  if Y1 > Y2 then begin Temp := Y1; Y1 := Y2; Y2 := Temp; end;
  ZonePointX[0] := X1; ZonePointY[0] := Y1;
  ZonePointX[1] := X2; ZonePointY[1] := Y1;
  ZonePointX[2] := X2; ZonePointY[2] := Y2;
  ZonePointX[3] := X1; ZonePointY[3] := Y2;
  ZonePointCount := 4;
end;

procedure ZoneMouseTimerTick(HWnd, UMsg, IdEvent, DwTime: LongWord);
var
  MouseDown: Boolean;
  DisplayX, DisplayY: Integer;
begin
  if (WizardForm.CurPageID <> ZonePage.ID) or (not ZoneFrameReady) then Exit;
  MouseDown := (GetAsyncKeyState(1) and $8000) <> 0;
  if MouseDown and (not ZoneDragging) then begin
    if GetZonePointer(DisplayX, DisplayY, False) then begin
      ZoneDragging := True;
      ZoneDragStartX := DisplayX; ZoneDragStartY := DisplayY;
      ZoneDragCurrentX := DisplayX; ZoneDragCurrentY := DisplayY;
      SetZoneRectangle(DisplayX, DisplayY, DisplayX, DisplayY);
      ZoneStatusLabel.Caption := 'Drawing zone. Release the mouse to set the box.';
      RenderZoneDrawing;
    end;
    Exit;
  end;

  if MouseDown and ZoneDragging then begin
    if GetZonePointer(DisplayX, DisplayY, True) and
       ((DisplayX <> ZoneDragCurrentX) or (DisplayY <> ZoneDragCurrentY)) then begin
      ZoneDragCurrentX := DisplayX; ZoneDragCurrentY := DisplayY;
      SetZoneRectangle(ZoneDragStartX, ZoneDragStartY, DisplayX, DisplayY);
      RenderZoneDrawing;
    end;
    Exit;
  end;

  if ZoneDragging then begin
    ZoneDragging := False;
    if (Abs(ZoneDragCurrentX - ZoneDragStartX) < 8) or
       (Abs(ZoneDragCurrentY - ZoneDragStartY) < 8) then begin
      ZonePointCount := 0;
      ZoneStatusLabel.Caption := 'Drag a larger area to create a zone.';
    end else begin
      SetZoneRectangle(ZoneDragStartX, ZoneDragStartY,
        ZoneDragCurrentX, ZoneDragCurrentY);
      ZoneStatusLabel.Caption := 'Zone ready. Enter a name and click Save Zone.';
    end;
    RenderZoneDrawing;
  end;
end;

procedure NewZoneClicked(Sender: TObject);
begin
  EditingZoneIndex := -1;
  ZoneNameEdit.Text := '';
  ZoneTypeCombo.ItemIndex := 0;
  ZonePointCount := 0;
  RenderZoneDrawing;
end;

procedure UndoZonePoint(Sender: TObject);
begin
  if ZonePointCount > 0 then ZonePointCount := ZonePointCount - 1;
  RenderZoneDrawing;
end;

procedure ClearZonePoints(Sender: TObject);
begin
  ZonePointCount := 0;
  RenderZoneDrawing;
end;

function NormalizedCoordinate(Value, Maximum: Integer): String;
var
  Fraction: String;
begin
  Fraction := IntToStr((Value * 1000000) div Maximum);
  while Length(Fraction) < 6 do Fraction := '0' + Fraction;
  Result := '0.' + Fraction;
end;

function CurrentPolygonJson: String;
var
  I: Integer;
  XValue, YValue: String;
begin
  Result := '[';
  for I := 0 to ZonePointCount - 1 do begin
    if I > 0 then Result := Result + ',';
    XValue := NormalizedCoordinate(ZonePointX[I], 640);
    YValue := NormalizedCoordinate(ZonePointY[I], 360);
    // Keep the same normalized polygon contract used by dashboard, tray and AI:
    // [[x,y], ...], never {x,y} point objects.
    Result := Result + '[' + XValue + ',' + YValue + ']';
  end;
  Result := Result + ']';
end;

procedure RebuildZoneList;
var
  I: Integer;
begin
  ZoneList.Items.Clear;
  for I := 0 to SavedZoneCount - 1 do begin
    if (SavedZoneSource[I] >= 0) and
       (SavedZoneSource[I] < ZoneCameraCombo.Items.Count) then
      ZoneList.Items.Add(ZoneCameraCombo.Items[SavedZoneSource[I]] +
        ' - ' + SavedZoneName[I])
    else
      ZoneList.Items.Add('Unavailable camera - ' + SavedZoneName[I]);
  end;
end;

procedure SaveZoneClicked(Sender: TObject);
var
  I, Index: Integer;
begin
  if Trim(ZoneNameEdit.Text) = '' then begin
    MsgBox('Enter a zone name.', mbError, MB_OK);
    Exit;
  end;
  if ZonePointCount < 3 then begin
    MsgBox('Draw the zone with at least 3 points.', mbError, MB_OK);
    Exit;
  end;
  Index := EditingZoneIndex;
  if Index < 0 then begin
    if SavedZoneCount >= 32 then begin
      MsgBox('The installer supports up to 32 zones. Add more later from the tray.',
        mbError, MB_OK);
      Exit;
    end;
    Index := SavedZoneCount;
    SavedZoneCount := SavedZoneCount + 1;
  end;
  SavedZoneSource[Index] := ZoneCameraCombo.ItemIndex;
  SavedZoneName[Index] := Trim(ZoneNameEdit.Text);
  SavedZoneType[Index] := ZoneTypeApiValue;
  SavedZonePolygon[Index] := CurrentPolygonJson;
  SavedZonePointCount[Index] := ZonePointCount;
  for I := 0 to ZonePointCount - 1 do begin
    SavedZonePointX[(Index * 32) + I] := ZonePointX[I];
    SavedZonePointY[(Index * 32) + I] := ZonePointY[I];
  end;
  EditingZoneIndex := -1;
  RebuildZoneList;
  ZoneStatusLabel.Caption := 'Zone saved. It will sync to the dashboard and tray after pairing.';
  NewZoneClicked(Sender);
end;

procedure EditZoneClicked(Sender: TObject);
var
  I: Integer;
begin
  if ZoneList.ItemIndex < 0 then Exit;
  EditingZoneIndex := ZoneList.ItemIndex;
  if (SavedZoneSource[EditingZoneIndex] < 0) or
     (SavedZoneSource[EditingZoneIndex] >= ZoneCameraCombo.Items.Count) then begin
    MsgBox('This zone belongs to a camera that was removed. Delete the zone or add the camera again.',
      mbError, MB_OK);
    EditingZoneIndex := -1;
    Exit;
  end;
  ZoneCameraCombo.ItemIndex := SavedZoneSource[EditingZoneIndex];
  ZoneNameEdit.Text := SavedZoneName[EditingZoneIndex];
  SelectZoneType(SavedZoneType[EditingZoneIndex]);
  ZonePointCount := SavedZonePointCount[EditingZoneIndex];
  for I := 0 to ZonePointCount - 1 do begin
    ZonePointX[I] := SavedZonePointX[(EditingZoneIndex * 32) + I];
    ZonePointY[I] := SavedZonePointY[(EditingZoneIndex * 32) + I];
  end;
  ZoneFrameReady := FileExists(ZoneBaseFramePath);
  if ZoneFrameReady then begin
    ZoneImage.Visible := True;
    RenderZoneDrawing;
  end else
    RefreshZoneFrame(RefreshFrameButton);
  ZoneStatusLabel.Caption := 'Editing saved zone. Change it and click Save Zone.';
end;

procedure DeleteZoneClicked(Sender: TObject);
var
  I, J, Index: Integer;
begin
  Index := ZoneList.ItemIndex;
  if Index < 0 then Exit;
  for I := Index to SavedZoneCount - 2 do begin
    SavedZoneSource[I] := SavedZoneSource[I + 1];
    SavedZoneName[I] := SavedZoneName[I + 1];
    SavedZoneType[I] := SavedZoneType[I + 1];
    SavedZonePolygon[I] := SavedZonePolygon[I + 1];
    SavedZonePointCount[I] := SavedZonePointCount[I + 1];
    for J := 0 to SavedZonePointCount[I] - 1 do begin
      SavedZonePointX[(I * 32) + J] := SavedZonePointX[((I + 1) * 32) + J];
      SavedZonePointY[(I * 32) + J] := SavedZonePointY[((I + 1) * 32) + J];
    end;
  end;
  SavedZoneCount := SavedZoneCount - 1;
  EditingZoneIndex := -1;
  RebuildZoneList;
end;

procedure InitializeWizard;
begin
  WizardForm.ClientWidth := ScaleX(900);
  WizardForm.ClientHeight := ScaleY(650);
  SourceSetupSkipped := False;
  SavedZoneCount := 0;
  EditingZoneIndex := -1;
  NavigatingFromSourceChoice := False;
  ZoneBaseBitmap := TBitmap.Create;
  ZoneRenderBitmap := TBitmap.Create;
  ZoneLoadedFramePath := '';
  WizardForm.CancelButton.Visible := False;

  IdentityPage := CreateInputQueryPage(wpSelectDir,
    'Connect to ONEVO', 'Enter the connector identity',
    'Generate a one-time setup code in the ONEVO dashboard and enter it here.');
  IdentityPage.Add('Setup code:', False);
  IdentityPage.Add('Connector name:', False);
  IdentityPage.Values[1] := 'ONEVO Store Connector';

  SourcePage := CreateInputOptionPage(IdentityPage.ID,
    'Camera source', 'Choose the input type',
    'Choose a source type. Camera and video sources continue to a frame-based zone editor. Choose Skip to install the connector without sources or zones.', True, False);
  SourcePage.Add('Live camera — RTSP URL(s)');
  SourcePage.Add('Live camera — ONVIF camera(s)');
  SourcePage.Add('Video upload — local MP4 file(s)');
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

  ZonePage := CreateCustomPage(FilePage.ID,
    'Camera zones', 'Create monitoring zones for each camera');
  ZoneCameraCombo := TNewComboBox.Create(ZonePage);
  ZoneCameraLabel := TNewStaticText.Create(ZonePage);
  ZoneCameraLabel.Parent := ZonePage.Surface;
  ZoneCameraLabel.Left := 0;
  ZoneCameraLabel.Top := 0;
  ZoneCameraLabel.Caption := 'Camera:';
  ZoneCameraCombo.Parent := ZonePage.Surface;
  ZoneCameraCombo.Left := 0;
  ZoneCameraCombo.Top := ScaleY(18);
  ZoneCameraCombo.Width := ScaleX(260);
  ZoneCameraCombo.Style := csDropDownList;
  ZoneCameraCombo.OnChange := @ZoneCameraChanged;
  RefreshFrameButton := TNewButton.Create(ZonePage);
  RefreshFrameButton.Parent := ZonePage.Surface;
  RefreshFrameButton.Caption := 'Refresh Frame';
  RefreshFrameButton.Left := ScaleX(275);
  RefreshFrameButton.Top := ScaleY(18);
  RefreshFrameButton.Width := ScaleX(110);
  RefreshFrameButton.OnClick := @RefreshZoneFrame;
  ZoneNameLabel := TNewStaticText.Create(ZonePage);
  ZoneNameLabel.Parent := ZonePage.Surface;
  ZoneNameLabel.Left := ScaleX(400);
  ZoneNameLabel.Top := 0;
  ZoneNameLabel.Caption := 'Zone name:';
  ZoneNameEdit := TNewEdit.Create(ZonePage);
  ZoneNameEdit.Parent := ZonePage.Surface;
  ZoneNameEdit.Left := ScaleX(400);
  ZoneNameEdit.Top := ScaleY(18);
  ZoneNameEdit.Width := ScaleX(190);
  ZoneNameEdit.Text := '';
  ZoneTypeLabel := TNewStaticText.Create(ZonePage);
  ZoneTypeLabel.Parent := ZonePage.Surface;
  ZoneTypeLabel.Left := ScaleX(600);
  ZoneTypeLabel.Top := 0;
  ZoneTypeLabel.Caption := 'Zone type:';
  ZoneTypeCombo := TNewComboBox.Create(ZonePage);
  ZoneTypeCombo.Parent := ZonePage.Surface;
  ZoneTypeCombo.Left := ScaleX(600);
  ZoneTypeCombo.Top := ScaleY(18);
  ZoneTypeCombo.Width := ScaleX(150);
  ZoneTypeCombo.Style := csDropDownList;
  ZoneTypeCombo.Items.Add('High-value shelf');
  ZoneTypeCombo.Items.Add('Shelf');
  ZoneTypeCombo.Items.Add('Checkout counter');
  ZoneTypeCombo.Items.Add('Exit');
  ZoneTypeCombo.Items.Add('Blind spot');
  ZoneTypeCombo.Items.Add('Normal area');
  ZoneTypeCombo.ItemIndex := 0;

  ZoneImage := TBitmapImage.Create(ZonePage);
  ZoneImage.Parent := ZonePage.Surface;
  ZoneImage.Left := 0;
  ZoneImage.Top := ScaleY(56);
  ZoneImage.Width := ScaleX(600);
  ZoneImage.Height := ScaleY(338);
  ZoneImage.Stretch := True;
  ZoneImage.Cursor := crCross;
  ZoneImage.Visible := False;
  ZoneMouseTimerId := SetTimer(0, 0, 33, CreateCallback(@ZoneMouseTimerTick));
  ZoneList := TNewListBox.Create(ZonePage);
  SavedZonesLabel := TNewStaticText.Create(ZonePage);
  SavedZonesLabel.Parent := ZonePage.Surface;
  SavedZonesLabel.Left := ScaleX(615);
  SavedZonesLabel.Top := ScaleY(56);
  SavedZonesLabel.Caption := 'Saved zones:';
  ZoneList.Parent := ZonePage.Surface;
  ZoneList.Left := ScaleX(615);
  ZoneList.Top := ScaleY(76);
  ZoneList.Width := ScaleX(235);
  ZoneList.Height := ScaleY(192);
  // A saved-zone row is the edit action: selecting it must immediately load
  // its camera, captured frame, name, and rectangle for inspection.
  ZoneList.OnClick := @EditZoneClicked;

  NewZoneButton := TNewButton.Create(ZonePage);
  NewZoneButton.Parent := ZonePage.Surface;
  NewZoneButton.Caption := '+ New Zone';
  NewZoneButton.Left := ScaleX(615);
  NewZoneButton.Top := ScaleY(278);
  NewZoneButton.Width := ScaleX(110);
  NewZoneButton.OnClick := @NewZoneClicked;
  EditZoneButton := TNewButton.Create(ZonePage);
  EditZoneButton.Parent := ZonePage.Surface;
  EditZoneButton.Caption := 'Edit';
  EditZoneButton.Left := ScaleX(735);
  EditZoneButton.Top := ScaleY(278);
  EditZoneButton.Width := ScaleX(55);
  EditZoneButton.OnClick := @EditZoneClicked;
  DeleteZoneButton := TNewButton.Create(ZonePage);
  DeleteZoneButton.Parent := ZonePage.Surface;
  DeleteZoneButton.Caption := 'Delete';
  DeleteZoneButton.Left := ScaleX(795);
  DeleteZoneButton.Top := ScaleY(278);
  DeleteZoneButton.Width := ScaleX(55);
  DeleteZoneButton.OnClick := @DeleteZoneClicked;
  UndoPointButton := TNewButton.Create(ZonePage);
  UndoPointButton.Parent := ZonePage.Surface;
  UndoPointButton.Caption := 'Undo Point';
  UndoPointButton.Left := ScaleX(615);
  UndoPointButton.Top := ScaleY(316);
  UndoPointButton.Width := ScaleX(110);
  UndoPointButton.OnClick := @UndoZonePoint;
  ClearPointsButton := TNewButton.Create(ZonePage);
  ClearPointsButton.Parent := ZonePage.Surface;
  ClearPointsButton.Caption := 'Clear Points';
  ClearPointsButton.Left := ScaleX(735);
  ClearPointsButton.Top := ScaleY(316);
  ClearPointsButton.Width := ScaleX(115);
  ClearPointsButton.OnClick := @ClearZonePoints;
  SaveZoneButton := TNewButton.Create(ZonePage);
  SaveZoneButton.Parent := ZonePage.Surface;
  SaveZoneButton.Caption := 'Save Zone';
  SaveZoneButton.Left := ScaleX(615);
  SaveZoneButton.Top := ScaleY(354);
  SaveZoneButton.Width := ScaleX(235);
  SaveZoneButton.OnClick := @SaveZoneClicked;

  PointCountLabel := TNewStaticText.Create(ZonePage);
  PointCountLabel.Parent := ZonePage.Surface;
  PointCountLabel.Left := 0;
  PointCountLabel.Top := ScaleY(404);
  PointCountLabel.Width := ScaleX(600);
  PointCountLabel.Caption := '0 point(s) - click and drag to draw a monitoring box';
  ZoneStatusLabel := TNewStaticText.Create(ZonePage);
  ZoneStatusLabel.Parent := ZonePage.Surface;
  ZoneStatusLabel.Left := 0;
  ZoneStatusLabel.Top := ScaleY(428);
  ZoneStatusLabel.Width := ScaleX(600);
  ZoneStatusLabel.Caption := 'Select a camera and click Refresh Frame.';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if UpdateMode and
     ((PageID = IdentityPage.ID) or (PageID = SourcePage.ID) or
      (PageID = RtspPage.ID) or (PageID = OnvifPage.ID) or
      (PageID = FilePage.ID) or (PageID = ZonePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if PreserveExistingConfig and
     ((PageID = IdentityPage.ID) or (PageID = SourcePage.ID) or
      (PageID = RtspPage.ID) or (PageID = OnvifPage.ID) or
      (PageID = FilePage.ID) or (PageID = ZonePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if SourceSetupSkipped and
     ((PageID = RtspPage.ID) or (PageID = OnvifPage.ID) or
      (PageID = FilePage.ID) or (PageID = ZonePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if (PageID = RtspPage.ID) and (SourcePage.SelectedValueIndex <> 0) then Result := True;
  if (PageID = OnvifPage.ID) and (SourcePage.SelectedValueIndex <> 1) then Result := True;
  if (PageID = FilePage.ID) and (SourcePage.SelectedValueIndex <> 2) then Result := True;
  { Source detail pages already prevent Next when no valid source is present.
    Do not use ActiveSourceCount here: Inno can evaluate ShouldSkipPage while a
    file-picker edit is still committing its value, which incorrectly skipped
    the native zone editor for a valid MP4 selection. }
  if (PageID = ZonePage.ID) and
     (SourceSetupSkipped or (SourcePage.SelectedValueIndex < 0)) then
    Result := True;
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
      Exit;
    end;
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
  if CurPageID = ZonePage.ID then begin
    // The dashboard keeps a draft zone until Save is pressed. In the native
    // installer, make Next forgiving: a valid named drawing is saved first so
    // the user never loses a completed box/polygon by clicking Next.
    if (ZonePointCount >= 3) and (Trim(ZoneNameEdit.Text) <> '') then
      SaveZoneClicked(SaveZoneButton);
    if SavedZoneCount = 0 then begin
      MsgBox('Draw a zone and enter its name, then click Save Zone.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    for I := 0 to ZoneCameraCombo.Items.Count - 1 do begin
      ValidCount := 0;
      for Base := 0 to SavedZoneCount - 1 do
        if SavedZoneSource[Base] = I then ValidCount := ValidCount + 1;
      if ValidCount = 0 then begin
        MsgBox('Save at least one zone for ' + ZoneCameraCombo.Items[I] + '.',
          mbError, MB_OK);
        Result := False;
        Exit;
      end;
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
  else if CurPageID = ZonePage.ID then begin
    PopulateZoneCameras;
    ZoneCameraChanged(ZoneCameraCombo);
    if (ZoneCameraCombo.ItemIndex >= 0) and (not ZoneFrameReady) then
      RefreshZoneFrame(RefreshFrameButton);
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
  end
  else if CurPageID = wpFinished then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonFinish)
  else if CurPageID = wpReady then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall)
  else
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, UpdatePath, MediaPath, Json, SourcesJson, ItemJson,
    PendingZonesJson, ReferencePath: String;
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
  PendingZonesJson := '';
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

  for I := 0 to SavedZoneCount - 1 do begin
    ReferencePath := ExpandConstant('{commonappdata}\ONEVO\Connector\media\zone-reference-' +
      IntToStr(SavedZoneSource[I]) + '.bmp');
    if not CopyFile(
      ExpandConstant('{tmp}\onevo-zone-frame-' + IntToStr(SavedZoneSource[I]) + '.bmp'),
      ReferencePath, False) then
      RaiseException('Could not preserve the zone reference frame for camera ' +
        IntToStr(SavedZoneSource[I] + 1) + '.');
    ItemJson := '{"source_index":' + IntToStr(SavedZoneSource[I]) +
      ',"name":"' + JsonEscape(SavedZoneName[I]) +
      '","zone_type":"' + JsonEscape(SavedZoneType[I]) +
      '","polygon":' + SavedZonePolygon[I] +
      ',"reference_frame":"' + JsonEscape(ReferencePath) + '"}';
    if PendingZonesJson <> '' then PendingZonesJson := PendingZonesJson + ',';
    PendingZonesJson := PendingZonesJson + ItemJson;
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
    '  "sources": [' + SourcesJson + '],' + #13#10 +
    '  "pending_zones": [' + PendingZonesJson + ']' + #13#10 +
    '}' + #13#10;
  SaveStringToFile(ConfigPath, Json, False);
end;
