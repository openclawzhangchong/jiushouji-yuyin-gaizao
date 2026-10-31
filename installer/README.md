# 安装包（Inno Setup 7）

把接收端打成一个**纯中文向导**的 Windows 安装包：装到 `Program Files\mic-bridge`，
带开始菜单/桌面快捷方式、可选防火墙规则、标准卸载程序，并在安装完成时检测 VB-Cable。

## 为什么不能把 VB-Cable 打进安装包

VB-Cable 的 `readme.txt` 写得很明确：

> It is **not allowed to integrate the VB-CABLE package in another software installation
> procedure** without Author agreement.

所以安装包**只检测、不内嵌**：查驱动服务键
`HKLM\SYSTEM\CurrentControlSet\Services\VBAudioVACMME`，缺失时弹窗并打开
<https://vb-audio.com/Cable/> 让用户单独安装。别为了"省一步"把它塞进来。

adb 不一样：platform-tools 是 Apache 2.0，可以随 EXE 分发（当前内置在 EXE 里）。

## 构建

前置：Inno Setup 7（官方自带 `Languages\ChineseSimplified.isl`，**不需要**额外语言包）。

```powershell
# 1) 先在仓库根目录打 EXE（见根 README「怎么打出这个 EXE」）
#    需要把 Android SDK 的 platform-tools 三个文件放到仓库根的 platform-tools\：
#      adb.exe  AdbWinApi.dll  AdbWinUsbApi.dll
#    v0.6.0 起接收端是托盘常驻，不带控制台窗口；v0.7.0 起带品牌图标：
pyinstaller --onefile --noconsole --name mic-bridge-receiver --icon mic-bridge.ico `
  --add-data "$PWD\release\mic-bridge-0.5.0.apk;." `
  --add-data "$PWD\platform-tools;platform-tools" pc_receiver.py

# 2) 打安装包
& "C:\Program Files\Inno Setup 7\ISCC.exe" installer\installer.iss
# 产物：dist\mic-bridge-setup-0.7.0.exe
```

图标由仓库根 `gen_icon.py` 生成（Pillow 程序化绘制 16~256px 的 `mic-bridge.ico`，改设计重跑即可）。
快捷方式的 `IconFilename` 必须指向独立 .ico——指向"EXE,0"会被 Windows 图标缓存坑住（v0.7.0 踩过）。

## 安装包做了什么

| 项 | 说明 |
|---|---|
| 安装目录 | `{autopf}\mic-bridge`（默认 `C:\Program Files\mic-bridge`） |
| 文件 | 接收端 EXE（托盘常驻无窗口）、平板 APK、USB/WiFi 两个诊断脚本、使用说明 |
| 快捷方式 | 开始菜单「mic-bridge 麦克风」+ 诊断入口；桌面快捷方式可选；**开机自启（当前用户）默认勾选**（v0.7.0） |
| 防火墙 | 可选任务，`netsh advfirewall` 放行入站 TCP 5005；卸载时删除 |
| VB-Cable | 安装完成时检测，缺失则提示并打开官网（不内嵌） |
| 完成页 | postinstall 直接启动接收端（托盘出现，无残留 pause 窗口）；「查看使用说明」是可选复选框 |
| 卸载 | 标准 `unins000.exe`，已实测能清空安装目录 |

## 已验证（v0.6.0）

- 静默装/卸 3 轮（Git Bash 会把 `/VERYSILENT` 转成本地路径，**必须用 PowerShell
  `Start-Process -ArgumentList` 传参**）：退出码 0、装出 EXE 与 dist 哈希一致、目录删净、
  防火墙规则随装随删。
- 修复：`isreadm` 标志在静默安装时会弹「ShellExecuteEx 失败 2147500033」错误窗
  （用户屏幕被卡住），改用 `[Run]` + `postinstall skipifsilent shellexec` 后静默安装零弹窗。
- 重复启动：第二个实例弹「已经在运行」MessageBox 后退出，不会假死。
- 安装包未签名，首次运行会有 SmartScreen「未知发布者」提示，这是预期行为。
