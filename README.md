# 旧平板 → Windows 语音输入麦克风（mic-bridge）

把一台 **MTK MT6582 / Android 5.1 (API 21)** 的旧平板变成 Windows 能用的**真麦克风**：
平板自己采麦，经 **USB（不是 WiFi）** 推到电脑，电脑把流灌进 VB-Cable 虚拟声卡，
Windows 就多出一个录音设备 **`CABLE Output (VB-Audio Virtual Cable)`**，
任何程序（微信/QQ 语音、网页语音输入、Win+H 语音听写、CapsWriter）都能选它当输入设备。

**一句话：不用买 USB 麦克风，不用改任何上层软件，一根数据线搞定。**

当前状态：**已做完并在真机验收通过**（2026-10-31，平板端 `release/mic-bridge-0.5.0.apk` 已装机，
接收端 `v0.7.0`）。识别验收原文逐字命中，数字见 [`docs/验收记录.md`](docs/验收记录.md)。

---

## v0.7.0 更新（2026-10-31）：实体麦自动兜底 + 新品牌图标

1. **实体麦自动兜底**：平板链路 10 秒收不到数据（没电/拔线/被杀），接收端自动挑一个
   **有信号的实体麦克风**继续往 CABLE 灌——语音输入不会突然哑掉，所有上层软件无感知；
   平板数据一恢复 2 秒内自动切回。选麦是**实测探测**：逐个开 0.4 秒量 RMS，
   空麦口/被静音的设备直接跳过（本机实测：Realtek 麦口 RMS=0 被跳过，摄像头麦 RMS=48 中选）。
   托盘新增**黄灯**=兜底中。`--no-fallback` 可关，`--fallback-mic 关键字` 可指定，`--fallback-after` 调时限。
2. **品牌图标**：`gen_icon.py` 用 Pillow 程序化绘制（深色圆角底+青绿麦克风+声波+右下角琥珀「zc」徽），
   一次产出 16~256px 的 `mic-bridge.ico`，EXE/快捷方式/安装包统一使用；托盘图标同步换成麦克风剪影四态色。
3. 安装包随带 `mic-bridge.ico`，开始菜单/桌面快捷方式 `IconFilename` 指向它（绕开 Windows 图标缓存坑）。

托盘四态（v0.7.0 起）：🟢推流中 · 🟡实体麦兜底中 · ⚪等待平板 · 🔴故障。

验收数字（假客户端灌 800Hz 正弦模拟平板，全程不动真机）：
断流 10s 触发兜底两次（13:41:34 / 13:42:24）；兜底期间 CABLE 录到房间声 peak=80、托盘黄像素 18；
正弦恢复两次自动切回（13:42:02 / 13:42:54），CABLE 正弦 peak=9005、800Hz 频带能量比 49 倍、托盘回绿。
详见 [`docs/接收端0.7.0兜底.md`](docs/接收端0.7.0兜底.md)。

---

## v0.6.0 更新（2026-10-30 深夜）：接收端托盘常驻，黑色窗口退场

平板端仍是 **0.5.0**，这一版只动 Windows 接收端的形态。

1. **系统托盘常驻，无窗口**：EXE 改为 windowless，不再弹黑色控制台。托盘图标颜色即状态——
   **绿=推流中、灰=等平板连接、红=故障**（悬停看原因），悬停一句话详情（链路/模式/速率）。
2. **右键菜单**：状态行 / **切换 USB⇄WiFi**（重启换链路）/ **显示诊断日志**（弹实时滚动窗口）/ 退出。
   切换已真机实测：USB→WiFi→USB 各重启一次，平板每次自动重连，稳定 32KB/s、丢块个位数。
3. **日志落盘**：`%LOCALAPPDATA%\mic-bridge\receiver.log`（超 1MB 自动换 `.old`）。
   重复启动不再静默假死——弹"已在运行"提示；端口被占、没装 VB-Cable 都有可见反馈（红盘/弹窗）。
4. **安装包 0.6.0**：postinstall 直接启动接收端（无残留 pause 窗口），开始菜单/桌面图标直指 EXE；
   两个 bat 保留作诊断入口。修复 `isreadme` 标志在静默安装时弹 ShellExecuteEx 错误窗的问题
   （改 postinstall 可选复选框）。

验收数字：3 轮静默装/卸全过（退出码 0、装出 EXE 与 dist 哈希一致、目录删净、防火墙规则随装随删）；
端到端：平板说话 App 端峰值 2320，同窗 CABLE Output 录到峰值 1965。

---

## v0.5.1 更新（2026-10-30 晚）：接收端修多连接 + 内置 adb + 中文安装包

平板端仍是 **0.5.0**，这一版只动 Windows 接收端和分发方式。

1. **修多连接混流**：接收端现在只把**最新连接**当音源，其它连接只排空、不混音，
   但**所有连接都回心跳**。修复前曾出现两条 32KB/s 流叠成 64KB/s、丢块约 40/s、
   连接数暴涨到 50 次/秒；修复后 USB 稳定在 32KB/s、1 条连接、欠载 0。
2. **内置 adb**：EXE 里打包 platform-tools，首次运行解到
   `%LOCALAPPDATA%\mic-bridge\platform-tools`。不再依赖 PATH / WinGet / Android SDK，
   也不会因为"找不到 adb"静默退化成纯 WiFi（原 EXE 的坑）。
3. **中文安装包**：`mic-bridge-setup-0.5.1.exe`，Inno Setup 7 + 官方简体中文语言文件，
   安装时检测 VB-Cable、可选防火墙规则、开始菜单/桌面快捷方式、标准卸载。
   VB-Cable 因授权限制**只检测不内嵌**。

完整的原因、修法和实测数字见 [`docs/接收端0.5.1与安装包.md`](docs/接收端0.5.1与安装包.md)。

---

## 为什么非走这条路（先读这段，否则会想错）

这台 Windows 主机**声卡没有任何录音输入**（无 mic、无 line-in、无 Stereo Mix）。
所以这些"看起来更简单"的方案全部不可行，别再试：

| 方案 | 为什么不行 |
|---|---|
| 3.5mm 音频线把手机接到电脑 | 电脑声卡根本没有 line-in 端点 |
| 开启"立体声混音 (Stereo Mix)" | Stereo Mix 本身就是 capture 端点，同样不存在 |
| 平板当蓝牙 HFP 耳机给电脑当麦 | Android 只能做 HFP 的 AG（话机）角色，做不了 HF（耳麦）角色 |
| 平板做 USB Audio Class 设备（插上就是麦克风） | 需要 kernel gadget 支持 + root，stock Android 5.1 没有 |

**结论：Windows 侧必须有一个虚拟声卡驱动，没有第二条路。** 这就是 VB-Cable 的来源。

---

## 架构

```
┌── 平板 b906 (Android 5.1) ──┐                ┌────────── Windows 11 ──────────┐
│ MainActivity                │                │ pc_receiver.py                 │
│  └ Bridge 线程              │   USB 数据线   │  └ TCP 监听 127.0.0.1:5005     │
│     AudioRecord             │  adb reverse   │  └ 弹性缓冲（目标水位 60ms）   │
│     16000Hz/mono/PCM16      │◄──────────────►│  └ sounddevice 播进 CABLE Input│
│     20ms=1280B 分包         │  TCP:5005      │                                 │
│     PARTIAL_WAKE_LOCK       │                │ CABLE Input(渲染) ──► CABLE Output(录音)
└─────────────────────────────┘                │                                  │  ▼
                                               │                     任意程序的麦克风输入
                                               └──────────────────────────────────┘
```

App 只连平板**自己的** `127.0.0.1:5005`；`adb reverse tcp:5005 tcp:5005` 把这个口搬到电脑上。
平板不需要开监听端口，也不需要和电脑在同一网段。

---

## 新电脑部署（两步半）

最省事：直接装 `mic-bridge-setup-0.7.0.exe`（内置 adb 与平板 APK，装完托盘常驻无窗口，
默认勾选开机自启）。
想从源码起，按下面的步骤：

```powershell
# 1) 装运行时依赖（adb + VB-Cable + Python 虚拟环境）。默认是演练，加 -Go 才动手
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go

#    如果这台机器还要重新编译 APK（不只使用），再加构建链（约 310MB）
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go -WithBuild

# 2) 装 App 并起流
adb install -r release\mic-bridge-0.5.0.apk
python pc_receiver.py            # 常驻；或双击「启动接收端.bat」
adb shell am start -n com.zcstudy.micbridge/.MainActivity --ez auto true
```

**半步 = 只有这三下必须人做，任何脚本都替代不了**（Android 安全模型决定的）：

1. 平板 `设置 → 开发者选项 → USB 调试` 打开（没有开发者选项就进 `设置 → 关于平板`，连点"版本号"7 次）；
2. 插上数据线（**必须是能传数据的线**，纯充电线不行）；
3. 平板屏幕上弹「允许 USB 调试？」时点 **允许**，勾上"一律允许这台计算机"。

然后建议手动把 `CABLE Output` 设成 Windows 默认录音设备（`设置 → 系统 → 声音 → 输入`）。
设成默认之后 **CapsWriter-Offline 不用改一行代码**就能用 —— 它取的就是系统默认输入设备
（`core/client/audio/stream.py:115` 用 `sd.query_devices(kind='input')`）。

---

## 文件清单

| 文件 | 作用 |
|---|---|
| `app/AndroidManifest.xml` | 权限 RECORD_AUDIO / INTERNET / WAKE_LOCK / READ_EXTERNAL_STORAGE，minSdk 21 |
| `app/src/com/zcstudy/micbridge/Bridge.java` | 采麦 → 20ms 分包 → TCP 推流；退避重连；`PARTIAL_WAKE_LOCK`；每 5 秒 logcat 心跳；标定音注入 |
| `app/src/com/zcstudy/micbridge/MainActivity.java` | 纯代码搭 UI（不依赖布局 XML，绕开 aapt2 丢 theme 的坑）：大开关 + 28 段电平 + 状态行 + 标定音 + **外放自测** + 音源切换；支持 intent 无人值守 |
| `build.sh` | 无 Gradle / 无 Android Studio 出包链：`aapt2 → javac → d8 → zipalign → apksigner` |
| `pc_receiver.py` | `adb reverse` 管理 + TCP 收流 + 弹性缓冲 + 播进 CABLE Input + 状态打印 + 可选同时录音（`--record`） |
| `启动接收端.bat` | 双击启动接收端 |
| `setup_windows.ps1` | 新机一键搭环境（默认 DRY-RUN，`-Go` 才装，`-WithBuild` 附带构建链） |
| `run_selftest.sh` | 无人值守回归：平板自己外放已知音频、自己听回来、PC 录下、出数字 |
| `acoustic_probe.py` / `look.py` | 声学回环与包络/频谱分析 |
| `spike/` | **丢弃型**验证脚本，结论已冻结在 `PLAN.md`，别当实现参考（见 `spike/README.md`） |
| `release/mic-bridge-0.5.0.apk` | 当前装机版本（20.9 KB，含签名） |
| `installer/` | 中文安装包脚本（Inno Setup 7）：`installer.iss`、启动脚本、使用说明 |
| `PLAN.md` | 决策与实测台账：每条结论带出处 |
| `AGENTS.md` | **给接手的 AI/程序员的硬约束与禁止事项，动手前先读这个** |
| `docs/验收记录.md` | 验收数字与原文 |

## 平板端操作

界面上只有四个控件：

- **开始送话 / 停止送话** —— 大按钮，开关上行推流
- **标定音 0.3s** —— 本地生成 1kHz 正弦**直接注入上行流、绕过麦克风**，用来量纯链路延迟
- **外放自测** —— 平板用外放播 `/sdcard/Music/demo.wav`（路径可用 intent 参数换），
  自己的麦克风再听进去，一次把"采麦→推流→虚拟麦→录音→ASR"整条链验完，不需要人说话
- **音源** —— 在 `VOICE_COMMUNICATION`（默认，沿用已验证配置）和 `VOICE_RECOGNITION` 之间切，
  用来对比 MTK 平台回声处理对音色的影响（详见下文「音源按钮是什么、什么时候需要切」）

### 音源按钮是什么、什么时候需要切

安卓给录音 App 提供的不是"一个麦克风"，而是几条**预设采音链路**——系统对声音的加工方式不同：

| 音源 | 系统做了什么 | 适合场景 |
|---|---|---|
| `VOICE_COMMUNICATION`（默认） | 按**通话**处理：回声消除、降噪、自动增益 | 微信/QQ 语音这类"对人说话"，能消掉平板外放漏进麦的声音 |
| `VOICE_RECOGNITION` | 按**给语音识别用**处理：不做通话降噪，频响平直、更原汁原味 | 听写/转写（Win+H、CapsWriter），或觉得默认音源"闷/小/忽大忽小"时 |

为什么要做成按钮：这两条链路在**不同芯片/厂商上表现差异很大**，MTK 老平板尤甚——
比如有的机型 VOICE_COMMUNICATION 会被降噪压得发闷、音量偏低，而 VOICE_RECOGNITION 反而干净响亮。
哪种好听没法靠猜，所以放在界面上现场切换对比，选听着最正常的那条；
**选完对电脑上所有软件都生效**，不需要改任何接收端/上层配置。

使用约定：

- **声音清楚响亮就别动它**，保持默认；只有音质不满意才切
- 点击切换会**重启采集**（正在送话时瞬间断一下再自动接上），日志里会记一条 `音源=…`
- 按钮只在上面两个音源间切换；代码里的 `srcName()` 还认 `MIC`（原始麦克风），
  但界面上切不到它——那是留给排查时对照用的，需要的话改 `switchSource()` 一行即可

无人值守（注意 `am` 的 `--ez` **只认 `true`/`false`**，写 `1` 会被解析成 false）：

```bash
adb shell am start -n com.zcstudy.micbridge/.MainActivity \
    --ez auto true --es act selftest --es demo /sdcard/Music/loop2.wav.off
```

## 已知未完成

- **端到端绝对延迟未实测**（只测了 Windows 段 143.9ms，总估 160–300ms）。
  要出准数需要平板与 PC 跨机时钟对齐，`adb shell date` 往返几百 ms，撑不起 ±30ms 结论。
- 熄屏只连续验了 **75 秒**，没跑 30 分钟 soak。
- **平板端开机自启 / 常驻防杀未做**：PC 端 v0.7.0 起安装器已带开机自启任务；
  平板 App 仍靠手点或 `am start`。要做接 `BOOT_COMPLETED`，
  并可用同设备已验证可行的 Device Owner / LockTask 方案（见上游仓库 `jiushouji-adb-apk2027`）。
- 音源两个档位没做正式 A/B 对比。

## 相关仓库

- [`openclawzhangchong/jiushouji-adb-apk2027`](https://github.com/openclawzhangchong/jiushouji-adb-apk2027) ——
  **这台平板的硬件评估与开发全过程记录**（含本仓库的前置结论）。
  麦克风/扬声器实测、adb 驱动排错、Kiosk 自启可行性、WebView 37 兼容性都在那边。
- `xiaole-ptt-android5-2027` —— 同设备上的语音对讲客户端，本仓库的采麦参数与出包链直接沿用它的成熟做法。

---

## 手机端不方便下载 APK？EXE 会自己装（2026-10-30 新增）

`mic-bridge-receiver.exe` 里**内置了同版本的 APK**。只要它检测到 adb 上有平板在线，就会：

1. `dumpsys package com.zcstudy.micbridge` 查已装版本；
2. **没装或版本旧** → 自动 `adb install -r`（平板上不需要浏览器/网盘/传文件）；
3. 装完再 `am start --ez auto true --es lan <本机局域网IP>` ——
   顺手把自己 IP 推给平板并开始送话，**连"在平板上手填 IP"都省了**。

三条保护：平板上的版本比内置的**更新**时不降级只提示；同版本跳过安装；
**平板正在推流时绝不动它**（不会因为"顺手升级"打断正在用的麦克风）。

```powershell
.\mic-bridge-receiver.exe --install-apk      # 只做一次安装+配网然后退出
.\mic-bridge-receiver.exe --no-auto-install  # 不希望它碰平板
.\mic-bridge-receiver.exe --adb D:\path\adb.exe   # adb 不在默认位置时指定
```

这套逻辑有个**不插设备也能跑**的测试：`python test_auto_install.py`
（造一个假 adb 转发脚本，把"没装过 / 同版本 / 平板版本更新"三种状态各验一遍并断言决策）。

### 怎么打出这个 EXE

```bash
# platform-tools\ 里放 adb.exe / AdbWinApi.dll / AdbWinUsbApi.dll（从 Android SDK 复制，已 gitignore）
pyinstaller --onefile --console --name mic-bridge-receiver \
    --add-data "<绝对路径>/release/mic-bridge-0.5.0.apk;." \
    --add-data "<绝对路径>/platform-tools;platform-tools" pc_receiver.py
```

产物约 **28 MB**（v0.5.0 是 21 MB，多出来的就是 adb）。

六个必须知道的坑（每条都踩过）：
- `--add-data` 的**源路径是相对 `--specpath` 解析的**，不是当前工作目录 → 一律写绝对路径，
  否则报 `Unable to find ...`。
- **目标 EXE 正在运行时 PyInstaller 会 `PermissionError` 且构建不中断**，
  于是你会拿着旧二进制以为是新的。判据只有产物**字节数 + sha256**。
- **内置 adb 不能直接从 `sys._MEIPASS` 跑**：onefile 退出会删临时目录，而 adb server 是常驻进程，
  下次启动时 server 还指着已删除的 `adb.exe`，表现成"莫名其妙的连不上"。
  必须先复制到固定目录（`%LOCALAPPDATA%\mic-bridge\platform-tools`）。
- **`--bind auto` 按"有没有设备在线"判断，不是"有没有 adb"**。内置 adb 之后后者恒真，
  纯 WiFi 那台电脑会永远绑 `127.0.0.1`，平板连不进来且不报任何错。
- 打完必须 `.\mic-bridge-receiver.exe --list` 能列出 CABLE 设备，才说明 PortAudio 真被打包进去了。
- EXE 与 APK 都**不进 git**（`dist/` 已忽略），走 GitHub Release；
  更新资产用 `gh release upload <tag> <file> --clobber`（**没有 `--overwrite` 这个参数，会静默不上传**），
  上传后回读 `releases/latest` 的 `.assets[].digest` 核对。

## WiFi 模式：平板不插线也能用（2026-10-30 已真机验证）

平板把音频**主动 TCP 推到电脑**，所以只要平板能出站打到那台电脑就行，不需要那台电脑能反向找到平板。
实测拓扑：平板挂在另一台电脑共享的 WiFi 上，包到达本机时源地址是**那台电脑的局域网 IP**（它做了 NAT），
所以两个网段"看着不同"并不妨碍连通 —— 反过来，电脑 ping 平板是 100% 丢包的，
**因此没法自动发现，电脑 IP 要在平板上填一次**。

### 收音的那台电脑（可以完全没有 adb、没有 Python）

从 **Releases** 下载 `mic-bridge-receiver.exe`（单文件，约 28 MB，自带 PortAudio 和 adb）：

```powershell
# 放行入站端口（WiFi 必需，不做这步接收端只会一直"等设备连"且不报错）
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go -Firewall

# 直接跑：没检测到 adb 时会自动绑 0.0.0.0 进入纯 WiFi 模式
mic-bridge-receiver.exe
# 想同时支持"插线在这台、也接受 WiFi"就显式指定：
mic-bridge-receiver.exe --bind 0.0.0.0
```

VB-Cable 虚拟声卡仍必须装（`setup_windows.ps1 -Go` 会装，或去 vb-audio.com 下 Pack45+）。

### 平板上填电脑 IP（一次就够，存 SharedPreferences）

```bash
adb shell am start -n com.zcstudy.micbridge/.MainActivity \
    --ez auto true --es lan 192.168.168.250
```

没有数据线时在平板界面点 **「WiFi 兜底：电脑 IP」** 按钮手填同一个地址即可。

### 行为约定

- **USB 优先，WiFi 兜底**：先试 `127.0.0.1:5005`（adb reverse），1.2 秒内连不上就试 WiFi。
- 连上后电脑每 2 秒回写 1 个心跳字节 `P`；平板 **10 秒内没见到第一个、或之后 6 秒没续上**，
  判定这条链路是"假通"，断开重选 —— 这是必须有的，因为 TCP 连上只代表进了对端缓冲区。
- WiFi 链路自动用更大的抖动缓冲（目标 250ms，实测稳定在 300-340ms），
  因为这条链路会偶发 100-250ms 的打嗝（见 `docs/验收记录.md`）。
- 拔掉数据线不影响推流，但平板就靠电池了；长期用建议保留线供电。

