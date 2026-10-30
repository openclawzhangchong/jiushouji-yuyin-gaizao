# AGENTS.md — 接手这个仓库前必须读完

面向 AI / 陌生程序员。**这里写的是"已经用真机付过学费"的约束，不是建议。**
违反第 2、3 节的条目会直接构建失败或跑不出声音，而且报错信息会把原因指到别处去。

---

## 1. 这个项目在做什么

旧平板（MTK MT6582 / Android 5.1 / API 21，代号 `b906`、`full_b906`、型号 `XXB`）
当 Windows 的麦克风：平板采麦 → **USB**（`adb reverse` 搬 TCP 口）→ `pc_receiver.py`
→ 播进 VB-Cable 的渲染端点 `CABLE Input` → Windows 出现录音端点 `CABLE Output` 供任意程序使用。

**链路上任何一环断了，现象都是"Windows 有麦克风但没声音"**，而不是报错。
排查顺序永远是：平板心跳（`adb logcat -s MICBRIDGE:V`，5 秒一条）→ 接收端打印的"推流中/水位"
→ CABLE Output 是否存在。别一上来就怀疑虚拟声卡。

---

## 2. 硬约束（改代码前对照）

### 平板侧

| # | 约束 | 违反了会怎样 |
|---|---|---|
| 1 | **只能 `armeabi-v7a`**，没有 64 位 | 装不上 |
| 2 | **API 21**：没有运行时权限模型（权限在清单里声明即安装时授予），也**没有** `AudioRecord.getInputBuffer`、`SNIHostName`、`WifiManager.getMacAddress` 等 API 17+ 之外新增的符号 | 编译期就缺符号；或误加 `requestPermissions` 导致永久拿不到权限 |
| 3 | **没有 Google 服务、没有 root、SELinux permissive** | 任何依赖 GMS/Play 商店/Firebase 的方案直接排除 |
| 4 | 采麦参数固定为 `AudioRecord(VOICE_COMMUNICATION, 16000, CHANNEL_IN_MONO, ENCODING_PCM_16BIT)`，缓冲 `getMinBufferSize()*4`（实测 min=1280B=40ms，用 5120B） | 换采样率/声道会在这台机器上初始化失败或出杂音；这是从 `xiaole-ptt` 生产代码抄来的**已验证**配置 |
| 5 | **长后台线程 + `PARTIAL_WAKE_LOCK`** 就够用：Android 5.1 **没有 Doze**（6.0 才有），熄屏续流已实测 75 秒无断档 | 别急着加 Foreground Service / 通知栏；那需要额外权限和生命周期处理，收益为零 |
| 6 | UI **全部用代码搭，不写布局 XML**；主题在 `onCreate` 里 `setTheme()` | `aapt2` 配这套工具链会**静默丢弃** manifest 里的 `android:theme` 和 flag 型属性值，且**不报任何告警** |
| 7 | 无 WebView 参与。这台机器 WebView 是 Chrome 37，跑复杂渲染曾触发框架软重启 | 别把链路改成 H5 |
| 8 | CPU 空闲时只 1 核 @598MHz，有负载才 4 核 @1.3GHz；内核有 **7 个长期 D 状态线程**（loadavg≈7 是正常态，不是故障） | 看到 loadavg 7 别去"修"它 |

### 传输

| # | 约束 | 理由 |
|---|---|---|
| 9 | **走 USB + `adb reverse`，不走 WiFi** | 平板和主机根本不在同一网段（主机有线 192.168.168.x，平板历史在 192.168.191.x）；USB 还顺便供电 |
| 10 | App 只连 `127.0.0.1:5005`（平板自己那侧） | `adb reverse tcp:5005 tcp:5005` 把它搬到主机的 5005。App **不要**改成监听端口，也不要写死主机 IP |
| 11 | **不要用 `adb reverse --list` 判存活** | Android 5.1 的 adbd 不支持它，会返回 `error: protocol fault (couldn't read status length)`。`pc_receiver.py` 因此改成"设备在位 + 当前无客户端"就幂等重下发 |
| 12 | 单声道 16bit 16kHz = **满速 32000 B/s**；实测 20ms 分包在 USB 上零丢包 | 心跳速率显著低于 32000 B/s 就是平板侧出问题，不是网络问题 |
| 13 | TCP（不是 UDP） | 已验 200/200 包零丢，TCP 的重传在这条链路上不会造成可闻损伤，且省掉丢包处理逻辑 |

### Windows 侧

| # | 约束 | 理由 |
|---|---|---|
| 14 | **必须装 VB-Cable Driver Pack 45 或更新**（`vbaudio_cable64_win10.sys`，DriverVer 2024-10-07） | **Pack 43 是 2015 年的包，只有 win7 驱动，Win11 22631 装不上** —— 这个坑踩过一次 |
| 15 | 装完**免重启**即出现 `CABLE Output`（`{0.0.1...}` = capture 端点）；卸载**需要**重启 | 别为了"生效"去重启主机 |
| 16 | 灌入用 `CABLE Input`（渲染端点），取用是 `CABLE Output`（录音端点）—— **方向别搞反** | 反了就是录音录不到东西 |
| 17 | `latency` 必须显式设 `'low'`（或具体秒数），否则走设备默认档 | 默认档 DirectSound 一个方向就是 120ms，实测总延迟从 330ms 掉到 143.9ms |
| 18 | 用 **Python + sounddevice**（和 CapsWriter 同栈） | PowerShell 5.1 加载 NAudio 的 netstandard2.0 会失败；最新 NAudio 只发 net9.0 更不行。要 .NET 做音频只能锁 NAudio 2.2.1 |
| 19 | PortAudio 设备名被截到 **32 字符**（如 `CABLE Output (VB-Audio Virtual `） | 按名字匹配要用**包含**，不能用相等；`sd.query_devices()` 在 0.5.6 返回 **dict** 不是对象 |
| 20 | 主机**没有任何真实录音设备** | 见 README「为什么非走这条路」。别再提议 line-in / Stereo Mix / 蓝牙 HFP / UAC gadget |

### 构建

| # | 约束 | 理由 |
|---|---|---|
| 21 | **工具链必须放在纯 ASCII 路径**，本项目用 `C:\android-build\` | `aapt2 link -I <jar>` 对中文路径报 `Failed to stat file '...': No such file or directory`，**文件其实是存在的** |
| 22 | 目录名有惊喜，别猜：`build-tools_r34-windows.zip` 解出来叫 **`android-14`**；`android-21_r02.zip` 解出来叫 **`android-5.0.1`**；JDK 需自己改名成 `jdk17` | `build.sh` 顶部的路径注释就是为这个 |
| 23 | `build.sh` 里 **程序路径用 POSIX（`/c/...`），传给原生 exe 的参数用 Windows（`C:/...`）** | JVM 打不开 POSIX 风格路径 |
| 24 | aapt2 link 的资源必须用**位置参数**，不能用 `-R` | `-R` 是 overlay 语义，定义新资源会报 `resource string/app_name does not override an existing resource` |
| 25 | `apksigner verify` 那一步**不能接 `| head`** | SIGPIPE 会让 `set -e` 把成功的构建误判成失败 |
| 26 | 出包后有**自证**：`aapt2 dump badging` 里的 versionCode/versionName 必须和脚本参数一致，不一致就拒绝出包 | 防多个会话同时改这棵树导致"脚本写 0.6.1、产物是 0.6.2" |
| 27 | `release/<模块>-<版本>.apk` **不许覆盖**，确实要重发用 `FORCE_RELEASE=1`；改代码就升 `VER`/`VC` | 同上，防版本错乱 |

### 测试与操作陷阱

| # | 陷阱 | 正确做法 |
|---|---|---|
| 28 | **`am start --ez NAME 1` 会被解析成 `false`**，`--ez` 只认 `true`/`false` | 写 `--ez auto true`。App 侧已兜底：只要给了 `act` 参数就自动开始送话 |
| 29 | 改 App 里"是否自动启动"这类逻辑时，光看"进程在不在"会误判成功 | 用 `MICBRIDGE:V` 心跳日志判活，进程存在 ≠ 在推流 |
| 30 | **主机显示器（MG2461VI）没有扬声器** | 所有声学验收必须**由平板自己外放**（`selftest`），不要试图用电脑放声音去喂平板麦克风 —— 那样只会得到"全零/底噪"的假失败 |
| 31 | 验证"经过虚拟麦的音频质量"时 | **比较区间必须卡在实际发送的秒数内**，并用冲激先定位对齐点，否则拿后半段静音比语音会得出 r=0.03 的**假阴性**（踩过）。用 `spike/fidelity.py`、`look.py` 的路子 |
| 32 | Python 脚本输出重定向到文件是**全缓冲** | 日志要实时可见得开 `sys.stdout.reconfigure(line_buffering=True)`，或 `python -u` |
| 33 | Git Bash 里 `adb shell` 的**远程**路径会被 MSYS 改写 | 远程路径前加 `MSYS_NO_PATHCONV=1`；但这样本地路径就得写 `E:/...` 的 Windows 形式 |
| 34 | 接收端收尾时 `srv.close()` 会让 `accept()` 抛 `WinError 10038` | 已 catch，别改成裸奔 |

---

## 3. 禁止事项

- **不要**删掉 `CABLE Output` 之外的任何音频端点，不要在验收中途卸载 VB-Cable。
- **不要**为了"更实时"把 TCP 换成 UDP —— 已验证零丢包，换协议只会增加丢包处理复杂度。
- **不要**把采样率改成 44.1k/48k 来"减少重采样"。16k 是 ASR 引擎的原生格式，也是已验证配置。
  设备侧 16k↔44.1k 的重采样只造成**相位**差异（皮尔逊 r≈0.865），**分频带能量比 100–6000Hz 全 ≈1.000**，
  ASR 逐字全对 —— 不值得为此改动。
- **不要**相信 `adb devices` 显示 `offline` 就等于"等用户点授权"。实测 `offline` 时授权框压根不会弹，
  这台平板的日期是正确的，最终是靠撤销/重开 USB 调试恢复的。`unauthorized` 才是"等你点"。
- **不要**在没跑 §4 的验收就声称"改好了"。这个项目里"看起来能连"和"能出可识别的语音"是两件事。
- 不要提交 `out/`、`*.wav`（验收音频）、`__pycache__`、根目录的 `mic-bridge.apk(.idsig)` —— 已在 `.gitignore`。

---

## 4. 怎么证明你的改动没把链路弄坏（必跑）

```bash
# 0) 前置：接收端在跑，平板已授权，VB-Cable 已装
# 1) 出包（会自动做版本自证）
VER=0.4.0 VC=6 bash build.sh
adb install -r release/mic-bridge-0.4.0.apk

# 2) 无人值守回归：平板自己外放已知中文、自己听回来、PC 录 34 秒
python pc_receiver.py --record 34 &
adb shell am start -n com.zcstudy.micbridge/.MainActivity \
    --ez auto true --es act selftest --es demo /sdcard/Music/loop2.wav.off
wait

# 3) 判据（三条都要满足）
adb logcat -d -s MICBRIDGE:V        # 心跳速率 31850–32650 B/s，欠采 0，重连不增长
# verify.wav 包络：外放段平均约 -8dBFS、峰值不低于 -4dB；静音段应≈ -97dBFS 数字零
python look.py                      # 频谱 1000-2000Hz 最强（语音形状）
# 丢给 ASR：必须逐字复现「Hello 啊，我是小智啦。声音好听的台湾女孩一枚，超开心认识你耶…」
node E:/github项目/yuyin-shuru-trial/test/ws-transcribe.mjs verify.wav zh
```

判据基线的完整数字在 `docs/验收记录.md`。

**`/sdcard/Music/` 里现成留着可用素材**：`loop1.wav.off`、`loop2.wav.off`（≈10.9s，已知中文文本，24kHz）、
`loop3.wav`（loop2 串三遍，32.7s）。`.off` 只是当年改名停用，内容有效，`selftest` 能直接播。

---

## 5. 现状与待办

**已完成**：v0.3.2 装机；链路端到端逐字识别通过；断线自恢复通过；熄屏 75 秒续流通过。

**未做（别当成已完成）**：

- 端到端绝对延迟未实测（只有 Windows 段 143.9ms 实测 + 组成估算 160–300ms）。
- 30 分钟以上熄屏 soak 未跑。
- **开机自启 / 常驻防杀未做**（现在靠手点或 `am start`）。要做就接 `BOOT_COMPLETED`，
  并参考同设备已验证的 Device Owner / LockTask 方案（上游仓库 `jiushouji-adb-apk2027` 的
  `docs/06-Kiosk可行性实测.md`）。注意那边记的坑：**清除 stopped 状态后必须手动起一次，
  开机自启才会生效**。
- 音源 `VOICE_COMMUNICATION` vs `VOICE_RECOGNITION` 未做正式 A/B。

台账（每条结论的出处、实测数字、环境变更记录）在 `PLAN.md`，改架构前先读它。
