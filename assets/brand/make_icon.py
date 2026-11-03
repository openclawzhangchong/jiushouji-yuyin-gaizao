#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MicBridge（麦克风桥）品牌图标生成脚本。

一条命令重跑全套产物：
    python assets/brand/make_icon.py

设计：深蓝 → 青蓝对角微渐变圆角方块 + 白色粗黑体「桥」+ 右下角低透明度「zc」。
16px 改用抽象单拱桥符号（汉字 11 笔在该尺寸无可读性）；24–72px 用简化版「桥」；
zc 仅在 64px 及以上绘制。

字体：优先微软雅黑 Bold（msyhbd.ttc），回退 SimHei / 等线 Bold；
西文（zc）优先 Segoe UI Bold，回退 Arial Bold。
"""

import io
import os
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent
FONT_DIR = Path(r"C:\Windows\Fonts")

# ---------- 配色 ----------
# 主版：深海军蓝 -> 青蓝
BG_TOP = (11, 34, 61)
BG_BOT = (26, 143, 184)
GLOW = (94, 210, 231)          # 左上柔光
FG = (255, 255, 255, 255)      # 桥
ZC = (214, 241, 250, 170)       # zc：浅青白、低透明度
# 简化版：更暗更实，保证 16px 白字反差
SM_TOP = (8, 26, 48)
SM_BOT = (18, 112, 150)
# 浅色对照版
LT_TOP = (238, 246, 252)
LT_BOT = (176, 214, 234)
LT_FG = (12, 55, 88, 255)
LT_ZC = (12, 55, 88, 150)

TILE_INSET = 0.042   # 圆角方块到画布边缘留白（约 4.2%）
TILE_RADIUS = 0.225  # 圆角半径 / 边长
SS = 8               # 超采样倍率（小尺寸更平滑）

# 主版字形参数（相对圆角方块内边长）
FULL_GLYPH_SCALE = 0.665
FULL_GLYPH_CX = 0.452
FULL_GLYPH_CY = 0.468
ZC_SCALE = 0.118
ZC_ALPHA = 205

# 简化版按尺寸分档：(字号比例, 加粗像素/最终尺寸)。16px 只能保「密度与反差」，
# 24px 起才勉强辨认字形，因此字号随尺寸递增、加粗在 32px 处封顶避免笔画粘连。
SMALL_PARAMS = {
    16: (0.645, 0.16),
    24: (0.695, 0.22),
    32: (0.710, 0.28),
    48: (0.700, 0.30),
    72: (0.700, 0.30),
}

# 16px 放弃汉字（11 笔无可读性），改用「横桥面 + 半圆拱」抽象符号
SYMBOL_SIZES = {16}
SYMBOL_PARAMS = {16: (0.70, 0.195, 0.50)}   # (视觉宽度, 笔画粗细, 拱半宽)，均为方块内边长比例
ZC_MIN_SIZE = 64   # 小于该尺寸一律不画 zc

CN_FONTS = ["msyhbd.ttc", "simhei.ttf", "Dengb.ttf", "msyh.ttc", "simsun.ttc"]
EN_FONTS = ["segoeuib.ttf", "arialbd.ttf", "bahnschrift.ttf", "calibrib.ttf", "arial.ttf"]


# ---------- 字体 ----------
def pick_font(candidates, probe="桥"):
    """返回 (路径, 字体名)。要求能真正渲染出 probe 的非空字形。"""
    for name in candidates:
        p = FONT_DIR / name
        if not p.exists():
            continue
        try:
            f = ImageFont.truetype(str(p), 64)
        except OSError:
            continue
        if probe:
            m = f.getmask(probe)
            if m.getbbox() is None:
                continue
        return p, name
    raise RuntimeError("找不到可用字体：%s" % candidates)


CN_PATH, CN_NAME = pick_font(CN_FONTS)
EN_PATH, EN_NAME = pick_font(EN_FONTS, probe="zc")


# ---------- 基础绘制 ----------
def diagonal_gradient(size, top, bot, tilt=0.38):
    """左上 -> 右下 的对角线性渐变（小图生成后放大，保证平滑）。"""
    n = 256
    g = Image.new("RGB", (n, n))
    px = g.load()
    for y in range(n):
        for x in range(n):
            t = (x * tilt + y * (1 - tilt)) / (n - 1)
            t = min(1.0, max(0.0, t))
            px[x, y] = (
                int(top[0] + (bot[0] - top[0]) * t),
                int(top[1] + (bot[1] - top[1]) * t),
                int(top[2] + (bot[2] - top[2]) * t),
            )
    return g.resize((size, size), Image.BILINEAR)


def add_glow(img, mask, color=GLOW, strength=90):
    """左上角柔光，制造扁平但有层次的微渐变。"""
    w, h = img.size
    g = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(g)
    r = int(w * 0.62)
    d.ellipse((-int(w * 0.22), -int(w * 0.30), r, r), fill=strength)
    g = g.filter(ImageFilter.GaussianBlur(w * 0.12))
    layer = Image.new("RGBA", (w, h), color + (0,))
    layer.putalpha(g)
    img.alpha_composite(Image.composite(layer, Image.new("RGBA", (w, h), (0, 0, 0, 0)), mask))


def tile_mask(size, inset, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    pad = int(size * inset)
    d.rounded_rectangle((pad, pad, size - pad - 1, size - pad - 1),
                        radius=int(size * radius), fill=255)
    return m


def circle_mask(size):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((0, 0, size - 1, size - 1), fill=255)
    return m


def paste_glyph(img, text, font, cx, cy, fill, dilate=0):
    """以字形墨迹盒的中心定位绘制文字；dilate 为超采样坐标下的膨胀像素半径。"""
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    box = d.textbbox((0, 0), text, font=font)
    ox = cx - (box[0] + box[2]) / 2
    oy = cy - (box[1] + box[3]) / 2
    d.text((ox, oy), text, font=font, fill=255)
    if dilate > 0:
        k = int(dilate) * 2 + 1
        m = m.filter(ImageFilter.MaxFilter(k))
    layer = Image.new("RGBA", (w, h), fill[:3] + (255,))
    layer.putalpha(m.point(lambda v: v * fill[3] // 255))
    img.alpha_composite(layer)


def draw_tile(canvas, variant="full"):
    """在透明画布上画圆角方块底。variant: full / small / light / circleBg"""
    n = canvas.size[0]
    if variant == "small":
        top, bot, glow = SM_TOP, SM_BOT, 60
    elif variant == "light":
        top, bot, glow = LT_TOP, LT_BOT, 70
    else:
        top, bot, glow = BG_TOP, BG_BOT, 90
    mask = tile_mask(n, TILE_INSET, TILE_RADIUS)
    bg = diagonal_gradient(n, top, bot).convert("RGBA")
    if glow:
        add_glow(bg, mask, color=GLOW if variant != "light" else (255, 255, 255), strength=glow)
    canvas.paste(bg, (0, 0), mask)
    return mask


# ---------- 16px 抽象桥符号 ----------
def draw_bridge_symbol(img, n, inner, size, fill=FG):
    """横桥面 + 下方半圆拱，几何对称、笔画粗。16px 一档放宽到 72% 宽度保证剪影清晰。"""
    w_ratio, t_ratio, r_ratio = SYMBOL_PARAMS.get(size, (0.65, 0.155, 0.415))
    d = ImageDraw.Draw(img)
    u = inner * w_ratio       # 视觉宽度
    t = u * t_ratio           # 笔画粗细
    R = u * r_ratio           # 拱半宽
    cx = n * 0.5
    cy = n * 0.5
    top = cy - (t + R) / 2    # 整体垂直居中
    # 桥面：两端圆头的横条
    d.rounded_rectangle((cx - u / 2, top, cx + u / 2, top + t),
                        radius=t / 2, fill=fill)
    # 半圆拱：顶端正接桥面下沿，两端落在同一基线
    yc = top + t + R
    d.arc((cx - R, yc - R, cx + R, yc + R), 180, 360,
          fill=fill, width=int(round(t)))


# ---------- 主渲染 ----------
def render(size, variant="full", shape="tile"):
    """variant: full / small / light；shape: tile（圆角方） / circle（安卓圆形）。"""
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    if shape == "circle":
        mask = circle_mask(n)
        bg = diagonal_gradient(n, SM_TOP if variant == "small" else BG_TOP,
                               SM_BOT if variant == "small" else BG_BOT).convert("RGBA")
        img.paste(bg, (0, 0), mask)
    else:
        draw_tile(img, variant)

    small = variant == "small"
    inner = n * (1 - 2 * TILE_INSET)   # 圆角方块内边长

    if small:
        if size in SYMBOL_SIZES:
            draw_bridge_symbol(img, n, inner, size)
        else:
            scale, dil = SMALL_PARAMS.get(size, (0.70, 0.30))
            font = ImageFont.truetype(str(CN_PATH), int(inner * scale))
            paste_glyph(img, "桥", font, n * 0.5, n * 0.492, FG,
                        dilate=max(1, int(round(dil * SS))))
    else:
        # 圆形 launcher 的 zc 会贴到裁切边缘，故圆形版只保留「桥」并居中
        circle = shape == "circle"
        scale = 0.685 if circle else FULL_GLYPH_SCALE
        font = ImageFont.truetype(str(CN_PATH), int(inner * scale))
        fg = LT_FG if variant == "light" else FG
        cx = n * (0.5 if circle else FULL_GLYPH_CX)
        cy = n * (0.5 if circle else FULL_GLYPH_CY)
        paste_glyph(img, "桥", font, cx, cy, fg)
        if not circle and size >= ZC_MIN_SIZE:
            # 右下 zc
            zc_font = ImageFont.truetype(str(EN_PATH), int(inner * ZC_SCALE))
            zc_fill = LT_ZC if variant == "light" else ZC[:3] + (ZC_ALPHA,)
            zbox = ImageDraw.Draw(img).textbbox((0, 0), "zc", font=zc_font)
            zx = n - n * TILE_INSET - n * 0.066 - (zbox[2] - zbox[0]) / 2
            zy = n - n * TILE_INSET - n * 0.058 - (zbox[3] - zbox[1]) / 2
            paste_glyph(img, "zc", zc_font, zx, zy, zc_fill)

    if size >= 128:
        # 大尺寸才加极细内描边，避免小图标出现杂边
        d = ImageDraw.Draw(img)
        pad = int(n * TILE_INSET)
        d.rounded_rectangle((pad, pad, n - pad - 1, n - pad - 1),
                            radius=int(n * TILE_RADIUS), outline=(255, 255, 255, 26),
                            width=max(1, int(n * 0.0025)))

    return img.resize((size, size), Image.LANCZOS)


def render_adaptive_fg(size=108):
    """108x108 透明前景，内容收在中央 66% 安全区内。"""
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    safe = n * 0.66
    font = ImageFont.truetype(str(CN_PATH), int(safe * 0.80))
    paste_glyph(img, "桥", font, n * 0.452, n * 0.478, FG)
    zc_font = ImageFont.truetype(str(EN_PATH), int(n * 0.082))
    zbox = ImageDraw.Draw(img).textbbox((0, 0), "zc", font=zc_font)
    zx = n * 0.5 + safe * 0.5 - n * 0.022 - (zbox[2] - zbox[0]) / 2
    zy = n * 0.5 + safe * 0.5 - n * 0.022 - (zbox[3] - zbox[1]) / 2
    paste_glyph(img, "zc", zc_font, zx, zy, ZC[:3] + (ZC_ALPHA,))
    return img.resize((size, size), Image.LANCZOS)


def render_adaptive_bg(size=108, variant="full"):
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    top, bot = (BG_TOP, BG_BOT)
    img.paste(diagonal_gradient(n, top, bot).convert("RGBA"), (0, 0))
    # 满幅柔光，允许被系统裁成任意形状
    add_glow(img, Image.new("L", (n, n), 255), color=GLOW, strength=95)
    return img.resize((size, size), Image.LANCZOS)


# ---------- ICO（手写多帧，确保每帧独立图） ----------
def write_ico(path, frames):
    """frames: [(size, PIL.Image)] -> Vista+ PNG-in-ICO。"""
    payloads = []
    for size, im in frames:
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        payloads.append((size, buf.getvalue()))
    n = len(payloads)
    head = struct.pack("<HHH", 0, 1, n)
    entries, body, offset = b"", b"", 6 + 16 * n
    for size, png in payloads:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        body += png
        offset += len(png)
    Path(path).write_bytes(head + entries + body)


def read_ico_sizes(path):
    data = Path(path).read_bytes()
    _, kind, count = struct.unpack("<HHH", data[:6])
    out = []
    for i in range(count):
        e = data[6 + 16 * i: 6 + 16 * (i + 1)]
        w, h = e[0], e[1]
        out.append((w or 256, h or 256, struct.unpack("<H", e[4:6])[0]))
    return kind, out


# ---------- 预览图 ----------
def build_preview(imgs):
    W, H = 1120, 960
    canvas = Image.new("RGB", (W, H), (236, 238, 242))
    d = ImageDraw.Draw(canvas)
    label = ImageFont.truetype(str(CN_PATH), 20)
    small_label = ImageFont.truetype(str(CN_PATH), 17)

    sizes = [16, 24, 32, 48]
    d.text((40, 22), "MicBridge · 小尺寸可读性自查（最近邻 4 倍放大，非平滑缩放）",
           font=label, fill=(30, 36, 48))

    def mark(s):
        return "抽象桥符号" if s in SYMBOL_SIZES else "汉字「桥」"

    for row, (bg, title, row_y) in enumerate([
            ((247, 248, 250), "浅色桌面背景", 76),
            ((32, 36, 42), "深色桌面背景", 372)]):
        fg = (40, 46, 56) if row == 0 else (228, 232, 240)
        d.text((40, row_y - 28), title, font=small_label, fill=fg)
        d.rounded_rectangle((40, row_y, W - 40, row_y + 268), radius=14, fill=bg)
        x = 68
        for s in sizes:
            d.text((x, row_y + 12), "%dpx" % s, font=small_label, fill=fg)
            d.text((x, row_y + 36), mark(s), font=small_label, fill=(120, 130, 145) if row == 0 else (150, 160, 175))
            im = imgs[s].resize((s * 4, s * 4), Image.NEAREST)
            canvas.paste(im, (x, row_y + 66), im)
            x += s * 4 + 52

    # 512 主视觉在浅底/深底下的圆角遮罩效果
    top = 700
    d.text((40, top - 28), "512px 主视觉（圆角遮罩实际观感）", font=small_label, fill=(40, 46, 56))
    d.rounded_rectangle((40, top, W - 40, H - 24), radius=14, fill=(247, 248, 250))
    big = imgs[512].resize((180, 180), Image.LANCZOS)
    canvas.paste(big, (70, top + 30), big)
    dark = Image.new("RGB", (180, 180), (24, 28, 34))
    dark.paste(big, (0, 0), big)
    canvas.paste(dark, (300, top + 30))
    d.text((530, top + 60),
           "左：浅底桌面 · 右：深底桌面\n圆角外为透明，Windows 快捷方式 / Android 均按此安全边距裁剪",
           font=small_label, fill=(90, 98, 110), spacing=10)
    return canvas


# ---------- 主流程 ----------
def main():
    produced = []

    big = {s: render(s, "full") for s in (512, 256, 128, 64, 48)}
    small = {s: render(s, "small") for s in (16, 24, 32)}

    for s, im in big.items():
        name = "micbridge-appicon.png" if s == 512 else "micbridge-appicon-%d.png" % s
        im.save(OUT / name)
        produced.append(name)
    for s, im in small.items():
        im.save(OUT / ("micbridge-appicon-%d.png" % s))
        produced.append("micbridge-appicon-%d.png" % s)

    # 浅色对照版（可选）
    render(512, "light").save(OUT / "micbridge-appicon-alt-light.png")
    produced.append("micbridge-appicon-alt-light.png")

    # 多尺寸 ICO：16/24/32 简化版，48 以上主版
    frames = [(16, small[16]), (24, small[24]), (32, small[32]),
              (48, big[48]), (64, big[64]), (128, big[128]), (256, big[256])]
    write_ico(OUT / "micbridge.ico", frames)
    produced.append("micbridge.ico")

    # Android 自适应
    render_adaptive_fg(108).save(OUT / "micbridge-adaptive-foreground.png")
    render_adaptive_bg(108).save(OUT / "micbridge-adaptive-background.png")
    produced += ["micbridge-adaptive-foreground.png", "micbridge-adaptive-background.png"]

    # Android 圆形 launcher（density 命名）
    for density, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        im = render(px, "full" if px >= 96 else "small", shape="circle")
        im.save(OUT / ("ic_launcher_round_%s.png" % density))
        produced.append("ic_launcher_round_%s.png" % density)

    # 预览
    build_preview({**big, **small}).save(OUT / "preview-small.png")
    produced.append("preview-small.png")

    kind, ico_sizes = read_ico_sizes(OUT / "micbridge.ico")
    print("字体：中文 %s / 西文 %s" % (CN_NAME, EN_NAME))
    print("ICO type=%d 帧：" % kind, ico_sizes)
    for name in produced:
        p = OUT / name
        print("  %-36s %s" % (name, Image.open(p).size if p.suffix == ".png" else p.stat().st_size))


if __name__ == "__main__":
    main()
