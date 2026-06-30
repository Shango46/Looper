#define MyAppName "Looper"
#define MyAppVersion "1.0"
#define MyAppPublisher "Looper"
#define MyAppURL "https://github.com/Shango46/Looper"
#define MyAppExeName "launcher.pyw"

[Setup]
AppId={{A7B3C924-D581-4E2F-9A1C-8F05E3D62B47}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Looper
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; No UAC elevation — installs entirely in user profile
PrivilegesRequired=lowest
OutputBaseFilename=LooperInstaller
OutputDir=Output
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\looper.ico
UninstallDisplayIcon={app}\looper.ico
DisableProgramGroupPage=no
; Don't create a Start Menu group page — we handle icons manually
DisableDirPage=no
; Show license if present
; LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ── Application source ────────────────────────────────────────────────────────
Source: "..\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\setup\*"; DestDir: "{app}\setup"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\run.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\agents.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\skills.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion

; ── Installer assets ──────────────────────────────────────────────────────────
Source: "assets\launcher.pyw"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\post_install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\looper.ico"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; Remove old venv on reinstall so packages are always fresh
Type: filesandordirs; Name: "{app}\.venv"

[Icons]
; Start Menu shortcut
Name: "{group}\Looper"; \
    Filename: "{app}\.venv\Scripts\pythonw.exe"; \
    Parameters: """{app}\launcher.pyw"""; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\looper.ico"

; Desktop shortcut (optional, controlled by Tasks)
Name: "{userdesktop}\Looper"; \
    Filename: "{app}\.venv\Scripts\pythonw.exe"; \
    Parameters: """{app}\launcher.pyw"""; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\looper.ico"; \
    Tasks: desktopicon

; Uninstall entry in Start Menu
Name: "{group}\Uninstall Looper"; \
    Filename: "{uninstallexe}"

[Run]
; Offer "Launch Looper now" on the final wizard page
Filename: "{app}\.venv\Scripts\pythonw.exe"; \
    Parameters: """{app}\launcher.pyw"""; \
    Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    WorkingDir: "{app}"; \
    Flags: postinstall nowait skipifsilent

[Code]
var
  ProgressPage: TOutputProgressWizardPage;

procedure InitializeWizard;
begin
  ProgressPage := CreateOutputProgressPage(
    'Setting up Looper',
    'Please wait while dependencies are installed...'
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  PSArgs: String;
  LogFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    ProgressPage.SetText('Installing Python, Git, and packages...', '');
    ProgressPage.SetProgress(0, 100);
    ProgressPage.Show;
    try
      LogFile := ExpandConstant('{localappdata}\Looper\post_install.log');
      PSArgs := '-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden' +
                ' -File "' + ExpandConstant('{app}\post_install.ps1') + '"' +
                ' -InstallDir "' + ExpandConstant('{app}') + '"' +
                ' *> "' + LogFile + '"';

      ProgressPage.SetProgress(10, 100);

      if not Exec('powershell.exe', PSArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      begin
        MsgBox(
          'Setup script could not be launched.' + #13#10 +
          'Please run post_install.ps1 manually from: ' + ExpandConstant('{app}'),
          mbError, MB_OK
        );
      end
      else if ResultCode <> 0 then
      begin
        MsgBox(
          'Dependency installation completed with warnings (exit code ' +
          IntToStr(ResultCode) + ').' + #13#10#13#10 +
          'Looper may still work correctly. If you have issues, check:' + #13#10 +
          LogFile,
          mbInformation, MB_OK
        );
      end;

      ProgressPage.SetProgress(100, 100);
    finally
      ProgressPage.Hide;
    end;
  end;
end;
