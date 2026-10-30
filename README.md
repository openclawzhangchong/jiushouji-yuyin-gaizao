# 旧平板 → Windows 语音输入麦克风（mic-bridge）

把一台 **MTK MT6582 / Android 5.1 (API 21)** 的旧平板变成 Windows 能用的**真麦克风**：
平板自己采麦，经 **USB（不是 WiFi）** 推到电脑，电脑把流灌进 VB-Cable 虚拟声卡，
Windows 就多出一个录音设备 **`CABLE Output (VB-Audio Virtual Cable)`**，
任何程序（微信/QQ 语音、网页语音输入、Win+H 语音听写、CapsWriter）都能选它当输入设备。

**一句话：不用买 USB 麦克风，不用改任何上层软件，一根数据线搞定。**

当前状态：**已做完并在真机验收通过**（2026-10-30，`release/mic-bridge-0.3.2.apk` 已装机）。
识别验收原文逐字命中，数字见 [`docs/验收记录.md`](docs/验收记录.md)。

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

```powershell
# 1) 装运行时依赖（adb + VB-Cable + Python 虚拟环境）。默认是演练，加 -Go 才动手
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go

#    如果这台机器还要重新编译 APK（不只使用），再加构建链（约 310MB）
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go -WithBuild

# 2) 装 App 并起流
adb install -r release\mic-bridge-0.3.2.apk
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
| `release/mic-bridge-0.3.2.apk` | 当前装机版本（20.9 KB，含签名） |
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
  用来对比 MTK 平台回声处理对音色的影响

无人值守（注意 `am` 的 `--ez` **只认 `true`/`false`**，写 `1` 会被解析成 false）：

```bash
adb shell am start -n com.zcstudy.micbridge/.MainActivity \
    --ez auto true --es act selftest --es demo /sdcard/Music/loop2.wav.off
```

## 已知未完成

- **端到端绝对延迟未实测**（只测了 Windows 段 143.9ms，总估 160–300ms）。
  要出准数需要平板与 PC 跨机时钟对齐，`adb shell date` 往返几百 ms，撑不起 ±30ms 结论。
- 熄屏只连续验了 **75 秒**，没跑 30 分钟 soak。
- **开机自启 / 常驻防杀未做**：现在靠手点或 `am start`。要做接 `BOOT_COMPLETED`，
  并可用同设备已验证可行的 Device Owner / LockTask 方案（见上游仓库 `jiushouji-adb-apk2027`）。
- 音源两个档位没做正式 A/B 对比。

## 相关仓库

- [`openclawzhangchong/jiushouji-adb-apk2027`](https://github.com/openclawzhangchong/jiushouji-adb-apk2027) ——
  **这台平板的硬件评估与开发全过程记录**（含本仓库的前置结论）。
  麦克风/扬声器实测、adb 驱动排错、Kiosk 自启可行性、WebView 37 兼容性都在那边。
- `xiaole-ptt-android5-2027` —— 同设备上的语音对讲客户端，本仓库的采麦参数与出包链直接沿用它的成熟做法。
