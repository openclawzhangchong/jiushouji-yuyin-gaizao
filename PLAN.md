# 旧平板做电脑语音输入麦克风 —— 决策与实测台账

> 本文件是运行中的决定日志，每条结论都带实测出处。改架构前先读这里。
> 建档 2026-10-30 上午（可行性 Spike）→ 当日中午完工（v0.3.2 已装机、链路在跑）。

## 0. 目标与结论

把手边这台旧安卓设备当**麦克风**，让 Windows 出现一个可用的录音设备，
任何程序（微信/QQ 语音、网页语音输入、Win+H、CapsWriter）都能当普通麦克风选它。

**已经做出来了。** 平板采麦 → USB(adb reverse) → PC 接收端 → VB-Cable → Windows 麦克风
`CABLE Output` → 已知中文被 Qwen3-ASR **逐字认出**。熄屏续流、断线自连都验过。

## 1. 设备事实

插着的这台 = `jiushouji-adb-apk2027` 记录的那台，**同一台**：
序列号 `0123456789ABCDEF`、`product:full_b906`、`model:XXB` 全部对上。

| 项 | 值 |
|---|---|
| 形态 | 7 寸**平板**（不是手机），MTK **MT6582** 4×Cortex-A7 @1.3GHz |
| 系统 | Android **5.1 / API 21**，无 root、无 Google 服务，SELinux permissive |
| ABI | 仅 `armeabi-v7a`；`adb shell getprop ro.build.version.sdk` = 21 复核 |
| 麦克风 | 好。用户 2026-10-30 中午用录音机手动录过；本轮又被声学自测二次确认 |
| 外放 | 好（自测靠它）。`/sdcard/Music/` 里还留着上次的 `loop1.wav.off / loop2.wav.off / loop3.wav` |
| 供电 | `USB powered: true`，一根线同时供电+走数据 |
| 网络 | 和 PC **不同网段**（PC 有线 192.168.168.250，平板记录过 192.168.191.x）→ 这正是选 USB 的理由 |

采麦参数不用猜，直接抄自己生产代码：
`xiaole-ptt-android5-2027/src/com/zcstudy/xiaole/ptt/Audio.java:15-40`
= `AudioRecord(VOICE_COMMUNICATION, 16000, CHANNEL_IN_MONO, ENCODING_PCM_16BIT)`。

## 2. 唯一的真卡点（已解除）：这台电脑原来一个录音设备都没有

只有 3 个**渲染**端点，capture 端点为 0。所以这些路都死：

- ❌ 3.5mm 音频线接电脑 line-in —— 没有 line-in
- ❌ 立体声混音 (Stereo Mix) —— 也是 capture 端点，不存在
- ❌ 手机当蓝牙 HFP 耳机 —— Android 只能做 AG 角色
- ❌ 手机做 USB Audio Class 设备 —— 要 kernel gadget + root

**必须有虚拟声卡驱动，没有第二条路。**

## 3. PC 侧可行性实测（Spike 数字，仍是有效结论）

- 驱动：官方 `VBCABLE_Driver_Pack45.zip`，`vbaudio_cable64_win10.sys` DriverVer 2024-10-07，
  签名 `Valid`、cat `Valid`，**装完免重启**。
  ⚠️ **Pack43 是 2015 年老包，只有 win7 驱动，Win11 22631 装不上**（一开始就踩了）。
- 端点：`CABLE Input`=渲染（往里灌），`CABLE Output`=capture（这就是麦克风），另有 `CABLE In 16 Ch`。
- 纯音透传：灌 440Hz@0.25 → 录到 peak **0.2500** 分毫不衰减；1000Hz 对照低 4 个数量级（选择性 65–78dB）。
- 分频带能量比 100-500 / 500-1k / 1k-2k / 2k-3.5k / 3.5k-6k Hz **全部 ≈1.000** → 频谱无损。
- 延迟：DirectSound 默认档 330–340ms；**WDM-KS/MME + `latency=low` + block 320 → 143.9ms**；
  block 再调小只增加欠载，不降延迟（大头是 PortAudio/WASAPI 缓冲预算，不是虚拟声卡）。

## 4. 最终架构

```
[平板 b906]  AudioRecord 16k/mono/PCM16  →20ms分包→ TCP 127.0.0.1:5005
                                                      ↑ adb reverse tcp:5005 tcp:5005
[PC]  pc_receiver.py  TCP监听 → 弹性缓冲(目标60ms) → sounddevice 播进 CABLE Input
                                                                     ↓
        Windows 麦克风「CABLE Output」 ← 任何程序可选；CapsWriter 走系统默认输入
```

**选 USB 不选 WiFi** 的理由：平板和 PC 根本不在一个网段；一根线还顺便供电。
App 只连自己的 `127.0.0.1:5005`，靠 `adb reverse` 把它搬到 PC 上，平板不需要开监听端口。

## 5. 交付物

| 文件 | 作用 |
|---|---|
| `app/AndroidManifest.xml` | 权限 RECORD_AUDIO/INTERNET/WAKE_LOCK/READ_EXTERNAL_STORAGE；minSdk 21 |
| `app/src/.../Bridge.java` | 采麦+分包+TCP 推流+退避重连+PARTIAL_WAKE_LOCK+5s 心跳日志+标定音注入 |
| `app/src/.../MainActivity.java` | 全程序化 UI（大开关/28段电平/状态行/标定音/外放自测/音源切换），intent 无人值守 |
| `build.sh` | 无 Gradle 出包链，沿用 ptt 版流程与自证检查 |
| `pc_receiver.py` | adb reverse 管理 + TCP 收流 + 弹性缓冲 + 播进 CABLE Input + 状态打印 + 可选同时录音 |
| `acoustic_probe.py` `look.py` | 声学回环与包络/频谱分析（`look.py` 读 verify.wav） |
| `run_selftest.sh` | 无人值守回归一条命令 |
| `setup_windows.ps1` | **新机一键部署**：adb + VB-Cable + .venv（`-WithBuild` 附带 APK 构建链）。默认 DRY-RUN，纯 ASCII（PS 5.1 会把无 BOM 的 UTF-8 读成 GBK） |
| `README.md` | 入口：为什么只能走这条路、架构图、部署两步半、文件清单 |
| `AGENTS.md` | **给接手 AI 的硬约束/禁止事项/必跑验收**，坑按"违反了会怎样"写 |
| `docs/验收记录.md` | 验收数字与 ASR 原文 |
| `spike/` | 丢弃型验证脚本 + `spike/README.md` 标明别当实现参考 |
| `启动接收端.bat` | 双击启动（优先用仓库内 `.venv`） |
| `acoustic_probe.py` `look.py` `spike/` | 验收脚本（spike/ 是丢弃型，结论已出可删） |
| `release/mic-bridge-0.3.2.apk` | 当前装机版本 |

### 用法

```bash
# 一次性：平板开 USB 调试并点「允许」；PC 已装 VB-Cable + adb
python pc_receiver.py            # 常驻，关窗口即停；或双击 启动接收端.bat
adb shell am start -n com.zcstudy.micbridge/.MainActivity --ez auto true   # 平板端自动开始送话
# 或者在平板上直接点大按钮「开始送话」

# 无人值守回归（含平板自己外放已知音频、自己听回来）
adb shell am start -n com.zcstudy.micbridge/.MainActivity \
    --ez auto true --es act selftest --es demo /sdcard/Music/loop2.wav.off
python pc_receiver.py --record 34   # 录下 CABLE Output，再丢给 ASR
```

**要让 CapsWriter 用**：把 `CABLE Output` 设成 Windows **默认录音设备**即可，
它 `core/client/audio/stream.py:115` 取的就是默认输入（`device=None`），不用改代码。
它按 `min(2, 声道数)` 开 2 声道，而 VB-Cable 会把单声道复制到两路，
所以幅度不丢（实测 2ch 录到 peak 仍等于灌入值）。

## 6. 验收结果（2026-10-30 中午，全部在真机跑）

| # | 项目 | 结果 |
|---|---|---|
| 1 | 字节率 | 心跳侧 **31852–32640 B/s**（满速 32000），接收端同量级；**欠采 0、丢块 0**，长时间稳定 |
| 2 | 水位 | 40–140ms 区间来回，不持续增长；**弹性缓冲不失效** |
| 3 | **真语音识别** | 平板外放已知中文 → 自己麦克风采 → USB → CABLE Output 录下 → Qwen3-ASR：「Hello 啊，我是小智啦。声音好听的台湾女孩一枚，超开心认识你耶。最近在忙啥？别忘了给我来点有趣的料哦！」 **逐字正确**，服务端处理 1644ms |
| 4 | 声学有效性 | verify.wav 包络：0–5s = -97dBFS 数字静音；**7–16s 平均 -8.7dBFS、峰值 -3.3dB**；17s 后回落 -50dB 底噪。频谱 1000-2000Hz 最强，是语音形状 |
| 5 | 断线自恢复 | 杀掉接收端 → App 退避重试；重启接收端 → **自动重连续流**，全程零人工（重连计数 14） |
| 6 | 熄屏续流 | `input keyevent 26` 熄屏（`mWakefulness=Asleep`、`Display Power: state=OFF`）**75 秒**，14 条心跳满速无断档、欠采 0；`PARTIAL_WAKE_LOCK 'micbridge:up'` 确认持有 |
| 7 | 长跑顺带观测 | 装机后链路连续跑了 **541 秒**（期间我反复重启接收端造成 **6 次重连**），速率仍 31676 B/s、水位 60–80ms；累计**欠载 126 次**。按 20ms 一块算约 27000 块，占比 **0.47%**，且怀疑主要来自每次重连后的水位重建期（**没做"纯稳态长跑"的对照，别当成稳态指标**）；30 分钟 soak 仍未跑 |

## 7. 没做到的 / 待办

- **端到端绝对延迟没实测**。只测了 Windows 段 143.9ms（§3，同设备同参数），
  加平板侧 20ms 分块 + USB ≈1ms + 接收端水位 40–140ms，**估 160–300ms**。
  要出准数需要平板与 PC 的跨机时钟对齐，`adb shell date` 往返延迟太粗（几百 ms），撑不起 ±30ms 的结论。
  对听写/语音输入这个用途延迟不敏感，所以没优先做。
- 熄屏只连续验了 **75 秒**，没跑 30 分钟 soak。
- **开机自启 / 常驻不被杀**：现在靠手动点按钮或 `am start`。要真正无人值守，
  下一步接 `BOOT_COMPLETED` +（你那套 Kiosk 已验证可行的）Device Owner/LockTask。
- 没做平板侧掉线提示音/界面告警（现在只有状态行文字）。
- 音源 A/B：现默认 `VOICE_COMMUNICATION`（沿用你验证过的配置），
  界面有按钮可切 `VOICE_RECOGNITION` 对比 MTK 回声处理的影响，**没正式对比过**。
- `spike/` 是丢弃型验证脚本，别当实现参考。

## 8. 本机环境变更（都可回退）

| 变更 | 位置 / 回退 |
|---|---|
| **VB-Cable 虚拟声卡**（核心依赖） | 卸载 `VBCABLE_Setup_x64.exe /u` 或设备管理器删 `ROOT\MEDIA\0000`，卸载需重启 |
| **adb** winget `Google.PlatformTools` r37.0.1 | `winget uninstall Google.PlatformTools` |
| 工具链 **`C:\android-build\`**（jdk17 / android-14=build-tools r34 / android-5.0.1=平台21） | 整目录可直接删 |
| venv `E:\github项目\jiushouji-yuyin-gaizao-build\venv`（sounddevice 0.5.6 + numpy） | 71MB，**当前后台接收端进程用的就是它**；仓库内另有 `.venv`（`setup_windows.ps1` 在新机器上建的就是这个）。临时下载的 3 个安装包 zip 已删（298MB，工具链已解压到 `C:\android-build`，需要时可重下） |
| 平板装了 `com.zcstudy.micbridge` v0.3.2；`/sdcard/Music/` 未改动 | `adb uninstall com.zcstudy.micbridge` |
| 为识别测试启动过 CapsWriter `start_server.exe` | **已 taskkill 停掉**，6016 端口已释放 |
| `%USERPROFILE%\.android\adbkey*` 被我备份后重生成过 | 旧密钥在 `~/.android/backup-1793325989/`；换密钥会让平板上的旧授权失效，需重新点「允许」 |
| 当前仍在后台跑着 `pc_receiver.py` | 关窗口 / `taskkill /IM python.exe` 会连链路一起停 |

## 9. 踩坑记录（下次别再踩）

- **VB-Cable 只能用 Pack45 及以上的 win10 驱动**，Pack43 只到 win7。
- **aapt2 stat 不到中文路径里的 android.jar**：`E:/github项目/...` 会报 No such file or directory。
  工具链必须整体放纯 ASCII 路径（这台放 `C:\android-build`，正好和你另一台的 `D:/android-build` 同构）。
- `am start --ez` **只认 `true`/`false`**；写 `--ez auto 1` 会被解析成 **false**，
  表现为"App 起来了但什么都没发生"。已让 App 见到 `act` 参数就自动启动来兜这个坑。
- **Android 5.1 的 adbd 不支持 `adb reverse --list`**（`error: protocol fault`），
  但 `adb reverse tcp:x tcp:x` / `--remove-all` 正常。所以隧道存活只能靠
  "设备在位 + 无客户端"来重新下发，不能查 list。
- PortAudio 设备名被截到 32 字符（`'CABLE Output (VB-Audio Virtual '`），匹配要用包含不是相等。
- `sd.query_devices()` 0.5.6 返回 **dict**，取属性 `AttributeError`。
- PowerShell 5.1 装不动 NAudio 的 netstandard2.0 包；最新 NAudio 只发 net9.0 更不行。
  要 .NET 做音频得锁 NAudio 2.2.1，或干脆用 Python+sounddevice（和 CapsWriter 同栈，本次选择）。
- Python 输出重定向到文件是全缓冲，日志要实时可见得开 `line_buffering`。
- 比较"经过虚拟麦的音频"时，**比较区间必须卡在实际发送的秒数内**并用冲激先定位，
  否则拿后半段静音比语音会得出 r=0.03 的假阴性。
- 接收端收尾时 `srv.close()` 会让 `accept()` 抛 `WinError 10038`，要 catch。

## 10. 仓库状态（2026-10-30 下午落地）

| 仓库 | 内容 | 状态 |
|---|---|---|
| **[`jiushouji-yuyin-gaizao`](https://github.com/openclawzhangchong/jiushouji-yuyin-gaizao)**（新建，public，28 文件 / 20 topics） | 本项目全部实现：APK 源码 + 无 Gradle 出包链 + PC 接收端 + 新机一键部署 + 验收脚本 + README/AGENTS/台账/验收记录 | 已推 `main` |
| [`jiushouji-adb-apk2027`](https://github.com/openclawzhangchong/jiushouji-adb-apk2027)（旧仓库，public） | **只加设备侧结论**：新增 `docs/09-麦克风与PC语音桥.md`，README 的文档索引与"设备速览"各补一行（麦克风从"特性声明可用"升级为"数据面实测可用"） | 已推 `main` |

**拆分原则**：设备本身的事实（采麦参数、`getMinBufferSize` 单位陷阱、熄屏保活、外放自测方法论、
adb 坑）留在设备仓库；"怎么在新电脑上重建这套东西"全归新仓库，且新仓库的 README/AGENTS 都指回旧仓库。

### 推送方式（本环境的坑，不是代码问题）

这台机器 `git push` 会 `curl 55 Send failure: Connection was reset` 或连不上 443，
而 `api.github.com` 只要 0.28 秒 —— 所以用仓库内的 `push_via_api.py` 走 Git Data API
（`blobs → trees → commits → refs`）。过程中踩到并修掉三个真问题：

1. **Git Data API 不接受完全空的仓库**：连 `git/blobs` 都返 `409 Git Repository is empty`。
   脚本改成自动用 Contents API 造一个占位提交，再续上后面的链。
2. **`git ls-tree` 默认 `core.quotePath=true`，会把非 ASCII 路径八进制转义并连引号一起输出**。
   我第一版按它建树，导致远端出现字面叫 `"\345\220\257…bat"` 的乱码文件名。
   改用 `ls-tree -z`（NUL 分隔 + UTF-8 解码），并用 `--base/--force-ref` 从占位提交重建整条链纠正。
   终检：两个仓库 `git/trees?recursive=1` 里**乱码条目 0 个**，
   `启动接收端.bat` / `docs/验收记录.md` / `docs/09-麦克风与PC语音桥.md` 名字全对。
3. `git/ref` 与 `git/refs` 端点要传 `heads/<branch>`；传 `refs/heads/<branch>` 会 404，
   脚本会误判成"分支不存在"去走创建，再撞 `422 Reference already exists`。

本地 `main` 与远端的**内容**逐字节一致（tree hash 相同，例：`cf9ddfd1…`），
但 **commit SHA 必然不同** —— 远端父链多一个空库 bootstrap 提交，而本地 `git fetch`
走不通 github.com，所以本地 `origin/main` 引用会停在旧值、`git status` 显示 ahead 1。
**这不是没推上去**：判成败要比 tree hash，不要比 SHA；
也别用 `git update-ref` 硬把跟踪引用指到远端 SHA，那个对象本地不存在，会直接报错。
等 github.com 可用时再 `git fetch` + `git diff --stat HEAD origin/main`（应为空）+ `git reset --hard origin/main` 对齐历史形状。
构建链的 keystore 在 `C:\android-build\micbridge.keystore`
（口令 `android`，Android 调试标准口令，非机密），`.gitignore` 已排除。

## 11. WiFi 双链路 + PC 端 EXE（2026-10-30 下午，用户追加需求）

**需求**：平板挂在**另一台电脑共享的 WiFi** 上，那台电脑才是实际收音的机器；
所以 PC 端必须打包成免安装 EXE 并上 GitHub。决定：USB 优先、WiFi 兜底；不折腾组网（IP 手填一次）；线保留供电。

**拓扑真相（推翻我今天上午的判断）**：平板网卡是 `192.168.137.224/24`，
但它的包到达本机时源地址是 `192.168.168.38` —— 那台共享 WiFi 的电脑在做 NAT。
所以"跨网段连不上"是**错的**：链路是平板主动连 TCP，只需出站可达。
反方向电脑→平板确实 100% 丢包，代价是**没法自动发现**，电脑 IP 必须手填。

| 实测项 | 结果 |
|---|---|
| 平板→本机 ping（30 次） | min 7.8 / **avg 39.0** / max 243ms，0 丢包，30 次里 3 次 >100ms |
| WiFi 连续推流（拔线状态） | **累计 272.6 秒不间断**，32637 B/s，欠载 0 |
| 心跳 | 接收端回写 136 次并被平板读走 → 真实消费者在场 |
| 语音是否真到了虚拟麦 | 拔线状态下从 CABLE Output 录 6 秒：RMS **-21.4 dBFS**、峰值 0.9904，包络呈说话节奏（-15/-12/-45/-17/-11/-38/-20/-18…），频谱 300-1000Hz 最强 |
| EXE 上线 | 换成 `mic-bridge-receiver.exe --bind 192.168.168.250` 后平板 **约 20 秒自动重连**，32635 B/s、欠载 0、心跳正常 |

### 今天为 WiFi 新写的防护（都已实现并验证）

1. **心跳从"可选"改成"硬要求"**（`PONG_FIRST_MS=10s` / `PONG_TIMEOUT_MS=6s`）——
   起因是 accept 线程里一个 `NameError` 静默死掉，而平板仍报告"已连 USB、32000 B/s"，
   数据全进了黑洞。**TCP 连接成功不等于有人消费**，这条是这个项目最容易骗过人的地方。
2. **`--bind` 不含回环时不下发 `adb reverse`** —— 否则设备侧回环桩"先接受后失败"，
   App 每轮先撞它、永远轮不到 WiFi。
3. **`--recv-bytes 3200`** —— 原来 `recv(65536)` 一次吞掉 2 秒音频，把预缓冲顶到 640ms；
   改完实测 300-340ms。
4. **去掉 `SO_REUSEADDR`** —— Windows 上它允许静默重复绑定，制造过"两个接收端、一个空转刷日志"的假象。
5. **`--bind auto` 随环境变形**：有 adb → 绑 127.0.0.1（不动防火墙）；无 adb → 绑 0.0.0.0（纯 WiFi）。
6. **`setup_windows.ps1 -Go -Firewall`** 加入站规则 `mic-bridge-receiver-5005`（WiFi 必需，否则静默失败）。

### 还没验证的

- `release/mic-bridge-0.5.0.apk`（多了"连上却收不到心跳就翻转链路优先级"）**没装进平板** ——
  当时 `adb install` 赶上设备掉线失败了。**平板现在实跑的是 v0.4.1**。
- "USB 与 WiFi 同时可用时的互拔切换"没做系统性测试（只验证了拔线后 WiFi 继续、以及换接收端进程后自动重连）。
- 平板续航（纯电池撑多久）没测。

### PC 端 EXE

`dist/mic-bridge-receiver.exe`（GitHub Release `v0.5.0` 上的最终版）
**21,075,491 字节，SHA-256 `42e7fdeb4e4ec60d1f5072dc20855eb85bfee6b05258da709506ee501db90d2a`**。

> 发布踩坑两条，都真实发生过：
> 1. **旧 EXE 在跑时 PyInstaller 会 `PermissionError` 写不进 dist**，但脚本不中断，
>    于是我一度把"新启动的进程"当成了新构建 —— 判据是先核对产物**字节数与 sha256**，别信"我刚重新构建过"。
> 2. `gh release upload --overwrite` 这个参数不存在，会静默不上传（远端仍是旧 sha），
>    正确参数是 **`--clobber`**；上传后必须回读 `releases/latest` 的 `.assets[].size/.digest` 对一遍。

同一 Release 里的 `mic-bridge-0.5.0.apk`：20,890 字节，
SHA-256 `3cffc2b0438df00ec38fef1619b70d5af55241ebdf50b86c2fcb4dac402c2b92`。

### 时钟漂移与弹性追赶（最后补上的一处）

只设预缓冲不追赶时，实测 **5 分钟水位从 320ms 漂到 620ms**（平板声卡与电脑声卡约 0.1% 时钟偏差），
最后要靠 `max_water` 一刀切掉整段，延迟表现是"越用越慢然后突然跳一下"。
改成回调里弹性追赶（超过 `water+120ms` 每次多丢一块 20ms）后：
**连续 247 秒水位稳在 280-360ms**，代价 156 次丢块 ≈ 总音频 1.3%（多数来自 WiFi 打嗝后的 TCP 突发补货）。
取代表：宁可丢 20ms 碎片，也不要延迟永久台阶上升。


