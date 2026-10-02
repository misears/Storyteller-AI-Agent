#define AppName "Storyteller AI"

[Setup]
AppId={{B5588F29-7E23-4895-ADE1-A2E170038D43}
AppName={#AppName}
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\StorytellerAI
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=output
OutputBaseFilename=StorytellerAI-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName}
CloseApplications=no
SetupLogging=yes
DiskSpanning=no

[Files]
Source: "output\StorytellerAI-Install\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "model4b"; Description: "Balanced: Qwen3 4B (about 2.5 GB download; recommended for most PCs)"; GroupDescription: "Local AI model:"; Flags: exclusive
Name: "model8b"; Description: "Higher quality: Qwen3 8B (about 5.2 GB download; 8 GB GPU memory recommended)"; GroupDescription: "Local AI model:"; Flags: exclusive unchecked
Name: "modelsmall"; Description: "Low memory: Qwen3 1.7B (about 1.4 GB download; simpler narration)"; GroupDescription: "Local AI model:"; Flags: exclusive unchecked

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Launch.ps1"""; Description: "Open Storyteller AI"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\.venv"
Type: files; Name: "{userdesktop}\Storyteller AI.lnk"
Type: files; Name: "{userprograms}\Storyteller AI\Storyteller AI.lnk"
Type: files; Name: "{userprograms}\Storyteller AI\Repair Storyteller AI.lnk"
Type: dirifempty; Name: "{userprograms}\Storyteller AI"

[Code]
var
  DependencyPage: TOutputMsgMemoWizardPage;

procedure InitializeWizard;
var
  ReportPath, Parameters: String;
  Report: AnsiString;
  ExitCode: Integer;
begin
  ExtractTemporaryFile('Install.ps1');
  ExtractTemporaryFile('Setup.Common.ps1');
  ReportPath := ExpandConstant('{tmp}\dependency-report.txt');
  Parameters := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\Install.ps1') +
    '" -CheckOnly -ReportPath "' + ReportPath + '"';
  DependencyPage := CreateOutputMsgMemoPage(wpWelcome, 'Computer and dependency check',
    'Review what will be installed before continuing.',
    'Setup installs Python and the application packages for you. Missing AI software and models are handled automatically.', '');
  if Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Parameters, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    if (ExitCode = 0) and LoadStringFromFile(ReportPath, Report) then
      DependencyPage.RichEditViewer.Text := UTF8Decode(Report)
    else
      DependencyPage.RichEditViewer.Text := 'The computer check failed. Cancel setup and ask your support person to check Windows PowerShell and Windows Management Instrumentation.';
  end
  else
    DependencyPage.RichEditViewer.Text := 'Windows PowerShell could not be started. Cancel setup and contact your support person.';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Available, Total: Int64;
begin
  Result := '';
  if GetSpaceOnDisk64(ExpandConstant('{app}'), Available, Total) then
    if Available < Int64(20) * 1024 * 1024 * 1024 then
      Result := 'Please free at least 20 GB on the installation drive, then retry.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Model, Parameters: String;
  ExitCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    Model := 'qwen3:4b';
    if WizardIsTaskSelected('model8b') then Model := 'qwen3:8b';
    if WizardIsTaskSelected('modelsmall') then Model := 'qwen3:1.7b';
    Parameters := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\Install.ps1') +
      '" -InstallRoot "' + ExpandConstant('{app}') + '" -Model ' + Model + ' -SkipConfirmation';
    if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Parameters,
      ExpandConstant('{app}'), SW_SHOWNORMAL, ewWaitUntilTerminated, ExitCode) then
      RaiseException('Setup could not start the dependency installer.');
    if ExitCode <> 0 then
      RaiseException('The software or AI model setup did not finish. Read the setup log in ' +
        ExpandConstant('{localappdata}\StorytellerAI\logs') +
        '. Run Install.ps1 again from the installed folder or rerun this installer to retry.');
  end;
end;
