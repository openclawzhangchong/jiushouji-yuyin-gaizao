# MicBridge（麦克风桥）品牌图标资源

深蓝 → 青蓝微渐变圆角方块 + 白色粗黑体「桥」+ 右下角低透明度小字「zc」；16px 一档改用抽象单拱桥符号。

## 设计说明

| 项 | 取值 |
|---|---|
| 底色 | 对角渐变 `#0B223D → #1A8FB8`（左上叠加一层青色柔光，扁平但有层次） |
| 主体字 | 白色「桥」，微软雅黑 Bold，墨迹宽度约占圆角方块 **68%**，视觉中心偏左（`x=0.452`） |
| 16px 符号 | 横桥面 + 半圆拱，纯几何、左右对称、白色；墨迹宽约方块 **62.5%**、高约 50%，居中 |
| 副标 | `zc`，Segoe UI Bold，字号约方块 11.8%，浅青白 `#D6F1FA`、透明度 205/255；**仅 ≥64px 绘制** |
| 圆角方块 | 到画布边缘留白 4.2%，圆角半径 = 边长 22.5%（squircle 观感） |
| 安全边距 | 512px 下「桥」左侧留白约 52px、底部约 96px；zc 距方块右侧约 34px、底部约 30px |

配色意图：深蓝负责“专业/音频设备”，青蓝渐变带一点声波与屏幕感；白色粗字在缩小后仍保持最高反差。
浅色对照版（`micbridge-appicon-alt-light.png`）用同结构 + 深藏青字，供明亮界面/浅色商店页使用。

### 尺寸 → 字形对应表

| 尺寸 | 字形 | zc | 说明 |
|---|---|---|---|
| 16 | **抽象单拱桥符号** | 无 | 汉字 11 笔在 16px 无可读性，改用「一条横桥面 + 一个半圆拱」剪影 |
| 24 | 简化版「桥」 | 无 | 加粗笔画，4× 放大可辨认；汉字能成立的最小一档 |
| 32 | 简化版「桥」 | 无 | 加粗笔画，清晰 |
| 48 | 简化版「桥」 | 无 | 加粗笔画；`zc` 已按阈值移除 |
| 64 | 主版「桥」 | 有 | 第一个带 zc 的尺寸 |
| 128 / 256 / 512 | 主版「桥」 | 有 | 主视觉 |

`zc` 阈值：`ZC_MIN_SIZE = 64`，`size < 64` 一律不绘制。

### 小尺寸策略

- **16px**：`draw_bridge_symbol()` 直接画几何符号——桥面为圆头横条（粗细约 `0.195×` 宽度），下方半圆拱顶接桥面下沿、两端落在同一基线；超采样 8× 后缩到 16px，横条与拱洞都能保留 1–2px 实心白像素。
- **24/32/48/72**：`SMALL_PARAMS` 分档放大字号（0.695–0.71）并用 `MaxFilter` 对字形蒙版做 0.22–0.30px 亚像素膨胀加粗；底色换更实的 `#081A30 → #127096` 提高反差。
- 24 与 32 也试过切符号版对比，4× 下 24px 的「桥」仍可辨认，故保留汉字以维持品牌识别；32px 汉字明显优于符号，确定保留。

## 文件清单

| 文件 | 尺寸 / 内容 | 用途 |
|---|---|---|
| `micbridge-appicon.png` | 512×512 RGBA | 主视觉母版（商店页、文档、README） |
| `micbridge-appicon-256.png` | 256×256 | 大图标（Windows 大图标视图） |
| `micbridge-appicon-128.png` | 128×128 | 中图标 |
| `micbridge-appicon-64.png` | 64×64，含 zc | 文件列表大图标 |
| `micbridge-appicon-48.png` | 48×48 简化版，无 zc | 列表图标 |
| `micbridge-appicon-32.png` | 32×32 简化版，无 zc | 小图标 |
| `micbridge-appicon-24.png` | 24×24 简化版，无 zc | Windows 小图标、托盘 |
| `micbridge-appicon-16.png` | 16×16 抽象桥符号，无 zc | 快捷方式角标 / 标题栏 |
| `micbridge.ico` | 7 帧：16/24/32/48/64/128/256，32bpp | exe、安装器、快捷方式（16 帧为符号版） |
| `micbridge-adaptive-foreground.png` | 108×108 透明前景 | Android 自适应图标 `foreground`，内容实测占 20–86px（安全区 18–90） |
| `micbridge-adaptive-background.png` | 108×108 满幅渐变 | Android 自适应图标 `background`，可被系统裁成任意形状 |
| `ic_launcher_round_mdpi.png` | 48×48 圆形 | Android mdpi 圆形 launcher（简化版「桥」，无 zc） |
| `ic_launcher_round_hdpi.png` | 72×72 圆形 | Android hdpi（简化版「桥」，无 zc） |
| `ic_launcher_round_xhdpi.png` | 96×96 圆形 | Android xhdpi（居中「桥」，无 zc） |
| `ic_launcher_round_xxhdpi.png` | 144×144 圆形 | Android xxhdpi（居中「桥」） |
| `ic_launcher_round_xxxhdpi.png` | 192×192 圆形 | Android xxxhdpi（居中「桥」） |
| `preview-small.png` | 1120×960 | 自查图：16/24/32/48 在浅底与深底下的最近邻 4× 放大（含字形标注）+ 512 圆角遮罩实际观感 |
| `micbridge-appicon-alt-light.png` | 512×512 | 浅色底对照版（可选） |
| `make_icon.py` | 生成脚本 | 一条命令重跑全部产物 |

> Android 命名说明：本仓库 `app/res/` 目前只有 `values/`，没有 mipmap 资源，因此这里按 Android 标准 `ic_launcher_round_<density>.png` 命名（`mdpi 48 / hdpi 72 / xhdpi 96 / xxhdpi 144 / xxxhdpi 192`），未参照也不改动现有工程资源。
> 圆形 launcher 不含 `zc`：方形图右下角的 zc 在圆形裁切下会贴边被切掉，因此圆形版只保留居中的「桥」（白色墨迹最远半径约为圆半径的 77%），保证安全区内不被裁。

## 接入仓库

Windows 安装器 / exe 使用的图标已同步到 `packaging/mic-bridge.ico`（`assets/brand/micbridge.ico` 的副本，覆盖原文件）；`packaging/` 其他文件未改动，`app/res/`、`release/` 也未改动。重跑脚本后若需再次同步：

```powershell
Copy-Item assets/brand/micbridge.ico packaging/mic-bridge.ico -Force
```

## 重跑 / 改字 / 换色

依赖：Python 3 + Pillow（`pip install pillow`）。字体不随仓库分发，脚本在 `C:\Windows\Fonts` 中按顺序查找可用字体，找到即用并把字体名打印出来：

- 中文：`msyhbd.ttc` → `simhei.ttf` → `Dengb.ttf` → `msyh.ttc` → `simsun.ttc`（当前命中 **Microsoft YaHei Bold / msyhbd.ttc**）
- 西文：`segoeuib.ttf` → `arialbd.ttf` → `bahnschrift.ttf` → `calibrib.ttf` → `arial.ttf`（当前命中 **Segoe UI Bold**）

```powershell
python assets/brand/make_icon.py
```

常用改动都集中在脚本顶部常量：

| 想改什么 | 改哪里 |
|---|---|
| 换字（如「桥」→「麥」） | `render()` / `render_adaptive_fg()` 里的字符串 `"桥"`；必要时调整 `FULL_GLYPH_SCALE` |
| 换 zc 文案 | `"zc"` 字符串（两处：主版、自适应前景） |
| 哪些尺寸不画 zc | `ZC_MIN_SIZE` |
| 哪些尺寸用抽象符号 | `SYMBOL_SIZES`（默认 `{16}`）；`SYMBOL_PARAMS` 里是 `(宽度, 笔画粗细, 拱半宽)` 三个比例 |
| 换底色 | `BG_TOP` / `BG_BOT`（主版）、`SM_TOP` / `SM_BOT`（简化版）、`LT_TOP` / `LT_BOT`（浅色版） |
| 字色 / zc 浓度 | `FG`、`ZC`、`ZC_ALPHA` |
| 留白与圆角 | `TILE_INSET`、`TILE_RADIUS` |
| 小尺寸字号与加粗 | `SMALL_PARAMS = {尺寸: (字号比例, 加粗px)}` |
| 换字体 | `CN_FONTS` / `EN_FONTS` 候选列表，或直接改 `CN_PATH` |

脚本会输出字体选择与每帧 ICO 尺寸；实现细节：ICO 为手写的 PNG-in-ICO（Vista+ 格式），每帧是独立绘制的 PNG，不是从 512 缩放而来，因此 16 帧能保持符号版、小帧能保持无 zc。

## 已知局限与改进建议

1. **24px 的「桥」属于“可辨认但偏密”**：4× 放大能读清，1:1 主要靠字形轮廓；若更在意小图标锐利度，可把 24 也加入 `SYMBOL_SIZES`（对比预览见 `preview-small.png`）。
2. 16px 符号已能看出“横桥面 + 单拱”，但拱洞在 16px 只剩 1–2px，若再降到 12/14px 会失去意义。
3. 全部为程序化几何绘制，无手工字距微调；若追求品牌级精细度，建议用矢量源（SVG/AI）逐像素调锚点后再导出位图。
