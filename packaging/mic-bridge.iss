; 免管理员（per-user）Windows 安装包（Inno Setup 6/7），由 packaging\build_installer.ps1 调用：
;   ISCC.exe /DAppVersion=0.7.0 packaging\mic-bridge.iss
;
; 与 installer\installer.iss（v0.7.0 的 admin 版，装到 Program Files）并存，互不干扰：
;   * 本脚本 PrivilegesRequired=lowest + {autopf} → %LOCALAPPDATA%\Programs\mic-bridge，
;     全程不弹 UAC；AppId 与 admin 版不同，不会把对方"升级"掉。
;   * 开机自启沿用 v0.7.0 的做法：只在「启动」文件夹放一个快捷方式（{userstartup}），
;     不写 HKCU\...\Run、不注册计划任务/服务 —— 与 installer.iss 同一种机制，避免双自启。
;     v0.7.0 的 pc_receiver.py 没有 --login 参数，因此快捷方式不带任何参数（无窗口进托盘）。
;   * 卸载由 Inno 自动登记到"应用和功能"，并自动移除上面那个启动快捷方式。

#ifndef AppVersion
  #define AppVersion "0.7.1"
#endif

#define AppName "旧平板麦克风桥（当前用户）"
#define AppPub "jiushouji-yuyin-gaizao"
#define AppExe "mic-bridge-receiver.exe"

[Setup]
; AppId 固定不变：本安装器的升级能识别为同一个应用，也不会和 admin 版（8E2F1C7A…）混淆
AppId={{8F1B7C24-5E3A-4C7B-9A0D-3E2B6F14C8A1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPub}
; PrivilegesRequired=lowest 时 {autopf} = {localappdata}\Programs，per-user、免 UAC
DefaultDirName={autopf}\mic-bridge
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
OutputDir=..\dist\windows
OutputBaseFilename=mic-bridge-setup-peruser-{#AppVersion}
SetupIconFile=mic-bridge.ico
UninstallDisplayIcon={app}\mic-bridge.ico
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AllowNoIcons=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=no
; v0.7.0 用端口 5005 的 socket 探测单实例（没有命名互斥），所以这里不设 AppMutex
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoCompany={#AppPub}
VersionInfoDescription=旧平板麦克风桥（当前用户安装，免管理员）

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："
Name: "autostart"; Description: "登录 Windows 时自动启动（静默进入托盘，之后可在托盘右键退出）"; GroupDescription: "开机自启："

[Files]
; onedir 产物整目录拷过去（不含临时解包，杀软误报更少）
Source: "..\dist\windows\Jiushouji-Mic\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "mic-bridge.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\release\mic-bridge-0.5.0.apk"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\mic-bridge.ico"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; \
    IconFilename: "{app}\mic-bridge.ico"; Tasks: desktopicon
; 与 installer.iss 相同的自启机制：当前用户「启动」文件夹里的快捷方式（卸载时由 Inno 移除）
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; \
    IconFilename: "{app}\mic-bridge.ico"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即启动接收端（托盘常驻）"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; v0.7.0 把日志写在 %LOCALAPPDATA%\mic-bridge（与安装目录分开），这里清掉日志，不动用户其它数据
Type: files; Name: "{localappdata}\mic-bridge\receiver.log"
Type: files; Name: "{localappdata}\mic-bridge\receiver.log.old"
Type: dirifempty; Name: "{localappdata}\mic-bridge"
Type: dirifempty; Name: "{app}"

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
