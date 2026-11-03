# 交接说明（HANDOVER）

> 交接时间：2026-11-03。整理前 `main` = `36c8bd1`，最新 tag = `v0.7.2`；本次整理提交 `ac0ae8a`（只加本文与 README 图标，未改代码）。
> **动手前先读 [`AGENTS.md`](../AGENTS.md) 的硬约束**；本文只讲现状、习惯、构建与发布，不重复那 60 多条踩坑表。
> 仓库内详细变更正文统一在 [`RELEASE_NOTES.md`](../RELEASE_NOTES.md)，本文不复述长文。

---

## 1. 一句话定位与目录速览

把旧 Android 手机/平板变成 Windows 能用的真麦克风：设备采麦 → USB（`adb reverse`）或 WiFi TCP →
`pc_receiver.py` → VB-Cable 的 `CABLE Input` → Windows 出现录音端点 `CABLE Output`，供任意上层软件选用。

当前有两条 Android 产品线并存：**legacy 0.5.0（旧机首选）** 与 **modern 0.6.2-a16（Android 16 变体）**；
Windows 侧是 **0.7.2 per-user 安装包**，托盘常驻、无控制台窗口。

| 路径 | 是什么 |
|---|---|
| `app/` | legacy Android 源码：`AndroidManifest.xml`、`src/`（Bridge/MainActivity）、`res/values/` |
| `app/src-modern/` | modern 变体覆盖层：独立 Manifest（包名 `.a16`）、MainActivity、自适应图标资源 |
| `build.sh` | legacy 出包链（`aapt2 → javac → d8 → zipalign → apksigner`），产物进 `out/` 与 `release/` |
| `build_android16.sh` | modern 出包链（targetSdk 36），产物进 `out-a16/` 与 `release/mic-bridge-a16-*.apk` |
| `pc_receiver.py` | Windows 接收端主程序；**版本号唯一常量 `APP_VER` 在这里** |
| `packaging/` | 当前发布用的 per-user 安装链：`.spec`、`.iss`、`version_info.txt`、`build_installer.ps1`、图标、中文语言文件 |
| `installer/` | 早期 admin 版安装链（装 Program Files），保留但**不是当前发布路径** |
| `release/` | 版本化 APK 正式产物；历史版本一律不删 |
| `assets/brand/` | 品牌图标母版、多尺寸 PNG/ICO、Android 自适应图标、生成脚本 |
| `docs/` | 验收记录与各版本专题说明；本文件是交接入口 |
| `spike/` | 丢弃型实验脚本，结论已冻结，别当实现参考 |
| `dist/`、`build_tmp/`、`out/`、`out-a16/`、`artifacts/` | **生成物，不入库**（已在 `.gitignore`） |

根目录另有 `setup_windows.ps1`（新机环境，默认 DRY-RUN）、`启动接收端.bat`、`run_selftest.sh`、
`gen_icon.py`（旧版托盘/EXE 图标生成器，与 `assets/brand/make_icon.py` 不是同一套）。

---

## 2. 维护者习惯与硬规矩

以下是从提交历史、发布记录和本次维护工作中核实出来的，**不是建议**。

| 领域 | 规则 | 依据 / 后果 |
|---|---|---|
| 沟通 | 中文优先；先给结论，再给必要细节；不要铺垫和营销式长文 | 全部文档、提交信息、Release 正文均为中文短句 |
| 构建 | **必须在本机完成，不上云、不加 CI**；工具链固定在纯 ASCII 路径 `C:\android-build` | `build.sh` / `build_android16.sh` 顶部硬编码；`aapt2` 遇中文路径会 stat 失败 |
| 旧版 APK | `release/mic-bridge-0.5.0.apk` **绝不能删除或覆盖**，它必须是旧机首选推荐；新版只能以独立变体（`.a16` 包名 + 独立文件名）并存 | README、RELEASE_NOTES 与 `.gitignore` 的 `!release/*.apk` 都以此为前提；`build.sh` 已存在同名文件时默认拒绝覆盖，只有 `FORCE_RELEASE=1` 才放行 |
| 静默 | 任何控制台黑框、模态框、抢焦点弹窗都不可接受；后台 `adb`/`netsh` 子进程必须 `CREATE_NO_WINDOW`，二次启动静默退出 | v0.7.1 专项修复；v0.7.2 回归抽样 22/22 次可见窗口为 0 |
| 版本 | Windows 版本号单一来源是 `pc_receiver.py` 的 `APP_VER`；改版必须同步 `packaging/version_info.txt`、`packaging/mic-bridge.iss`、`packaging/build_installer.ps1` 的默认 `-Version` | 四处在 v0.7.2 均为 0.7.2；漏一处就会出现 exe 属性、安装包名、托盘显示互相对不上 |
| 发版 | 每次发版同时做三件事：更新 `RELEASE_NOTES.md`、打 **annotated tag**、发 GitHub Release 并挂资产 | `v0.7.1` / `v0.7.2` 都是 annotated tag；`v0.5.0` / `v0.6.0` / `v0.7.0` 是轻量 tag（历史遗留，不要模仿） |
| 改动粒度 | 小步提交、可回滚；不顺手动无关文件、不格式化全仓 | 提交历史按 `feat(...)` / `fix(...)` / `docs(...)` / `chore(...)` 拆分 |
| 提交 | **逐路径 `git add`，禁止 `git add -A`**；不 force push、不 amend、不 reset 别人的提交 | 本仓库历史上多次因整树 add 混入无关文件 |
| 未提交改动 | 工作区里用户的 `AGENTS.md`、`PLAN.md`、`test_*.py` 改动必须原样保留，不覆盖、不顺手 stage | 本次交接时这些文件仍处于 modified/untracked 状态 |
| 产物 | EXE / 安装包 / APK 二进制不进 git（`dist/`、`build_tmp/` 已忽略），走 GitHub Release；APK 只把版本化正式包放 `release/` | 仓库体积与 Release 资产分工 |

---

## 3. 版本演进

详细正文只看 [`RELEASE_NOTES.md`](../RELEASE_NOTES.md)，下表只做索引。

| 版本 | 日期 | 新增 | 修复 | 注意 |
|---|---|---|---|---|
| `v0.5.0` | 2026-10-30 | 无（功能与 0.4.1 一致） | 旧机长跑 500+ 秒零丢包、端到端 143.9 ms，消除 CPU 打嗝断续 | **旧机优化版、旧机首选**；不要用 `.a16` 替换它 |
| `v0.6.0` | 2026-10-30 | 接收端改系统托盘常驻、无窗口；右键切 USB⇄WiFi / 看日志；中文 Inno 安装包 | 重复启动不再静默假死；安装包 `isreadme` 静默安装报错 | 平板端仍是 0.5.0，本版只动 Windows |
| `v0.6.1` / `v0.6.2` | 2026-11-02/03 | modern 变体（targetSdk 36、包名 `.a16`、可与 legacy 并存）；品牌 launcher 图标 | 加入 16KB 页对齐校验 | **只有 APK 文件，没有 git tag、没有独立 GitHub Release**；0.6.2 是图标定稿后重出（VC11） |
| `v0.7.0` | 2026-10-31 | 实体麦自动兜底（托盘黄灯）；品牌图标；安装器开机自启任务 | — | 兜底选麦按实测 RMS，不按设备顺序 |
| `v0.7.1` | 2026-11-03 | 无（只做安静化） | 全链路消除命令行黑框；诊断日志改 `notepad.exe`；二次启动静默 `exit=3`；adb 探测指数退避，10 次失败后停 | 覆盖安装即可，快捷方式与自启项无需重配 |
| `v0.7.2` | 2026-11-03 | 托盘菜单显示 `版本 0.7.2`；「重新扫描设备」「重启程序」 | 修 `rescan` 标志被 `pop` 删键导致下一轮 `KeyError` | 当前最新；重启走 `--restart` 交接进程，绝不产生双实例 |

---

## 4. 当前状态（交接点）

- **分支**：`main`；整理前 HEAD `36c8bd1`，本次交接提交 `ac0ae8a`（README 图标 + 本文件），当时与 `origin/main` 一致；此后以 `git log -1` 为准。
- **最新 tag**：`v0.7.2`（annotated，tag 对象指向提交 `4b4af67`）。`main` 比 tag 多若干纯文档提交（0.7.2 补记与本交接文档），均未改代码。
- **最新 Release**：`v0.7.2`，资产三件：
  `mic-bridge-0.5.0.apk`（20,890 B）、`mic-bridge-a16-0.6.2.apk`（95,329 B）、
  `mic-bridge-setup-peruser-0.7.2.exe`（21,313,146 B）。
- **用户机器已装**：接收端 `0.7.2`，per-user 安装，默认落在 `%LOCALAPPDATA%\Programs\mic-bridge`；
  平板端按旧机/新机分别装 0.5.0 或 0.6.2-a16。
- **工作区未提交**：`AGENTS.md`、`PLAN.md`、`test_auto_install.py` 为 modified，`test_freq_shift.py` 未跟踪。
  这些是用户自己的改动，接手时不要覆盖或吞掉。

| 分支 | 与 main 的关系 | 是什么 | 处置建议 |
|---|---|---|---|
| `feat/android16-build` | 分支领先 0（未合并提交 0，已全部在 main 历史里） | A16 modern 变体开发过程 | 可删；删前 `git branch -d` 确认已并入 |
| `feat/win-install-port` | 分支领先 0（未合并提交 0，已全部并入） | per-user 安装包移植过程 | 可删；同上 |
| `feat/windows-install-autostart` | 分支领先 8（未合并提交 8，已分叉） | 早期 Windows 安装版实现（admin 安装、HKCU Run 自启、onefile），已被 main 的 per-user 链路取代 | **保留作备份，不要合进 main**；确认不再需要后再删 |
| `chore/a16-icon-sync` | 分支领先 0（未合并提交 0，已并入） | 图标定稿与 0.6.2 重出 | 可删 |
| `fix/silent-foreground` | 分支领先 0（未合并提交 0，已并入） | v0.7.1 消黑框过程 | 可删 |

> 表中只记「分支领先 main」的未合并提交数（判断能不能删就看它）；`main` 领先多少会随每次文档提交递增，不写死，需要时用 `git rev-list --count origin/main..<branch>` 现查。

---

## 5. 构建方法

### 5.1 Android legacy（`build.sh`）

- 工具链：Git Bash；JDK 17 `C:\android-build\jdk17`；build-tools 34 解出的 `C:\android-build\android-14`；
  Platform 21 解出的 `C:\android-build\android-5.0.1`；签名 `C:\android-build\micbridge.keystore`（alias `micbridge`）。
- 命令：`VER=0.5.0 VC=8 bash build.sh`。
- 产物：`out/`（中间物）、根目录 `mic-bridge.apk`、`release/mic-bridge-<VER>.apk`。
- 红线：`release/` 同名文件默认拒绝覆盖；产物会用 `aapt2 dump badging` 自证 versionCode/versionName，
  不一致直接失败。不要为 modern 的需求去改 `app/src/`、`app/AndroidManifest.xml`、`build.sh`。

### 5.2 Android modern（`build_android16.sh`）

- 工具链：同一 JDK 17 与 keystore；build-tools 36.0.0 解出的 `C:\android-build\android-16`；
  Platform 36 解出的 `C:\android-build\android-36`。缺工具链时脚本顶部有官方下载地址与 SHA-1。
- 命令：`VER=0.6.2 VC=11 bash build_android16.sh`。
- 产物：`out-a16/`、`release/mic-bridge-a16-<VER>.apk`；包内 versionName 为 `<VER>-a16`，
  包名 `com.zcstudy.micbridge.a16`，minSdk 21 / targetSdk 36。
- 机制：编译 `app/src-modern/java` + `app/src` 里除 `MainActivity.java` 外的共用类；
  脚本自证包名、versionCode、targetSdk 36；`zipalign -P 16` 做 16KB 页对齐。
- 红线：改 modern 不得动 legacy 的 `app/src/`、`app/AndroidManifest.xml`、`build.sh`；
  所有 modern 差异放 `app/src-modern/`。

### 5.3 Windows per-user 安装包（`packaging/`）

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1
# 可选：-Version 0.7.3、-Sign、-SkipExe、-Python <path>
```

- 链：`.venv\Scripts\python.exe` → PyInstaller **onedir、关 UPX**（`mic_bridge_receiver.spec`）
  → `dist\windows\Jiushouji-Mic\` → `ISCC.exe /DAppVersion=<ver> packaging\mic-bridge.iss`
  → `dist\windows\mic-bridge-setup-peruser-<ver>.exe`。
- 安装器：`PrivilegesRequired=lowest`，装到 `%LOCALAPPDATA%\Programs\mic-bridge`，全程不弹 UAC；
  开机自启是「启动」文件夹快捷方式，不写 `HKCU\...\Run`、不建服务；
  随带 `release/mic-bridge-0.5.0.apk`；VB-Cable 只检测并提示，不内嵌。
- `-Sign` 是可选的：需要 `MICBRIDGE_PFX` + `MICBRIDGE_PFX_PASS`，或 `MICBRIDGE_SIGN_THUMBPRINT`，
  且本机有 `signtool.exe`；没有证书就保持未签名（自用可接受 SmartScreen 提示）。
- `build_installer.ps1` **必须保持纯 ASCII**：Windows PowerShell 5.1 会把无 BOM 的 UTF-8 当 GBK 读。
- `installer/` 是旧的 admin 安装链，仅作历史参考，不要从这里发新版。

### 5.4 版本号同步点

改 Windows 版本时，以下四处必须一起改，改完用 `Select-String APP_VER` / 打开 exe 属性核对：

1. `pc_receiver.py` → `APP_VER`
2. `packaging/version_info.txt` → `filevers` / `prodvers` / `FileVersion` / `ProductVersion`
3. `packaging/mic-bridge.iss` → `#define AppVersion`
4. `packaging/build_installer.ps1` → `param([string]$Version = ...)`

---

## 6. 图标资产（`assets/brand/`）

- 主视觉：深蓝→青蓝渐变圆角方块 + 白色粗体「桥」+ 右下角浅青 `zc`；**16px 改用抽象单拱桥符号**。
- 尺寸 → 字形：16px 抽象符号（无 zc）；24/32/48 简化「桥」（无 zc）；**64px 起才是主版含 zc**
  （`ZC_MIN_SIZE = 64`）。
- 核心文件：`micbridge-appicon.png`（512 母版）、`-256/-128/-64/-48/-32/-24/-16.png`、
  `micbridge.ico`（16/24/32/48/64/128/256 七帧）、`micbridge-adaptive-foreground.png`、
  `micbridge-adaptive-background.png`、`ic_launcher_round_{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}.png`、`make_icon.py`。
- **不入库**（`.gitignore` 明确忽略）：`preview-small.png`、`micbridge-appicon-alt-light.png`。
  已核实 `git ls-files assets/brand` 共 18 个文件入库，上述两个只在本地。
- 重新生成：`python assets/brand/make_icon.py`（依赖 Pillow；字体从 `C:\Windows\Fonts` 自动挑选，
  优先微软雅黑 Bold / Segoe UI Bold）。
- Windows 取用：`packaging/mic-bridge.ico` 是 `micbridge.ico` 的副本，同时用于
  PyInstaller `icon=`、Inno `SetupIconFile=`、快捷方式 `IconFilename=`。换图后重新复制：
  `Copy-Item assets/brand/micbridge.ico packaging/mic-bridge.ico -Force`。
- Android 取用：modern 资源在 `app/src-modern/res/`：
  `drawable-nodpi/ic_launcher_foreground.png`、`drawable-nodpi/ic_launcher_background.png`、
  `mipmap-anydpi-v26/ic_launcher_round.xml`、五个密度的 `mipmap-*/ic_launcher_round.png`。
- 改字/换色/换 zc 阈值都集中在 `make_icon.py` 顶部常量，详见 `assets/brand/README.md`。

---

## 7. 已知待验证 / 未完成

- **A16 版已在 Android 12 真机验证通过（见实测记录），Android 16 仍未验证**：
  0.6.2 / 0.6.3-a16 在 realme RMX3161（Android 12 / API 31）上完成安装、联调、截图与息屏复测，
  记录见 `docs/real-device-tests/2026-11-03-realme-RMX3161-android12/README.md`。
  期间发现并修复了「Android 11+ 息屏后录音被判 silenced」的问题（0.6.3 加 microphone 前台服务，
  仅改 `app/src-modern/`）。**Android 16（API 36）真机仍无运行记录**，真机验证前不要对外称"已支持 Android 16"。
- **安装包未代码签名**：自用场景接受 SmartScreen 提示；要分发需补证书并走 `-Sign`。
- **`platform-tools` 未内置**：仓库根目录当前没有 `platform-tools/`，`mic_bridge_receiver.spec`
  只在目录存在时才打包 adb。分发前需补齐 `adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll`。
  注意该目录目前**不在** `.gitignore` 里（README 旧的"已 gitignore"说法与现状不符），
  放入二进制时不要整树 add。
- **adb 探测会自动停**：连续 10 次失败后停止主动探测，需要用户在托盘点「重新扫描设备（连接平板）」；
  拔插/授权后没反应先看这里，不是坏了。
- 平板端开机自启/常驻防杀仍未做；端到端绝对延迟、30 分钟熄屏 soak、音源正式 A/B 也未做
  （详见 `AGENTS.md` §5 与 README「已知未完成」）。

---

## 8. 发布流程清单

1. 确认改动范围只涉及本次目标；不要顺手动无关文件。
2. 改 Windows 版本：同步 §5.4 的四处，并确认 `APP_VER` 是唯一来源。
3. 需要出 APK 时：
   legacy `VER=<ver> VC=<vc> bash build.sh`；modern `VER=<ver> VC=<vc> bash build_android16.sh`。
   确认产物出现在 `release/`，且旧 APK 未被覆盖。
4. 出安装包：`powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1 -Version <ver>`；
   核对 exe 属性里的 ProductVersion / FileVersion 和产物字节数、sha256。
5. 跑回归：`python test_auto_install.py`；改过移频则跑 `python test_freq_shift.py`；
   涉及接收端行为时按 `AGENTS.md` §4 做端到端验收。
6. 更新 `RELEASE_NOTES.md`（新增/修复/注意三块），README 只改确实过时的段落。
7. **逐路径** `git add` 本次文件（不要把用户的 `AGENTS.md`、`PLAN.md`、`test_*.py` 混进来），
   中文 conventional commit，提交后 `git push origin main`。
8. 打 annotated tag：`git tag -a v<ver> -m "v<ver> — <一句话>"`，`git push origin v<ver>`。
9. 发 Release：`gh release create v<ver> --title "v<ver> — <标题>" --notes-file RELEASE_NOTES.md`，
   挂上安装包与对应 APK（旧机 0.5.0 必须继续可下载）。
10. 回读核对：`gh release view v<ver> --json assets`，确认文件名、大小、digest 都对；
    再确认 `origin/main` 与本地 HEAD 一致。
