# 真机实测记录：realme RMX3161（Android 12 / API 31）

日期：2026-11-03　｜　被测变体：modern（`com.zcstudy.micbridge.a16`）
第一次把这个变体装进真机跑通全链路，并顺带查出、修复了「息屏后麦克风被静音」的问题。

## 1. 结论

| 项目 | 结果 |
|---|---|
| 设备 | realme RMX3161，Android **12 / API 31**（不是 Android 16） |
| 安装 | `0.6.2-a16`（VC11）与 `0.6.3-a16`（VC12）均 `Success`，无 `INSTALL_FAILED_*` |
| 界面 | 正常，edge-to-edge 未遮挡按钮，无权限弹窗卡死 |
| 图标 | 桌面「桥」图标（含 zc 徽标）、标签「麦克风桥 A16」显示正常 |
| 链路 | `adb reverse tcp:5005` → PC 接收端 `ESTABLISHED`，稳定 **32,000 B/s**（16 kHz × 16 bit 单声道满速） |
| 息屏 30 s（0.6.2） | 字节仍在推，但麦克风被系统静音：峰值 **0**，`dumpsys audio` 标记 `silenced:true` |
| 息屏 30 s（0.6.3 修复后） | 峰值 **5516 / 10205 / 416**（真实环境音），速率 32 KB/s，`silenced:false` |

## 2. 设备信息

| 项 | 值 |
|---|---|
| 型号 / 厂商 | realme RMX3161 / realme |
| 序列号 | `36c7****`（打码，仅留前 4 位） |
| Android 版本 | 12（`ro.build.version.release`） |
| API level | 31（`ro.build.version.sdk`） |
| Build 指纹 | `realme/RMX3161/RMX3161CN:12/RKQ1.211103.002/R.174f96f_1-1:user/release-keys` |
| 安全补丁 | 2024-04-05 |

> 同会话里另一台设备（序列号 `0123****`，型号 XXB / alps，**Android 5.1 / API 21**）是旧机，
> 上面装着 legacy `com.zcstudy.micbridge` 0.5.0（VC8、targetSdk 22）。按约定**只读盘点，未安装、未卸载、未改任何设置**。

## 3. 安装与权限

- 安装命令：`adb -s 36c77fb6 install -r release\mic-bridge-a16-0.6.2.apk` → `Success`；
  修复后 `install -r release\mic-bridge-a16-0.6.3.apk` → `Success`。
- 安装后核对：

```
versionCode=12 minSdk=21 targetSdk=36
versionName=0.6.3-a16
```

- 权限：`adb shell pm grant com.zcstudy.micbridge.a16 android.permission.RECORD_AUDIO`
  在该 ROM 上被拒（shell 没有 `GRANT_RUNTIME_PERMISSIONS`）：

```
java.lang.SecurityException: grantRuntimePermission: Neither user 2000 nor current process
has android.permission.GRANT_RUNTIME_PERMISSIONS.
```

  但 `dumpsys package` 显示 `RECORD_AUDIO: granted=true`，App 内 `checkSelfPermission` 通过，
  实测能正常采麦（峰值非 0）。`appops` 模式为 `RECORD_AUDIO: foreground`——这正是息屏静音的伏笔。
- 启动：`adb shell am start -n com.zcstudy.micbridge.a16/com.zcstudy.micbridge.MainActivity --ez auto true`。

## 4. 链路实测

PC 端接收端在运行：`mic-bridge-receiver.exe --bind 0.0.0.0`（监听 `0.0.0.0:5005`，PID 2996）。

```
TCP  0.0.0.0:5005   0.0.0.0:0        LISTENING    2996
TCP  127.0.0.1:5005 127.0.0.1:55233  ESTABLISHED  2996
```

手机端日志（`adb -s 36c77fb6 logcat -s MICBRIDGE`）：

```
I MICBRIDGE: 已连 USB 音源=VOICE_COMMUNICATION minBuf=1280 用=5120
I MICBRIDGE: 心跳 已推 50s 累计 1597440B 速率 31987B/s 峰值 416 欠采 0 重连 0 链路 USB 状态 采麦中 · USB
```

- 1 分钟累计约 2.09 MB，峰值持续非 0，`欠采 0`、`重连 0`；
- App 内置心跳校验（PC 端要回写字节）通过，说明对端**真的在读**，不是把数据吞进内核缓冲区。

界面（0.6.3 运行中）：[`ui-main-0.6.3.png`](ui-main-0.6.3.png)
0.6.2 首次装机的界面：`ui-main-0.6.2.png`（同目录）

## 5. 桌面图标

[`launcher-icon.png`](launcher-icon.png) —— 仅裁到图标与名称区域：深色底「桥」+ 右下角 `zc` 徽标，
标签「麦克风桥 A16」。桌面其余区域（含第三方 App、推广卡片、通知栏）已裁掉，未入库。

## 6. 息屏静音：现象、根因、修复

### 6.1 现象（0.6.2，未修复）

息屏 30 秒期间每 5 秒一条心跳：

```
15:17:07 心跳 速率 32000B/s 峰值 0 欠采 0 重连 0 链路 USB 状态 采麦中 · USB
15:17:12 心跳 速率 32000B/s 峰值 0 ...
15:17:22 心跳 速率 32000B/s 峰值 0 ...
```

即：**TCP 推流没断（速率满 32 KB/s），但采到的样本全是 0**。

### 6.2 根因证据

息屏时进程状态从 `top-activity` 变成 `top-sleeping`：

```
Proc # 0: fg b/A/TPSL ---- t: 0 31307:com.zcstudy.micbridge.a16/u0a350 (top-sleeping)
```

AudioService 的 `RecordActivityMonitor` 直接把该 session 判为静音（亮屏/息屏来回切换可见翻转）：

```
session:66633 ... pack:com.zcstudy.micbridge.a16 ... silenced:true
15:16:26 rec update ... silenced pack:com.zcstudy.micbridge.a16     ← 息屏
15:16:41 rec update ... not silenced pack:com.zcstudy.micbridge.a16 ← 亮屏
15:16:57 rec update ... silenced pack:com.zcstudy.micbridge.a16     ← 再息屏
```

`appops` 模式是 `RECORD_AUDIO: foreground`，而 App 只有 `PARTIAL_WAKE_LOCK`、没有前台服务。

**判断**：这不是 `WAKE_LOCK` 不够，也不是 AudioRecord 坏了，而是 **Android 11+ 的后台录音限制**——
非前台进程（`top-sleeping`）的录音会被 AudioService 静默成 0；`PARTIAL_WAKE_LOCK` 只保证 CPU 不休眠，
不改变进程的前台/后台判定。旧机型（Android 5.1）没有这条限制，所以 legacy 版不暴露此问题。

### 6.3 修复（0.6.3-a16 / VC12，仅动 `app/src-modern/`）

- 新增 `app/src-modern/java/com/zcstudy/micbridge/MicService.java`：`foregroundServiceType="microphone"`
  的前台服务，`startForeground(..., FOREGROUND_SERVICE_TYPE_MICROPHONE)`，常驻通知「麦克风桥正在送话」。
- `app/src-modern/AndroidManifest.xml`：补 `FOREGROUND_SERVICE`、`FOREGROUND_SERVICE_MICROPHONE`、
  `POST_NOTIFICATIONS`，并声明该 service。
- `app/src-modern/.../MainActivity.java`：开始/停止送话时同步 start/stop 前台服务，`onDestroy` 兜底停服务。
- legacy 的 `app/src/`、`app/AndroidManifest.xml`、`build.sh`、`release/mic-bridge-0.5.0.apk` **零改动**。
- 出包：`VER=0.6.3 VC=12 bash build_android16.sh` → `release/mic-bridge-a16-0.6.3.apk`。

### 6.4 修复后复测（息屏 30 秒）

进程被抬成前台服务（息屏状态）：

```
Proc # 0: fg +50 F/A/FGS --MN t: 0 17460:com.zcstudy.micbridge.a16/u0a350 (fg-service-act)
mWakefulness=Asleep
session:66649 ... pack:com.zcstudy.micbridge.a16 ... silenced:false
```

心跳（每 10 秒取样一次）：

```
[10s] 心跳 已推 30s 累计 956800B  速率 31993B/s 峰值 5516  欠采 0 重连 0 链路 USB
[20s] 心跳 已推 40s 累计 1277440B 速率 32000B/s 峰值 10205 欠采 0 重连 0 链路 USB
[30s] 心跳 已推 50s 累计 1597440B 速率 31987B/s 峰值 416   欠采 0 重连 0 链路 USB
```

峰值随环境音变化（不是恒定 0），`silenced:false` 全程保持 → **息屏静音问题已修复**。

前台服务通知：[`fg-service-notification.png`](fg-service-notification.png)（仅保留本条通知卡片，
其余第三方通知已裁掉）。

## 7. 图片索引

| 文件 | 内容 | 对应结论 |
|---|---|---|
| [`ui-main-0.6.3.png`](ui-main-0.6.3.png) | 0.6.3 主界面（采麦中 · USB，速率/峰值/心跳；状态栏第三方通知图标已打码） | 界面正常、链路在推 |
| [`ui-main-0.6.2.png`](ui-main-0.6.2.png) | 0.6.2 首次装机主界面（状态栏第三方通知图标已打码） | 首装可运行 |
| [`launcher-icon.png`](launcher-icon.png) | 桌面「桥」图标 + 名称（已裁剪） | 图标正常 |
| [`fg-service-notification.png`](fg-service-notification.png) | 前台服务常驻通知（仅保留本条卡片） | 0.6.3 修复手段生效 |

脱敏说明：两张主界面截图的状态栏只保留时间、系统状态图标与麦克风隐私指示点，
第三方 App 的通知图标已用底色覆盖；`launcher-icon.png` 仅裁图标与名称；
`fg-service-notification.png` 仅保留本条通知卡片，下方其它通知已裁掉。

## 8. 未验证 / 限制

- **Android 16（API 36）真机仍未验证**：本次只有 Android 12 设备。targetSdk 36 在 API 31 上
  向后兼容、实测无 `targetSdk` 相关崩溃，但 Android 16 上的行为（edge-to-edge 强制、FGS 启动限制、
  16 KB 页对齐）仍无真机数据。
- **通知权限**：Android 12 上通知默认可用；Android 13+ 需要用户授予 `POST_NOTIFICATIONS`，
  否则前台服务通知不可见（服务本身仍有效）。本次未在 13+ 上验证。
- **厂商后台策略**：realme/ColorOS 的省电策略可能杀后台。本次息屏 30 秒通过，长时间（数小时）
  与「应用被划掉后」的存活未测；如需长期常驻，建议在系统设置里允许该 App 后台运行/自启动。
- **外放自测**未跑（需要 `READ_EXTERNAL_STORAGE` + `/sdcard/Music/demo.wav`，本次未授予/未推送）。
  `READ_EXTERNAL_STORAGE` 仍为 `granted=false`，与主链路无关。

---

## 9. 0.6.4 前台服务生命周期修复（2026-11-03 复测）

### 9.1 修了什么

独立复核报出 5 个缺陷（2 个中级）。修法按要求走**变体覆盖**：新增
`app/src-modern/java/com/zcstudy/micbridge/Bridge.java`（modern 专用副本），
`build_android16.sh` 的 javac 同步排除 legacy 的 `Bridge.java`；
`app/src/`、`app/AndroidManifest.xml`、`build.sh`、`release/mic-bridge-0.5.0.apk` **零改动**。

| 缺陷 | 修法 |
|---|---|
| 异常路径漏 wakelock、`running`/状态不回落 | `run()` 外层兜底 `Throwable`：`running=false`、`releaseWake()`、状态写「已停止（异常：…）」、`Log.e` 带栈，并通知 UI 撤服务 |
| 先起前台服务、后起 Bridge，初始化失败服务常驻 | `Bridge.start(Listener)` 回传结果；**收到 PC 第一个心跳（真实数据流）才** `startForeground`，断线立即撤通知并释放 wakelock（重连成功再抬回前台） |
| `MicService` 异常终止残留通知 | `onDestroy()` 里 `stopForeground(STOP_FOREGROUND_REMOVE)` + `stopSelf()` |
| Android 13+ 未运行时申请通知权限 | `MainActivity` 在开始送话前申请 `POST_NOTIFICATIONS`（拒绝只影响通知可见性，不阻塞送话） |

### 9.2 legacy 等价性证明

用隔离副本（`build.sh` + 原样 `app/`）以 `VER=0.5.0 VC=8` 重建 legacy，与
`release/mic-bridge-0.5.0.apk` 内的条目逐一比对 SHA-256：

| 条目 | 原 0.5.0 APK | 重建产物 | 一致 |
|---|---|---|---|
| `classes.dex` | `557BCB1CE1CA3250D9576CE8460A083CA5BA8D9E84A18C4884EE21B4EA0F6EAC` | 同左 | ✅ |
| `resources.arsc` | `ACB4A519A871C87AF4E678A02FB8C4435DF0D6A74A1FAC8C8984D248E8D6C4E5` | 同左 | ✅ |
| `AndroidManifest.xml` | `B272CAD0C413B4F6C047DD04BD77CC91D0E03393511D29B9966FFF50DD35E638` | 同左 | ✅ |

`release/mic-bridge-0.5.0.apk` 文件级 SHA-256 全程未变：
`3CFFC2B0438DF00EC38FEF1619B70D5AF55241EBDF50B86C2FCB4DAC402C2B92`（未重写该文件）。
重建产物的整包哈希会因签名时间戳不同，因此以**内嵌条目哈希**为准。

### 9.3 真机复测（realme RMX3161 / Android 12，0.6.4-a16 / VC13）

**① 正常送话**（`ui-main-0.6.4.png`）：

```
心跳 已推 92s 累计 2003200B 速率 32000B/s 峰值 71 欠采 0 重连 7 链路 USB 状态 采麦中 · USB
dumpsys activity services → isForeground=true（front-of-task 前台服务）
PC 端 mic-bridge-receiver：累计 92s / 32016 B/s（真实收到，非内核缓冲区）
```

**② 息屏 30 秒**（每 10 秒采样）：

```
[10s] silenced=false 峰值 722   速率 32000B/s
[20s] silenced=false 峰值 284   速率 32000B/s
[30s] silenced=false 峰值 2989  速率 32000B/s
dumpsys power: mWakefulness=Asleep；micbridge:up 仅在采麦期间持有
```

**③ 失败态**（停掉 PC 接收端，模拟「对端不可用/断线」）：

```
MICBRIDGE: 断开/连不上：java.io.IOException: Broken pipe  1000ms 后重试
dumpsys activity services com.zcstudy.micbridge.a16 → 空（前台服务已停、通知已撤）
dumpsys power | grep micbridge:up → 连续 3 次采样均为空（wakelock 未持有）
pidof com.zcstudy.micbridge.a16 → 进程存活；logcat 无 FATAL EXCEPTION / ANR
```

失败态界面（`ui-fail-0.6.4.png`）显示「等待电脑端 (Broken pipe)」「上行 0 B/s」「还没连上」，
按钮仍为「停止送话」（采集线程在退避重试）；恢复接收端后自动重连，前台服务与通知自动回来。

> 备注：失败注入用的是**停掉 PC 端接收进程**（不是撤销权限）。该 ROM 的 shell 没有
> `MANAGE_APP_OPS_MODES` / `REVOKE_RUNTIME_PERMISSIONS`，`cmd appops set` / `pm revoke` 均被拒绝，
> 无法用 adb 撤销权限。

### 9.4 未修的 3 个低优先级项（已知风险）

1. **`Bridge.stop()` 仍在主线程 join（最长 1500ms）**：点「停止送话」时 UI 线程最多阻塞 1.5s。
   0.6.4 未改为后台停止（改法要引入线程状态机与按钮防重入，超出本次范围），列为此后优化项。
2. **`MicService` 用 `START_NOT_STICKY`**：进程被 ColorOS 省电策略杀掉后服务不会自动重建，
   需要用户重新点「开始送话」；长期常驻仍建议在系统里允许后台运行/自启动。
3. **Android 13+ 通知权限/Android 16 行为未真机验证**：已补运行时申请，但不授予时通知不可见；
   Android 16 的 FGS 启动限制、edge-to-edge 强制仍无实机数据。

