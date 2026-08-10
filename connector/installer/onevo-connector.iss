; Display brand is onetix; install paths / AppId / service stay ONEVO for upgrades.
#define AppName "onetix Local Connector"
#define AppVersion "1.1.18"
#define AppPublisher "onetix"
#define AppExeName "onevo-connector.exe"
#define AppServiceExe "onevo-connector-service.exe"
#define AppId "{{A7C3E91F-4B2D-4E8A-9F01-0E0C0C001100}"
#define BrandFont "IBM Plex Sans"
#define BrandFontMono "IBM Plex Mono"
#define BrandFontFallback "Segoe UI"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ONEVO\Connector
DefaultGroupName=onetix
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableWelcomePage=yes
DisableReadyPage=yes
DirExistsWarning=no
OutputDir=..\dist
; Filename keeps ONEVO prefix so backend ConnectorInstallerService still finds it.
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
WizardImageFile=assets\wizard-side.bmp
WizardSmallImageFile=assets\wizard-small.bmp
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
; Brand fonts for the wizard (OFL) — loaded at runtime via AddFontResource.
Source: "assets\fonts\IBMPlexSans-Regular.ttf"; Flags: dontcopy
Source: "assets\fonts\IBMPlexSans-Medium.ttf"; Flags: dontcopy
Source: "assets\fonts\IBMPlexSans-SemiBold.ttf"; Flags: dontcopy
Source: "assets\fonts\IBMPlexMono-Medium.ttf"; Flags: dontcopy
Source: "assets\fonts\OFL.txt"; DestDir: "{app}\assets\fonts"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\ONEVO\Connector\data"; Permissions: users-modify
Name: "{commonappdata}\ONEVO\Connector\media"; Permissions: users-modify
Name: "{app}\bin"
Name: "{app}\assets\fonts"

[Icons]
Name: "{group}\onetix Connector Status"; Filename: "{app}\{#AppExeName}"; Parameters: "--open-admin"; WorkingDir: "{app}"; IconFilename: "{app}\assets\onevo.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\onetix Connector Status"; Filename: "{app}\{#AppExeName}"; Parameters: "--open-admin"; WorkingDir: "{app}"; IconFilename: "{app}\assets\onevo.ico"

[Run]
; In-place updates preserve the existing service registration. Unregistering and
; immediately registering it again creates a race when a tray update overlaps a
; manually started installer and can leave the connector with no service.
Filename: "{app}\{#AppServiceExe}"; Parameters: "install"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Installing Windows service..."; Check: not ExistingService
Filename: "{sys}\sc.exe"; Parameters: "config ONEVOConnector start= demand"; Flags: runhidden waituntilterminated; Check: PausedMarkerExists
Filename: "{app}\{#AppServiceExe}"; Parameters: "start"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Activating connector and starting monitoring..."; Check: not PausedMarkerExists
Filename: "{app}\{#AppExeName}"; Parameters: "--tray"; WorkingDir: "{app}"; Flags: runasoriginaluser runhidden nowait; StatusMsg: "Starting onetix system tray..."
Filename: "http://localhost:8099/"; Flags: shellexec runasoriginaluser nowait; StatusMsg: "Opening onetix local dashboard..."; Check: OpenDashboardAfterFirstInstall

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
const
  WM_FONTCHANGE = $001D;

function AddFontResource(lpszFilename: String): Integer;
  external 'AddFontResourceW@gdi32.dll stdcall';
function RemoveFontResource(lpFileName: String): Boolean;
  external 'RemoveFontResourceW@gdi32.dll stdcall';
function BrandSendMessage(hWnd: LongWord; Msg, wParam, lParam: LongWord): LongWord;
  external 'SendMessageW@user32.dll stdcall';

var
  BrandFontsLoaded: Boolean;
  ActiveBrandFont: String;
  IdentityPage: TInputQueryWizardPage;
  IdentityKeyLabel, IdentitySecureLabel, IdentityExampleLabel: TNewStaticText;
  GlobalSidebar, IdentitySidebar, SourceSidebar, ZoneSidebar: TBitmapImage;
  IdentityHeadingLabel, IdentityDescriptionLabel: TNewStaticText;
  SourcePage: TWizardPage;
  ZonePage: TWizardPage;
  SelectedSourceType: Integer;
  EditingSourceIndex: Integer;
  AddedSourceCount: Integer;
  AddedSourceKind: array[0..15] of Integer;
  AddedSourceRtsp: array[0..15] of String;
  AddedSourceHost, AddedSourcePort, AddedSourceUser, AddedSourcePass: array[0..15] of String;
  AddedSourceMp4: array[0..15] of String;
  RtspBtn, OnvifBtn, Mp4Btn: TNewButton;
  RtspCardLabel, OnvifCardLabel, Mp4CardLabel: TNewStaticText;
  RtspHintLabel, Mp4HintLabel, AddedSourcesLabel: TNewStaticText;
  RtspUrlEdit: TNewEdit;
  RtspUrlLabel: TNewStaticText;
  OnvifHostEdit, OnvifPortEdit, OnvifUserEdit, OnvifPassEdit: TNewEdit;
  OnvifHostLabel, OnvifPortLabel, OnvifUserLabel, OnvifPassLabel: TNewStaticText;
  Mp4PathEdit: TNewEdit;
  Mp4BrowseButton: TNewButton;
  Mp4DropPanel: TPanel;
  Mp4DropTitle, Mp4DropOrLabel: TNewStaticText;
  AddSourceButton: TNewButton;
  Mp4PathLabel: TNewStaticText;
  SourceList: TNewListBox;
  SourceRowLabel: array[0..15] of TNewStaticText;
  SourceRowTypeLabel, SourceRowPathLabel, SourceRowStatusLabel: array[0..15] of TNewStaticText;
  SourceRowEditButton, SourceRowDeleteButton: array[0..15] of TNewButton;
  SourceHeaderName, SourceHeaderType, SourceHeaderPath, SourceHeaderStatus,
    SourceHeaderActions: TNewStaticText;
  ClearAllSourcesButton: TNewButton;
  SuccessSummaryLabel: TNewStaticText;
  SuccessHeadingLabel, SuccessDescriptionLabel, SuccessIconLabel: TNewStaticText;
  ZoneCameraCombo, ZoneTypeCombo: TNewComboBox;
  ZoneNameEdit: TNewEdit;
  ZoneImage: TBitmapImage;
  ZoneBaseBitmap, ZoneRenderBitmap: TBitmap;
  ZoneLoadedFramePath: String;
  ZoneMouseTimerId: LongWord;
  ZoneList: TNewListBox;
  ZoneRowPanel: array[0..7] of TPanel;
  ZoneRowLabel: array[0..7] of TNewStaticText;
  ZoneRowEditButton, ZoneRowDeleteButton: array[0..7] of TNewButton;
  ZoneCameraLabel, ZoneNameLabel, ZoneTypeLabel, SavedZonesLabel: TNewStaticText;
  RefreshFrameButton, NewZoneButton, UndoPointButton,
    ClearPointsButton, SaveZoneButton: TNewButton;
  ZoneStatusLabel, PointCountLabel: TNewStaticText;
  SourceSetupSkipped: Boolean;
  ZoneFrameReady: Boolean;
  ZoneDragging: Boolean;
  ZoneDragStartX, ZoneDragStartY, ZoneDragCurrentX, ZoneDragCurrentY: Integer;
  ZonePointX, ZonePointY: array[0..31] of Integer;
  ZonePointCount: Integer;
  SavedZoneSource: array[0..31] of Integer;
  SavedZonePointCount: array[0..31] of Integer;
  SavedZonePointX, SavedZonePointY: array[0..1023] of Integer;
  SavedZoneName, SavedZoneType, SavedZonePolygon: array[0..31] of String;
  VisibleZoneIndex: array[0..31] of Integer;
  VisibleZoneCount: Integer;
  SavedZoneCount, EditingZoneIndex: Integer;
  ExistingInstall: Boolean;
  OldWizardWndProc: Longint;
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

procedure LoadBrandFonts;
var
  Loaded: Integer;
begin
  BrandFontsLoaded := False;
  ActiveBrandFont := '{#BrandFontFallback}';
  try
    ExtractTemporaryFile('IBMPlexSans-Regular.ttf');
    ExtractTemporaryFile('IBMPlexSans-Medium.ttf');
    ExtractTemporaryFile('IBMPlexSans-SemiBold.ttf');
    ExtractTemporaryFile('IBMPlexMono-Medium.ttf');
    Loaded := 0;
    Loaded := Loaded + AddFontResource(ExpandConstant('{tmp}\IBMPlexSans-Regular.ttf'));
    Loaded := Loaded + AddFontResource(ExpandConstant('{tmp}\IBMPlexSans-Medium.ttf'));
    Loaded := Loaded + AddFontResource(ExpandConstant('{tmp}\IBMPlexSans-SemiBold.ttf'));
    Loaded := Loaded + AddFontResource(ExpandConstant('{tmp}\IBMPlexMono-Medium.ttf'));
    if Loaded > 0 then begin
      BrandFontsLoaded := True;
      ActiveBrandFont := '{#BrandFont}';
      BrandSendMessage(HWND_BROADCAST, WM_FONTCHANGE, 0, 0);
    end;
  except
    BrandFontsLoaded := False;
    ActiveBrandFont := '{#BrandFontFallback}';
  end;
end;

procedure UnloadBrandFonts;
begin
  if not BrandFontsLoaded then Exit;
  RemoveFontResource(ExpandConstant('{tmp}\IBMPlexSans-Regular.ttf'));
  RemoveFontResource(ExpandConstant('{tmp}\IBMPlexSans-Medium.ttf'));
  RemoveFontResource(ExpandConstant('{tmp}\IBMPlexSans-SemiBold.ttf'));
  RemoveFontResource(ExpandConstant('{tmp}\IBMPlexMono-Medium.ttf'));
  BrandSendMessage(HWND_BROADCAST, WM_FONTCHANGE, 0, 0);
  BrandFontsLoaded := False;
end;

procedure StyleFont(AFont: TFont; FontSize: Integer; Bold: Boolean);
begin
  AFont.Name := ActiveBrandFont;
  AFont.Size := FontSize;
  if Bold then AFont.Style := [fsBold] else AFont.Style := [];
  AFont.Color := $242529; { ink #292524 in BGR }
end;

procedure ApplyWizardBrandFonts;
begin
  StyleFont(WizardForm.Font, 9, False);
  StyleFont(WizardForm.PageNameLabel.Font, 12, True);
  StyleFont(WizardForm.PageDescriptionLabel.Font, 9, False);
  StyleFont(WizardForm.WelcomeLabel1.Font, 14, True);
  StyleFont(WizardForm.WelcomeLabel2.Font, 9, False);
  StyleFont(WizardForm.FinishedLabel.Font, 9, False);
  StyleFont(WizardForm.NextButton.Font, 9, False);
  StyleFont(WizardForm.BackButton.Font, 9, False);
  StyleFont(WizardForm.CancelButton.Font, 9, False);
end;

procedure DeinitializeSetup();
begin
  UnloadBrandFonts;
end;

function InitializeSetup(): Boolean;
var
  Choice: Integer;
begin
  LoadBrandFonts;
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
      'onetix Connector ' + InstalledVersion + ' is already installed.' + #13#10 +
      'This installer is version {#AppVersion}. Downgrading is not supported.',
      mbError, MB_OK);
    Result := False;
    Exit;
  end;

  if ExistingInstall and not UpdateMode then begin
    if InstalledVersion = '' then InstalledVersion := 'an earlier version';
    Choice := MsgBox(
      'onetix Connector ' + InstalledVersion + ' is already installed.' + #13#10 +
      'Update it to version {#AppVersion}?' + #13#10#13#10 +
      'Your existing connector identity and camera data will be preserved.',
      mbConfirmation, MB_OKCANCEL);
    if Choice <> IDOK then begin
      Result := False;
      Exit;
    end;
  end else if OrphanedRepair then begin
    MsgBox(
      'A previous onetix connector pairing was found, but its Windows service is missing.' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Setup will repair the local service and keep the existing store, cameras, and zones.',
      mbInformation, MB_OK);
  end else if PreviousConfigFound then begin
    MsgBox(
      'A previous onetix configuration was found, but the application is not installed.' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Setup will remove the incomplete data and start a new configuration. ' +
      'You will enter the setup code and camera sources again.',
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
  // Open local admin UI after first-time install (not /UPDATE / preserve-only).
  Result := (not UpdateMode) and (not PreserveExistingConfig);
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



procedure ClearSourceForm;
begin
  RtspUrlEdit.Text := '';
  OnvifHostEdit.Text := '';
  OnvifPortEdit.Text := '80';
  OnvifUserEdit.Text := 'admin';
  OnvifPassEdit.Text := '';
  Mp4PathEdit.Text := '';
  EditingSourceIndex := -1;
  AddSourceButton.Caption := '+ Add';
end;

function SourceDisplayLine(Index: Integer): String;
begin
  if AddedSourceKind[Index] = 0 then
    Result := IntToStr(Index + 1) + '. [RTSP] ' + AddedSourceRtsp[Index] + '  - Valid'
  else if AddedSourceKind[Index] = 1 then
    Result := IntToStr(Index + 1) + '. [ONVIF] ' + AddedSourceHost[Index] + ':' +
      AddedSourcePort[Index] + ' (' + AddedSourceUser[Index] + ')  - Connected'
  else
    Result := IntToStr(Index + 1) + '. [MP4] ' + ExtractFileName(AddedSourceMp4[Index]);
end;

procedure RefreshSourceList;
var
  I: Integer;
  ShowList: Boolean;
begin
  SourceList.Items.Clear;
  for I := 0 to AddedSourceCount - 1 do
    SourceList.Items.Add(SourceDisplayLine(I));
  ShowList := AddedSourceCount > 0;
  AddedSourcesLabel.Visible := ShowList;
  SourceList.Visible := False;
  for I := 0 to 15 do begin
    SourceRowLabel[I].Visible := I < AddedSourceCount;
    SourceRowTypeLabel[I].Visible := I < AddedSourceCount;
    SourceRowPathLabel[I].Visible := I < AddedSourceCount;
    SourceRowStatusLabel[I].Visible := I < AddedSourceCount;
    SourceRowEditButton[I].Visible := I < AddedSourceCount;
    SourceRowDeleteButton[I].Visible := I < AddedSourceCount;
    if I < AddedSourceCount then begin
      SourceRowLabel[I].Caption := 'Source ' + IntToStr(I + 1);
      if AddedSourceKind[I] = 0 then begin
        SourceRowTypeLabel[I].Caption := 'RTSP';
        SourceRowPathLabel[I].Caption := AddedSourceRtsp[I];
        SourceRowStatusLabel[I].Caption := 'Ready';
      end else if AddedSourceKind[I] = 1 then begin
        SourceRowTypeLabel[I].Caption := 'ONVIF';
        SourceRowPathLabel[I].Caption := AddedSourceHost[I] + ':' + AddedSourcePort[I];
        SourceRowStatusLabel[I].Caption := 'Ready';
      end else begin
        SourceRowLabel[I].Caption := 'Store Video ' + IntToStr(I + 1);
        SourceRowTypeLabel[I].Caption := 'Video File';
        SourceRowPathLabel[I].Caption := ExtractFileName(AddedSourceMp4[I]);
        SourceRowStatusLabel[I].Caption := 'Ready';
      end;
    end;
  end;
  SourceHeaderName.Visible := ShowList;
  SourceHeaderType.Visible := ShowList;
  SourceHeaderPath.Visible := ShowList;
  SourceHeaderStatus.Visible := ShowList;
  SourceHeaderActions.Visible := ShowList;
  ClearAllSourcesButton.Visible := ShowList;
  AddedSourcesLabel.Caption := 'Added Sources (' + IntToStr(AddedSourceCount) + ')';
  if AddedSourceCount > 0 then begin
    SourceSetupSkipped := False;
    WizardForm.NextButton.Caption := 'Next';
  end else
    WizardForm.NextButton.Caption := 'Skip';
end;

procedure SetSourcePanelVisible;
var
  ShowForm: Boolean;
begin
  ShowForm := SelectedSourceType >= 0;

  RtspUrlLabel.Visible := SelectedSourceType = 0;
  RtspUrlEdit.Visible := SelectedSourceType = 0;
  RtspHintLabel.Visible := SelectedSourceType = 0;

  OnvifHostLabel.Visible := SelectedSourceType = 1;
  OnvifHostEdit.Visible := SelectedSourceType = 1;
  OnvifPortLabel.Visible := SelectedSourceType = 1;
  OnvifPortEdit.Visible := SelectedSourceType = 1;
  OnvifUserLabel.Visible := SelectedSourceType = 1;
  OnvifUserEdit.Visible := SelectedSourceType = 1;
  OnvifPassLabel.Visible := SelectedSourceType = 1;
  OnvifPassEdit.Visible := SelectedSourceType = 1;

  Mp4PathLabel.Visible := SelectedSourceType = 2;
  Mp4PathEdit.Visible := SelectedSourceType = 2;
  Mp4BrowseButton.Visible := SelectedSourceType = 2;
  Mp4HintLabel.Visible := SelectedSourceType = 2;
  Mp4DropPanel.Visible := SelectedSourceType = 2;

  AddSourceButton.Visible := ShowForm;

  if SelectedSourceType = 0 then begin
    RtspBtn.Caption := Chr(149) + ' RTSP Camera';
  end else
    RtspBtn.Caption := 'RTSP Camera';
  if SelectedSourceType = 1 then begin
    OnvifBtn.Caption := Chr(149) + ' ONVIF Camera';
  end else
    OnvifBtn.Caption := 'ONVIF Camera';
  if SelectedSourceType = 2 then begin
    Mp4Btn.Caption := Chr(149) + ' Local MP4';
  end else
    Mp4Btn.Caption := 'Local MP4';

  RefreshSourceList;
end;

procedure SelectSourceType(TypeIndex: Integer);
begin
  SelectedSourceType := TypeIndex;
  ClearSourceForm;
  SetSourcePanelVisible;
end;

procedure RtspTypeClicked(Sender: TObject);
begin
  SelectSourceType(0);
end;

procedure OnvifTypeClicked(Sender: TObject);
begin
  SelectSourceType(1);
end;

procedure Mp4TypeClicked(Sender: TObject);
begin
  SelectSourceType(2);
end;

procedure AddMp4File(FileName: String); forward;

procedure BrowseMp4Clicked(Sender: TObject);
var
  FileNames: TStringList;
  I: Integer;
begin
  FileNames := TStringList.Create;
  try
    if GetOpenFileNameMulti('Select MP4 videos', FileNames,
       ExpandConstant('{userdocs}'), 'MP4 video (*.mp4)|*.mp4', 'mp4') then begin
      for I := 0 to FileNames.Count - 1 do
        AddMp4File(FileNames[I]);
      RefreshSourceList;
    end;
  finally
    FileNames.Free;
  end;
end;

procedure AddMp4File(FileName: String);
var
  I, Index: Integer;
begin
  if (not FileExists(FileName)) or
     (Lowercase(ExtractFileExt(FileName)) <> '.mp4') then Exit;
  for I := 0 to AddedSourceCount - 1 do
    if (AddedSourceKind[I] = 2) and
       (CompareText(AddedSourceMp4[I], FileName) = 0) then Exit;
  if AddedSourceCount >= 16 then Exit;
  Index := AddedSourceCount;
  AddedSourceCount := AddedSourceCount + 1;
  AddedSourceKind[Index] := 2;
  AddedSourceMp4[Index] := FileName;
  AddedSourceRtsp[Index] := '';
  AddedSourceHost[Index] := '';
  AddedSourcePort[Index] := '';
  AddedSourceUser[Index] := '';
  AddedSourcePass[Index] := '';
  SourceSetupSkipped := False;
end;

procedure ClearAllSourcesClicked(Sender: TObject);
begin
  AddedSourceCount := 0;
  ClearSourceForm;
  RefreshSourceList;
end;

procedure AddSourceClicked(Sender: TObject);
var
  Index, Port: Integer;
  Url, Host: String;
begin
  if SelectedSourceType < 0 then begin
    MsgBox('Select RTSP, ONVIF, or Local MP4 first.', mbInformation, MB_OK);
    Exit;
  end;

  if SelectedSourceType = 0 then begin
    Url := Trim(RtspUrlEdit.Text);
    if Url = '' then begin
      MsgBox('Enter an RTSP URL.', mbError, MB_OK);
      Exit;
    end;
    if Pos('rtsp://', Lowercase(Url)) <> 1 then begin
      MsgBox('RTSP URL must start with rtsp://.', mbError, MB_OK);
      Exit;
    end;
  end else if SelectedSourceType = 1 then begin
    Host := Trim(OnvifHostEdit.Text);
    Port := StrToIntDef(Trim(OnvifPortEdit.Text), 0);
    if Host = '' then begin
      MsgBox('Enter an ONVIF host / IP.', mbError, MB_OK);
      Exit;
    end;
    if (Port < 1) or (Port > 65535) then begin
      MsgBox('Enter a valid ONVIF port.', mbError, MB_OK);
      Exit;
    end;
  end else begin
    if (Trim(Mp4PathEdit.Text) = '') or (not FileExists(Mp4PathEdit.Text)) then begin
      MsgBox('Select an existing MP4 video file.', mbError, MB_OK);
      Exit;
    end;
  end;

  if EditingSourceIndex >= 0 then
    Index := EditingSourceIndex
  else begin
    if AddedSourceCount >= 16 then begin
      MsgBox('You can add up to 16 sources here. Add more later from the dashboard.',
        mbInformation, MB_OK);
      Exit;
    end;
    Index := AddedSourceCount;
    AddedSourceCount := AddedSourceCount + 1;
  end;

  AddedSourceKind[Index] := SelectedSourceType;
  AddedSourceRtsp[Index] := '';
  AddedSourceHost[Index] := '';
  AddedSourcePort[Index] := '';
  AddedSourceUser[Index] := '';
  AddedSourcePass[Index] := '';
  AddedSourceMp4[Index] := '';

  if SelectedSourceType = 0 then
    AddedSourceRtsp[Index] := Trim(RtspUrlEdit.Text)
  else if SelectedSourceType = 1 then begin
    AddedSourceHost[Index] := Trim(OnvifHostEdit.Text);
    AddedSourcePort[Index] := Trim(OnvifPortEdit.Text);
    AddedSourceUser[Index] := Trim(OnvifUserEdit.Text);
    AddedSourcePass[Index] := OnvifPassEdit.Text;
  end else
    AddedSourceMp4[Index] := Trim(Mp4PathEdit.Text);

  ClearSourceForm;
  RefreshSourceList;
end;

procedure EditSourceClicked(Sender: TObject);
var
  Index: Integer;
begin
  Index := TNewButton(Sender).Tag;
  if Index < 0 then begin
    MsgBox('Select a source in the list to edit.', mbInformation, MB_OK);
    Exit;
  end;
  EditingSourceIndex := Index;
  SelectedSourceType := AddedSourceKind[Index];
  SetSourcePanelVisible;
  if SelectedSourceType = 0 then
    RtspUrlEdit.Text := AddedSourceRtsp[Index]
  else if SelectedSourceType = 1 then begin
    OnvifHostEdit.Text := AddedSourceHost[Index];
    OnvifPortEdit.Text := AddedSourcePort[Index];
    OnvifUserEdit.Text := AddedSourceUser[Index];
    OnvifPassEdit.Text := AddedSourcePass[Index];
  end else
    Mp4PathEdit.Text := AddedSourceMp4[Index];
  AddSourceButton.Caption := 'Update Source';
end;

procedure DeleteSourceClicked(Sender: TObject);
var
  Index, I: Integer;
begin
  Index := TNewButton(Sender).Tag;
  if Index < 0 then begin
    MsgBox('Select a source in the list to delete.', mbInformation, MB_OK);
    Exit;
  end;
  for I := Index to AddedSourceCount - 2 do begin
    AddedSourceKind[I] := AddedSourceKind[I + 1];
    AddedSourceRtsp[I] := AddedSourceRtsp[I + 1];
    AddedSourceHost[I] := AddedSourceHost[I + 1];
    AddedSourcePort[I] := AddedSourcePort[I + 1];
    AddedSourceUser[I] := AddedSourceUser[I + 1];
    AddedSourcePass[I] := AddedSourcePass[I + 1];
    AddedSourceMp4[I] := AddedSourceMp4[I + 1];
  end;
  AddedSourceCount := AddedSourceCount - 1;
  ClearSourceForm;
  RefreshSourceList;
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
begin
  Result := AddedSourceCount;
end;

procedure PopulateZoneCameras;
var
  I: Integer;
begin
  ZoneCameraCombo.Items.Clear;
  for I := 0 to AddedSourceCount - 1 do begin
    if AddedSourceKind[I] = 0 then
      ZoneCameraCombo.Items.Add('Camera ' + IntToStr(I + 1))
    else if AddedSourceKind[I] = 1 then
      ZoneCameraCombo.Items.Add('ONVIF Camera ' + IntToStr(I + 1))
    else
      ZoneCameraCombo.Items.Add('Local Video ' + IntToStr(I + 1));
  end;
  if ZoneCameraCombo.Items.Count > 0 then ZoneCameraCombo.ItemIndex := 0;
end;

function SourceOriginalIndex(CompactIndex: Integer): Integer;
begin
  if (CompactIndex >= 0) and (CompactIndex < AddedSourceCount) then
    Result := CompactIndex
  else
    Result := -1;
end;

function WriteCaptureRequest(Path: String): Boolean;
var
  SourceIndex: Integer;
  Json: String;
begin
  Result := False;
  SourceIndex := SourceOriginalIndex(ZoneCameraCombo.ItemIndex);
  if SourceIndex < 0 then Exit;
  if AddedSourceKind[SourceIndex] = 0 then
    Json := '{"rtsp_url":"' + JsonEscape(Trim(AddedSourceRtsp[SourceIndex])) + '"}'
  else if AddedSourceKind[SourceIndex] = 1 then
    Json := '{"onvif_host":"' + JsonEscape(Trim(AddedSourceHost[SourceIndex])) +
      '","onvif_port":' + IntToStr(StrToIntDef(Trim(AddedSourcePort[SourceIndex]), 80)) +
      ',"onvif_user":"' + JsonEscape(Trim(AddedSourceUser[SourceIndex])) +
      '","onvif_pass":"' + JsonEscape(AddedSourcePass[SourceIndex]) + '"}'
  else
    Json := '{"source_file":"' + JsonEscape(AddedSourceMp4[SourceIndex]) + '"}';
  Result := SaveStringToFile(Path, Json, False);
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
  { Dashboard accent #2563EB as BGR }
  ZoneRenderBitmap.Canvas.Pen.Color := $EB6325;
  ZoneRenderBitmap.Canvas.Pen.Width := 3;
  ZoneRenderBitmap.Canvas.Brush.Color := $EB6325;
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

procedure RebuildZoneList; forward;

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
  RebuildZoneList;
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
    end;
    Exit;
  end;

  if MouseDown and ZoneDragging then begin
    if GetZonePointer(DisplayX, DisplayY, True) and
       ((DisplayX <> ZoneDragCurrentX) or (DisplayY <> ZoneDragCurrentY)) then begin
      ZoneDragCurrentX := DisplayX; ZoneDragCurrentY := DisplayY;
      SetZoneRectangle(ZoneDragStartX, ZoneDragStartY, DisplayX, DisplayY);
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
  I, Row: Integer;
begin
  ZoneList.Items.Clear;
  for Row := 0 to 7 do begin
    ZoneRowPanel[Row].Visible := False;
    ZoneRowLabel[Row].Visible := False;
    ZoneRowEditButton[Row].Visible := False;
    ZoneRowDeleteButton[Row].Visible := False;
  end;
  VisibleZoneCount := 0;
  for I := 0 to SavedZoneCount - 1 do begin
    if SavedZoneSource[I] = ZoneCameraCombo.ItemIndex then begin
      VisibleZoneIndex[VisibleZoneCount] := I;
      Row := VisibleZoneCount;
      VisibleZoneCount := VisibleZoneCount + 1;
      ZoneList.Items.Add(SavedZoneName[I] + '  -  ' + SavedZoneType[I]);
      if Row <= 7 then begin
        ZoneRowPanel[Row].Visible := True;
        ZoneRowLabel[Row].Visible := True;
        ZoneRowEditButton[Row].Visible := True;
        ZoneRowDeleteButton[Row].Visible := True;
        ZoneRowLabel[Row].Caption := SavedZoneName[I] + '  -  ' + SavedZoneType[I];
        ZoneRowEditButton[Row].Tag := I;
        ZoneRowDeleteButton[Row].Tag := I;
        if EditingZoneIndex = I then begin
          ZoneRowPanel[Row].Color := $00D96A10;
          ZoneRowLabel[Row].Font.Color := clWhite;
        end else begin
          ZoneRowPanel[Row].Color := clWhite;
          ZoneRowLabel[Row].Font.Color := clBlack;
        end;
      end;
    end;
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
  if SavedZoneCount > 0 then
    WizardForm.NextButton.Caption := 'Install'
  else
    WizardForm.NextButton.Caption := 'Skip';
  ZoneStatusLabel.Caption := 'Zone saved. It will sync to the dashboard and tray after pairing.';
  NewZoneClicked(Sender);
end;

procedure EditZoneClicked(Sender: TObject);
var
  I: Integer;
begin
  if Sender = ZoneList then begin
    if ZoneList.ItemIndex < 0 then Exit;
    EditingZoneIndex := VisibleZoneIndex[ZoneList.ItemIndex];
  end else
    EditingZoneIndex := TNewButton(Sender).Tag;
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
  RebuildZoneList;
end;

procedure DeleteZoneClicked(Sender: TObject);
var
  I, J, Index: Integer;
begin
  if Sender = ZoneList then begin
    if ZoneList.ItemIndex < 0 then Exit;
    Index := VisibleZoneIndex[ZoneList.ItemIndex];
  end else
    Index := TNewButton(Sender).Tag;
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
  if SavedZoneCount > 0 then
    WizardForm.NextButton.Caption := 'Install'
  else
    WizardForm.NextButton.Caption := 'Skip';
end;


procedure SetupCodeChanged(Sender: TObject);
begin
  if WizardForm.CurPageID = IdentityPage.ID then
    WizardForm.NextButton.Enabled := Trim(IdentityPage.Values[0]) <> '';
end;

function DragQueryFileW(hDrop, FileIndex: LongWord; FileName: String;
  FileNameSize: LongWord): LongWord;
  external 'DragQueryFileW@shell32.dll stdcall';
procedure DragFinish(hDrop: LongWord);
  external 'DragFinish@shell32.dll stdcall';
procedure DragAcceptFiles(hWnd: LongWord; Accept: Boolean);
  external 'DragAcceptFiles@shell32.dll stdcall';
function ChangeWindowMessageFilterEx(hWnd, Msg, Action: LongWord;
  ChangeInfo: LongWord): Boolean;
  external 'ChangeWindowMessageFilterEx@user32.dll stdcall';
function SetWindowLongW(hWnd: LongWord; Index, NewLong: Longint): Longint;
  external 'SetWindowLongW@user32.dll stdcall';
function CallWindowProcW(PrevWndFunc: Longint; hWnd, Msg, wParam,
  lParam: LongWord): Longint;
  external 'CallWindowProcW@user32.dll stdcall';

function WizardDropWndProc(hWnd, Msg, wParam, lParam: LongWord): Longint;
var
  FileName: String;
  FileLength, FileCount, I: LongWord;
begin
  if Msg = $0233 then begin { WM_DROPFILES }
    if (WizardForm.CurPageID = SourcePage.ID) and (SelectedSourceType = 2) then begin
      FileCount := DragQueryFileW(wParam, $FFFFFFFF, '', 0);
      if FileCount > 0 then
        for I := 0 to FileCount - 1 do begin
          FileLength := DragQueryFileW(wParam, I, '', 0);
          SetLength(FileName, FileLength + 1);
          DragQueryFileW(wParam, I, FileName, FileLength + 1);
          SetLength(FileName, FileLength);
          AddMp4File(FileName);
        end;
      Mp4DropTitle.Caption := IntToStr(FileCount) + ' file(s) processed';
      RefreshSourceList;
    end;
    DragFinish(wParam);
    Result := 0;
    Exit;
  end;
  Result := CallWindowProcW(OldWizardWndProc, hWnd, Msg, wParam, lParam);
end;

procedure InitializeWizard;
var
  CardW, CardGap, TopY, ContentW: Integer;
  I: Integer;
begin
  { Wide, DPI-aware shell matching the ONETIX setup references. }
  { Compact desktop installer size; intentionally not maximized. }
  WizardForm.ClientWidth := ScaleX(800);
  WizardForm.ClientHeight := ScaleY(570);
  WizardForm.Color := clWhite;
  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.Font.Size := 10;
  SourceSetupSkipped := False;
  SelectedSourceType := -1;
  EditingSourceIndex := -1;
  AddedSourceCount := 0;
  SavedZoneCount := 0;
  EditingZoneIndex := -1;
  ZoneBaseBitmap := TBitmap.Create;
  ZoneRenderBitmap := TBitmap.Create;
  ZoneLoadedFramePath := '';
  { Keep the native Windows close/minimise controls and the installer cancel path
    operational.  Hiding Cancel also made the title-bar close action appear dead. }
  WizardForm.CancelButton.Visible := False;
  ApplyWizardBrandFonts;

  ExtractTemporaryFile('wizard-sidebar.bmp');
  GlobalSidebar := TBitmapImage.Create(WizardForm);
  GlobalSidebar.Parent := WizardForm.InnerNotebook;
  GlobalSidebar.Left := 0;
  GlobalSidebar.Top := 0;
  GlobalSidebar.Width := ScaleX(200);
  GlobalSidebar.Height := WizardForm.InnerNotebook.Height;
  GlobalSidebar.Stretch := True;
  GlobalSidebar.Bitmap.LoadFromFile(ExpandConstant('{tmp}\wizard-sidebar.bmp'));
  GlobalSidebar.Visible := False;

  IdentityPage := CreateInputQueryPage(wpSelectDir,
    'Connect to onetix', 'Enter the connector identity',
    'Generate a one-time setup code in the onetix dashboard and enter it here.');
  IdentityPage.Add('Setup code:', False);
  IdentityPage.Add('Connector name:', False);
  IdentityPage.Values[1] := 'onetix Store Connector';
  { Setup code uses mono when brand fonts loaded; otherwise UI fallback. }
  if BrandFontsLoaded then
    IdentityPage.Edits[0].Font.Name := '{#BrandFontMono}'
  else
    IdentityPage.Edits[0].Font.Name := ActiveBrandFont;
  IdentityPage.Edits[0].Font.Size := 11;
  StyleFont(IdentityPage.Edits[1].Font, 9, False);

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
  ZoneCameraCombo.Width := ScaleX(300);
  ZoneCameraCombo.Style := csDropDownList;
  ZoneCameraCombo.OnChange := @ZoneCameraChanged;
  RefreshFrameButton := TNewButton.Create(ZonePage);
  RefreshFrameButton.Parent := ZonePage.Surface;
  RefreshFrameButton.Caption := 'Refresh Frame';
  RefreshFrameButton.Left := ScaleX(310);
  RefreshFrameButton.Top := ScaleY(18);
  RefreshFrameButton.Width := ScaleX(170);
  RefreshFrameButton.OnClick := @RefreshZoneFrame;
  ZoneNameLabel := TNewStaticText.Create(ZonePage);
  ZoneNameLabel.Parent := ZonePage.Surface;
  ZoneNameLabel.Left := 0;
  ZoneNameLabel.Top := ScaleY(46);
  ZoneNameLabel.Caption := 'Zone name:';
  ZoneNameEdit := TNewEdit.Create(ZonePage);
  ZoneNameEdit.Parent := ZonePage.Surface;
  ZoneNameEdit.Left := 0;
  ZoneNameEdit.Top := ScaleY(64);
  ZoneNameEdit.Width := ScaleX(260);
  ZoneNameEdit.Text := '';
  ZoneTypeLabel := TNewStaticText.Create(ZonePage);
  ZoneTypeLabel.Parent := ZonePage.Surface;
  ZoneTypeLabel.Left := ScaleX(270);
  ZoneTypeLabel.Top := ScaleY(46);
  ZoneTypeLabel.Caption := 'Zone type:';
  ZoneTypeCombo := TNewComboBox.Create(ZonePage);
  ZoneTypeCombo.Parent := ZonePage.Surface;
  ZoneTypeCombo.Left := ScaleX(270);
  ZoneTypeCombo.Top := ScaleY(64);
  ZoneTypeCombo.Width := ScaleX(270);
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
  ZoneImage.Top := ScaleY(94);
  { Product reference requires a stable 480 x 362 frame viewport. }
  { Keep the visible frame at the requested physical pixel dimensions even
    when Windows display scaling is 125% or 150%. }
  ZoneImage.Width := 480;
  ZoneImage.Height := 362;
  ZoneImage.Stretch := True;
  ZoneImage.Cursor := crCross;
  ZoneImage.Visible := False;
  ZoneMouseTimerId := SetTimer(0, 0, 50, CreateCallback(@ZoneMouseTimerTick));
  ZoneList := TNewListBox.Create(ZonePage);
  SavedZonesLabel := TNewStaticText.Create(ZonePage);
  SavedZonesLabel.Parent := ZonePage.Surface;
  SavedZonesLabel.Left := ScaleX(380);
  SavedZonesLabel.Top := ScaleY(94);
  SavedZonesLabel.Caption := 'Zones';
  SavedZonesLabel.Font.Style := [fsBold];
  ZoneList.Parent := ZonePage.Surface;
  ZoneList.Left := ScaleX(380);
  ZoneList.Top := ScaleY(118);
  ZoneList.Width := ScaleX(130);
  ZoneList.Height := ScaleY(170);
  ZoneList.OnClick := @EditZoneClicked;
  ZoneList.Visible := False;

  for I := 0 to 7 do begin
    ZoneRowPanel[I] := TPanel.Create(ZonePage);
    ZoneRowPanel[I].Parent := ZonePage.Surface;
    ZoneRowPanel[I].SetBounds(ScaleX(380), ScaleY(118 + (I * 24)),
      ScaleX(172), ScaleY(22));
    ZoneRowPanel[I].BevelOuter := bvNone;
    ZoneRowPanel[I].Color := clWhite;
    ZoneRowPanel[I].Visible := False;
    ZoneRowLabel[I] := TNewStaticText.Create(ZonePage);
    ZoneRowLabel[I].Parent := ZoneRowPanel[I];
    ZoneRowLabel[I].SetBounds(ScaleX(6), ScaleY(3), ScaleX(118), ScaleY(16));
    ZoneRowLabel[I].AutoSize := False;
    ZoneRowLabel[I].Visible := False;
    ZoneRowEditButton[I] := TNewButton.Create(ZonePage);
    ZoneRowEditButton[I].Parent := ZoneRowPanel[I];
    ZoneRowEditButton[I].SetBounds(ScaleX(126), ScaleY(1), ScaleX(21), ScaleY(20));
    ZoneRowEditButton[I].Caption := Chr($E70F);
    ZoneRowEditButton[I].Font.Name := 'Segoe MDL2 Assets';
    ZoneRowEditButton[I].OnClick := @EditZoneClicked;
    ZoneRowEditButton[I].Visible := False;
    ZoneRowDeleteButton[I] := TNewButton.Create(ZonePage);
    ZoneRowDeleteButton[I].Parent := ZoneRowPanel[I];
    ZoneRowDeleteButton[I].SetBounds(ScaleX(149), ScaleY(1), ScaleX(21), ScaleY(20));
    ZoneRowDeleteButton[I].Caption := Chr($E74D);
    ZoneRowDeleteButton[I].Font.Name := 'Segoe MDL2 Assets';
    ZoneRowDeleteButton[I].OnClick := @DeleteZoneClicked;
    ZoneRowDeleteButton[I].Visible := False;
  end;

  UndoPointButton := TNewButton.Create(ZonePage);
  UndoPointButton.Parent := ZonePage.Surface;
  UndoPointButton.Caption := 'Undo Point';
  UndoPointButton.Left := 0;
  UndoPointButton.Top := ScaleY(464);
  UndoPointButton.Width := ScaleX(195);
  UndoPointButton.Height := ScaleY(24);
  UndoPointButton.OnClick := @UndoZonePoint;
  ClearPointsButton := TNewButton.Create(ZonePage);
  ClearPointsButton.Parent := ZonePage.Surface;
  ClearPointsButton.Caption := 'Clear Points';
  ClearPointsButton.Left := ScaleX(215);
  ClearPointsButton.Top := ScaleY(464);
  ClearPointsButton.Width := ScaleX(195);
  ClearPointsButton.Height := ScaleY(24);
  ClearPointsButton.OnClick := @ClearZonePoints;
  SaveZoneButton := TNewButton.Create(ZonePage);
  SaveZoneButton.Parent := ZonePage.Surface;
  SaveZoneButton.Caption := 'Save Zone';
  SaveZoneButton.Left := 0;
  SaveZoneButton.Left := ScaleX(380);
  SaveZoneButton.Top := ScaleY(298);
  SaveZoneButton.Width := ScaleX(172);
  SaveZoneButton.Height := ScaleY(26);
  SaveZoneButton.OnClick := @SaveZoneClicked;

  PointCountLabel := TNewStaticText.Create(ZonePage);
  PointCountLabel.Parent := ZonePage.Surface;
  PointCountLabel.Left := 0;
  PointCountLabel.Top := ScaleY(430);
  PointCountLabel.Width := ScaleX(480);
  PointCountLabel.Caption := 'Tip: Drag points to create or edit a zone.';
  PointCountLabel.Font.Color := $00666666;
  ZoneStatusLabel := TNewStaticText.Create(ZonePage);
  ZoneStatusLabel.Parent := ZonePage.Surface;
  ZoneStatusLabel.Left := 0;
  ZoneStatusLabel.Top := ScaleY(500);
  ZoneStatusLabel.Width := ScaleX(700);
  ZoneStatusLabel.Caption := 'Select a camera and click Refresh Frame.';

  StyleFont(ZoneCameraLabel.Font, 8, False);
  StyleFont(ZoneNameLabel.Font, 8, False);
  StyleFont(ZoneTypeLabel.Font, 8, False);
  StyleFont(SavedZonesLabel.Font, 8, False);
  StyleFont(PointCountLabel.Font, 8, False);
  StyleFont(ZoneStatusLabel.Font, 8, False);
  ZoneStatusLabel.Font.Color := $6C7178; { muted #78716C BGR }
  StyleFont(ZoneCameraCombo.Font, 9, False);
  StyleFont(ZoneTypeCombo.Font, 9, False);
  StyleFont(ZoneNameEdit.Font, 9, False);
  StyleFont(ZoneList.Font, 9, False);
  StyleFont(RefreshFrameButton.Font, 9, False);
  StyleFont(NewZoneButton.Font, 9, False);
  StyleFont(EditZoneButton.Font, 9, False);
  StyleFont(DeleteZoneButton.Font, 9, False);
  StyleFont(UndoPointButton.Font, 9, False);
  StyleFont(ClearPointsButton.Font, 9, False);
  StyleFont(SaveZoneButton.Font, 9, False);
  StyleFont(AddRtspButton.Font, 9, False);
  StyleFont(AddOnvifButton.Font, 9, False);
  StyleFont(AddVideoButton.Font, 9, False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if UpdateMode and
     ((PageID = IdentityPage.ID) or (PageID = SourcePage.ID) or
      (PageID = ZonePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if PreserveExistingConfig and
     ((PageID = IdentityPage.ID) or (PageID = SourcePage.ID) or
      (PageID = ZonePage.ID)) then begin
    Result := True;
    Exit;
  end;
  if (PageID = ZonePage.ID) and
     (SourceSetupSkipped or (AddedSourceCount = 0)) then
    Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = IdentityPage.ID then begin
    if Trim(IdentityPage.Values[0]) = '' then begin
      MsgBox('Setup code is required.', mbError, MB_OK);
      Result := False;
    end;
  end;
  if CurPageID = SourcePage.ID then begin
    if AddedSourceCount = 0 then begin
      { Nothing saved yet - Skip moves straight on, no source is forced. }
      SourceSetupSkipped := True;
      SelectedSourceType := -1;
    end else
      SourceSetupSkipped := False;
  end;
  if CurPageID = ZonePage.ID then begin
    if (ZonePointCount >= 3) and (Trim(ZoneNameEdit.Text) <> '') then
      SaveZoneClicked(SaveZoneButton);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  SrcCount: Integer;
  ServiceNote: String;
begin
  SuccessSummaryLabel.Visible := False;
  SuccessHeadingLabel.Visible := False;
  SuccessDescriptionLabel.Visible := False;
  SuccessIconLabel.Visible := False;
  GlobalSidebar.Visible := CurPageID = wpFinished;
  WizardForm.WizardSmallBitmapImage.Visible := not GlobalSidebar.Visible;
  if GlobalSidebar.Visible then GlobalSidebar.BringToFront;
  { Footer Cancel is intentionally omitted in the approved wizard.  Native
    title-bar Close remains functional. }
  WizardForm.CancelButton.Visible := False;
  WizardForm.BackButton.Caption := 'Back';

  if CurPageID = IdentityPage.ID then begin
    IdentitySidebar.BringToFront;
    WizardForm.PageNameLabel.Visible := False;
    WizardForm.PageDescriptionLabel.Visible := False;
    WizardForm.NextButton.Caption := 'Next';
    WizardForm.NextButton.Enabled := Trim(IdentityPage.Values[0]) <> ''
  end else if CurPageID = SourcePage.ID then begin
    SourceSidebar.BringToFront;
    WizardForm.NextButton.Enabled := True;
    WizardForm.PageNameLabel.Visible := True;
    WizardForm.PageDescriptionLabel.Visible := True;
    if PreserveExistingConfig then
      WizardForm.NextButton.Caption := 'Keep existing'
    else begin
      // Keep prior selection state when navigating Back; never force a type.
      SetSourcePanelVisible;
    end;
  end else if CurPageID = ZonePage.ID then begin
    ZoneSidebar.BringToFront;
    WizardForm.NextButton.Enabled := True;
    WizardForm.PageNameLabel.Visible := True;
    WizardForm.PageDescriptionLabel.Visible := True;
    if ZoneCameraCombo.Items.Count <> AddedSourceCount then begin
      PopulateZoneCameras;
      ZoneCameraChanged(ZoneCameraCombo);
    end else
      RebuildZoneList;
    if (ZoneCameraCombo.ItemIndex >= 0) and (not ZoneFrameReady) then
      RefreshZoneFrame(RefreshFrameButton);
    if SavedZoneCount > 0 then
      WizardForm.NextButton.Caption := 'Install'
    else
      WizardForm.NextButton.Caption := 'Skip';
  end else if CurPageID = wpReady then begin
    WizardForm.NextButton.Enabled := True;
    WizardForm.NextButton.Caption := 'Install';
    WizardForm.ReadyLabel.Caption :=
      'Click Install to install ONETIX Local Connector with the settings you entered.';
  end else if CurPageID = wpFinished then begin
    WizardForm.NextButton.Enabled := True;
    WizardForm.NextButton.Caption := 'Finish';
    WizardForm.PageNameLabel.Visible := False;
    WizardForm.PageDescriptionLabel.Visible := False;
    WizardForm.FinishedHeadingLabel.Visible := False;
    WizardForm.FinishedLabel.Visible := False;
    SrcCount := ActiveSourceCount;
    if ExistingService then
      ServiceNote := 'Connector service is running'
    else
      ServiceNote := 'Connector service installed';
    SuccessSummaryLabel.Caption :=
      'Summary' + #13#10#13#10 +
      Chr(10003) + '   Setup Code                         Success' + #13#10#13#10 +
      Chr(10003) + '   Sources                              ' + IntToStr(SrcCount) +
        ' source(s) added' + #13#10#13#10 +
      Chr(10003) + '   Detection Zones                 ' + IntToStr(SavedZoneCount) +
        ' zone(s) configured' + #13#10#13#10 +
      Chr(10003) + '   Connector Service              ' + ServiceNote + #13#10#13#10 +
      'Click Finish to exit Setup.';
    SuccessSummaryLabel.Visible := True;
    SuccessHeadingLabel.Visible := True;
    SuccessDescriptionLabel.Visible := True;
    SuccessIconLabel.Visible := True;
    GlobalSidebar.BringToFront;
    SuccessSummaryLabel.BringToFront;
    SuccessHeadingLabel.BringToFront;
    SuccessDescriptionLabel.BringToFront;
    SuccessIconLabel.BringToFront;
  end else begin
    WizardForm.NextButton.Enabled := True;
    WizardForm.PageNameLabel.Visible := True;
    WizardForm.PageDescriptionLabel.Visible := True;
    WizardForm.NextButton.Caption := 'Next';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, UpdatePath, MediaPath, Json, SourcesJson, ItemJson,
    PendingZonesJson, ReferencePath: String;
  I: Integer;
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
    for I := 0 to AddedSourceCount - 1 do begin
      if AddedSourceKind[I] = 0 then
        ItemJson := '{"name":"Camera ' + IntToStr(I + 1) +
          '","rtsp_url":"' + JsonEscape(Trim(AddedSourceRtsp[I])) + '"}'
      else if AddedSourceKind[I] = 1 then
        ItemJson := '{"name":"ONVIF Camera ' + IntToStr(I + 1) +
          '","onvif_host":"' + JsonEscape(Trim(AddedSourceHost[I])) +
          '","onvif_port":' + IntToStr(StrToIntDef(Trim(AddedSourcePort[I]), 80)) +
          ',"onvif_user":"' + JsonEscape(Trim(AddedSourceUser[I])) +
          '","onvif_pass":"' + JsonEscape(AddedSourcePass[I]) + '"}'
      else begin
        MediaPath := ExpandConstant('{commonappdata}\ONEVO\Connector\media\installer-video-' +
          IntToStr(I + 1) + '.mp4');
        if not CopyFile(AddedSourceMp4[I], MediaPath, False) then
          RaiseException('Could not copy MP4 video ' + IntToStr(I + 1) + '.');
        ItemJson := '{"name":"Local Video ' + IntToStr(I + 1) +
          '","source_file":"' + JsonEscape(MediaPath) + '","loop":true}';
      end;
      if SourcesJson <> '' then SourcesJson := SourcesJson + ',';
      SourcesJson := SourcesJson + ItemJson;
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
    if SourceSetupSkipped or (SourcesJson = '') then Exit;
    Json := '{"sources":[' + SourcesJson + ']}' + #13#10;
    SaveStringToFile(UpdatePath, Json, False);
    Exit;
  end;

  Json := '{' + #13#10 +
    '  "setup_complete": false,' + #13#10 +
    '  "setup_code": "' + JsonEscape(Trim(IdentityPage.Values[0])) + '",' + #13#10 +
    '  "connector_name": "ONETIX Store Connector",' + #13#10 +
    '  "sources": [' + SourcesJson + '],' + #13#10 +
    '  "pending_zones": [' + PendingZonesJson + ']' + #13#10 +
    '}' + #13#10;
  SaveStringToFile(ConfigPath, Json, False);
end;
