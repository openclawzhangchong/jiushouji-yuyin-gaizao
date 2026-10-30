# 旧平板 → Windows 麦克风（mic-bridge）

把一台 **MTK MT6582 / Android 5.1** 的旧平板变成 Windows 能用的真麦克风。
Windows 侧得到录音端点 **`CABLE Output (VB-Audio Virtual Cable)`**，
任何程序（微信/QQ 语音、网页语音输入、Win+H 语音听写、CapsWriter）都能选它当输入设备。

**不用买 USB 麦克风，不用改任何上层软件。**

---

## 这个 Release 里有两个文件

| 文件 | 给谁 | 说明 |
|---|---|---|
| **`mic-bridge-receiver.exe`**（约 21 MB） | **Windows 那台要收音的电脑** | 单文件免安装，**不需要 Python**，自带 PortAudio；**内部还打包了平板的 APK** |
| `mic-bridge-0.5.0.apk`（20.9 KB） | 安卓平板 | 也可以单独装；但**手机不方便下载 APK 时不必单独下**，见下 |

### 手机上装不了 APK？EXE 会自己装

`mic-bridge-receiver.exe` 内置了同版本的 APK。只要它检测到 adb 上有平板在线，就会：

1. 查平板上有没有 `com.zcstudy.micbridge`、版本对不对；
2. 没装或版本旧 → 自动 `adb install -r`（平板上**不需要浏览器、不需要网盘、不需要传文件**）；
3. 装完顺手把**这台电脑的局域网 IP** 通过 intent 推给平板并开始送话，
   连"在平板上手填 IP"这一步都省了。

保护逻辑：平板上版本比 EXE 内置的**更新**时**不降级**，只提示；
已经同版本就跳过；**平板正在推流时不动它**（不会因为"顺手升级"打断你正在用的麦克风）。

```powershell
.\mic-bridge-receiver.exe --install-apk    # 只做一次"安装+配网"然后退出，不启动音频
.\mic-bridge-receiver.exe --no-auto-install # 不希望它碰平板时就关掉这个行为
```

---

## 前置条件（三样，缺一不可）

1. **VB-Cable 虚拟声卡**，必须 **Driver Pack 45 或更新**。
   ⚠️ Pack43 是 2015 年的包，只带 win7 时代驱动，**Win11 装不上**（这个坑踩过）。
   装完**不用重启**就会出现 `CABLE Input` / `CABLE Output`。
2. **平板开 USB 调试并点一次「允许」**（开发者选项入口：设置→关于平板→连点"版本号"7 次）。
   纯 WiFi 长期使用可以之后拔掉线，但第一次授权必须人点。
3. **走 WiFi 的话必须放行入站端口**，否则程序只会一直显示"等设备连"、**不报任何错**：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go -Firewall
   ```
   （仓库里有 `setup_windows.ps1`；它默认是 DRY-RUN，加 `-Go` 才动系统。）

## 三种用法，按你的情况挑一种

**A. 平板插线在这台电脑（最简单，零配置）**
```powershell
.\mic-bridge-receiver.exe
```
检测到 adb → 只绑 127.0.0.1，靠 `adb reverse` 走 USB，**不需要开防火墙**。
延迟实测 **143.9 ms**，连续 500+ 秒零丢包零欠载。

**B. 平板走 WiFi，收音电脑就是这台**
```powershell
.\mic-bridge-receiver.exe                          # 有 adb 时自动下发 reverse
adb shell am start -n com.zcstudy.micbridge/.MainActivity --ez auto true --es lan 192.168.168.250
```

**C. 平板挂在另一台电脑共享的 WiFi 上，收音的是那台电脑（真实使用场景）**
在那台电脑上：装 VB-Cable → 跑 `.\mic-bridge-receiver.exe`。
它没有 adb 也会自动改绑 `0.0.0.0` 进入纯 WiFi 模式。
平板侧把 IP 填那台电脑的局域网地址即可（或先插一次线让 EXE 自动配好）。

> **拓扑说明（重要，别按"必须同网段"去推理）**：实测平板挂在共享 WiFi 的电脑上时，
> 它的包到达本机源地址会变成**那台电脑的局域网 IP**（NAT 后的地址）。
> 链路是平板**主动出站**连 TCP，所以"电脑 ping 不通平板"完全不妨碍它工作。
> 代价只是没法广播/mDNS 自动发现，所以 IP 要填一次（或让 EXE 通过 adb 帮你填）。

---

## 行为约定

- **USB 优先、WiFi 兜底**：先试 `127.0.0.1:5005`（1.2 秒），连不上再试配置的 IP（1.5 秒）。
- **心跳是硬要求**：电脑每 2 秒回写 1 个字节 `P`；平板连上 10 秒内没见到第一个、
  或之后 6 秒没续上，判定这条链路"假通"并换链路。
  为什么必须这样：**TCP 连接成功只代表数据进了对端内核缓冲区，不代表有人消费**——
  本项目真的遇见过接收端线程已死而平板仍显示"已连、速率正常"的情况。
- 音频格式：16000 Hz / 单声道 / PCM16 小端，20ms（1280 字节）一包，满速 **32000 B/s**。
- WiFi 链路自动用更大抖动缓冲（目标 250ms），并有弹性追赶防止平板与电脑声卡约 0.1% 的
  时钟偏差把延迟越推越高。

---

## 实测数字（都是这台真机跑出来的，不是估计）

| 项 | USB | WiFi（拔线状态） |
|---|---|---|
| 上行速率 | 31603–32640 B/s | 31671–32636 B/s |
| 连续时长 | 541 秒不中断 | 365+ 秒不中断 |
| 欠采 / 丢包 | 0 / 0 | 0 / 0（丢块是弹性追赶主动裁的 20ms 碎片） |
| 缓冲水位 | 20–140 ms | 稳定 240–360 ms |
| 端到端延迟 | **143.9 ms**（实测） | 约 300 ms（Windows 段实测值 + 缓冲，未做跨机绝对测量） |
| 断线自愈 | 杀接收端→重启后自动重连 | 换 EXE 进程后约 20–35 秒自动重连 |
| 熄屏续流 | 熄屏 75 秒满速无断档（`PARTIAL_WAKE_LOCK`） | 同机制，未单独长跑 |

**可识别性验收**：让平板自己外放已知中文、再用它自己的麦克风听回来，
经 USB/WiFi → CABLE Output 录下后丢给 CapsWriter 的 Qwen3-ASR，结果逐字正确：
> 「Hello 啊，我是小智啦。声音好听的台湾女孩一枚，超开心认识你耶。最近在忙啥？别忘了给我来点有趣的料哦！」

虚拟声卡本身的透传质量另测：灌 440Hz@0.25 录到 peak **0.2500** 分毫不衰减，
100–6000Hz 分频带能量比全部 **≈1.000**。

---

## 出问题先看这几条

| 现象 | 原因 / 处置 |
|---|---|
| 程序一直显示"等设备连"，平板却说已连 | 十有八九是**防火墙没放行**，或者这台电脑不是平板连的那台。先 `--list` 看设备在不在，再确认 IP |
| 平板显示"已连 USB"但电脑没声音 | 检查 `CABLE Output` 是否被设成了**默认录音设备**；以及是否真的有程序在消费（心跳会暴露这一点） |
| 声音断续、延迟越用越大 | WiFi 打嗝。别调大 `--max-water`，先看 `--recv-bytes` 是否被改回大值 |
| `adb devices` 显示 `offline` | **不等于**"等你点授权"，此时授权框根本不会弹。撤销 USB 调试授权后重开，或重启平板 |
| 平板界面按钮点了没反应 | 看是不是 `--ez auto 1` 这种写法 —— `am` 的 `--ez` **只认 true/false**，写 `1` 会被解析成 false |
| 想彻底卸载平板端 | `adb uninstall com.zcstudy.micbridge` |

---

## 文件校验

```
mic-bridge-receiver.exe   21,095,203 B
sha256 d74f7db0e644a9a416d6e0d8c209e64202335a60cb0e693d5d6276060fbb3ec5

mic-bridge-0.5.0.apk         20,890 B
sha256 3cffc2b0438df00ec38fef1619b70d5af55241ebdf50b86c2fcb4dac402c2b92
```

源码、构建方法（无 Gradle 出包 + PyInstaller 打包命令）、全部实测台账与踩坑清单在仓库：
**`openclawzhangchong/jiushouji-yuyin-gaizao`**。
设备本身的硬件结论在上游仓库 **`openclawzhangchong/jiushouji-adb-apk2027`**。
