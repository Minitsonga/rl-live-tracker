; Inno Setup script — requires PyInstaller output in dist\RLLiveTracker\
#define MyAppName "RL Live Tracker"
#define MyAppPublisher "Minitsonga"
#define MyAppURL "https://github.com/Minitsonga/rl-live-tracker"
#define MyAppExeName "RLLiveTracker.exe"

; Pass /DMyAppVersion=1.0.0.2 from build.ps1 (dots only for Inno)
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0.2"
#endif

[Setup]
AppId={{A7B4E2C1-9F3D-4A8B-RLT-TRACKER01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\RLLiveTracker
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=RLLiveTracker-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "launch"; Description: "Launch RL Live Tracker after install"; GroupDescription: "Options:"; Flags: checked unchecked
Name: "autostart"; Description: "Start with Windows"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\dist\RLLiveTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; Tasks: launch

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RLLiveTracker"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue
