; mic-bridge 安装脚本 (Inno Setup 7)
#define AppName "旧平板麦克风桥"
#define AppVer "0.6.0"
#define AppExe "mic-bridge-receiver.exe"

[Setup]
AppId={{8E2F1C7A-6B4D-4A2E-9C31-5D7A0B2E4F61}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=mic-bridge
DefaultDirName={autopf}\mic-bridge
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=installer
OutputBaseFilename=mic-bridge-setup-{#AppVer}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
ShowLanguageDialog=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked
Name: "firewall"; Description: "放行 Windows 防火墙 TCP 5005（WiFi 模式需要）"; GroupDescription: "网络："

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "release\mic-bridge-0.5.0.apk"; DestDir: "{app}"; Flags: ignoreversion
Source: "启动USB接收端.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "启动WiFi接收端.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\mic-bridge 麦克风"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\使用说明"; Filename: "{app}\使用说明.txt"
Name: "{group}\诊断：USB 模式控制台"; Filename: "{app}\启动USB接收端.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\mic-bridge 麦克风"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""mic-bridge TCP 5005"" dir=in action=allow protocol=TCP localport=5005"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#AppExe}"; Description: "立即启动接收端（托盘常驻）"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""mic-bridge TCP 5005"""; Flags: runhidden; RunOnceId: "DelFirewallRule"

[Code]
function VBCableInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\VBAudioVACMME');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not VBCableInstalled then
    begin
      if MsgBox('没有检测到 VB-Cable 虚拟声卡。' + #13#10 +
                '它是本方案的必要组件，授权不允许随安装包分发，需要单独安装。' + #13#10#13#10 +
                '现在打开官方下载页面？', mbConfirmation, MB_YESNO) = IDYES then
        ShellExec('open', 'https://vb-audio.com/Cable/', '', '', SW_SHOWNORMAL, ewNoWait, ErrCode);
    end;
  end;
end;
