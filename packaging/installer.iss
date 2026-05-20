; Inno Setup script — requires PyInstaller output in dist\RLLiveTracker\
#define MyAppName "RL Live Tracker"
#define MyAppPublisher "Minitsonga"
#define MyAppURL "https://github.com/Minitsonga/rl-live-tracker"
#define MyAppExeName "RLLiveTracker.exe"

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{A7B4E2C1-9F3D-4A8B-RLT-TRACKER01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\RLLiveTracker
UsePreviousAppDir=no
DirExistsWarning=no
DisableDirPage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=RL-LiveTracker-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
AlwaysUsePersonalGroup=yes
SetupIconFile=..\packaging\branding\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
english.DirBrowseHint=Type a full path in the field below (you can include a new folder name). The installer will create missing folders. The Browse button only picks existing folders.
french.DirBrowseHint=Saisissez un chemin complet ci-dessous (vous pouvez inclure un nouveau dossier). L'installateur créera les dossiers manquants. Parcourir ne choisit que des dossiers existants.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "launch"; Description: "Launch RL Live Tracker after install"; GroupDescription: "Options:"
Name: "autostart"; Description: "Start with Windows"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\dist\RLLiveTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; Tasks: launch

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RLLiveTracker"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

[Code]
procedure DirBrowseButtonClick(Sender: TObject);
var
  Dir: string;
begin
  Dir := WizardForm.DirEdit.Text;
  if BrowseForFolder('Select installation folder', Dir, True) then
    WizardForm.DirEdit.Text := Dir;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir: string;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Dir := Trim(WizardForm.DirEdit.Text);
    if Dir = '' then
    begin
      MsgBox('Please choose an installation folder.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not DirExists(Dir) then
    begin
      if not CreateDir(Dir) then
      begin
        MsgBox(
          'Could not create the folder:' + #13#10 + Dir + #13#10#13#10 +
          'Try another location or type a path that includes a new folder name in the text field.',
          mbError, MB_OK);
        Result := False;
      end;
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectDir then
    WizardForm.StatusLabel.Caption := ExpandConstant('{cm:DirBrowseHint}');
end;
