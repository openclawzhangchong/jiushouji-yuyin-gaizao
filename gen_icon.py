#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 mic-bridge 全套图标：mic-bridge.ico（EXE/快捷方式/安装包用）。

设计：深色圆角方底 + 青绿麦克风与声波 + 右下角琥珀圆徽「zc」。
一次生成多尺寸（16~256），Windows 会按场景挑合适的。
用法：python gen_icon.py   （改设计只改这个文件，重跑即可）
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mic-bridge.ico")
S = 256
BG = (24, 32, 48, 255)          # 深蓝灰底
BG2 = (38, 50, 72, 255)         # 底部渐深
MIC = (45, 212, 191, 255)       # 青绿麦克风
MIC_D = (20, 120, 110, 255)     # 麦克风描边
WAVE = (125, 211, 252, 255)     # 淡蓝声波
BADGE = (245, 158, 11, 255)     # 琥珀圆徽
BADGE_T = (30, 25, 5, 255)      # 徽标上的字色


def font(sz):
    for name in ("arialbd.ttf", "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, sz)
        except OSError:
            continue
    return ImageFont.load_default()


def render(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = size / S

    def r(*v):
        return [x * k for x in v]

    # 圆角方底（上浅下深两段近似渐变）
    d.rounded_rectangle(r(8, 8, 248, 248), radius=48 * k, fill=BG)
    d.rounded_rectangle(r(8, 128, 248, 248), radius=48 * k, fill=BG2)
    d.rounded_rectangle(r(8, 8, 248, 248), radius=48 * k, outline=(70, 90, 120, 255), width=max(1, int(2 * k)))

    # 麦克风头：竖直胶囊
    d.rounded_rectangle(r(104, 44, 152, 136), radius=24 * k, fill=MIC, outline=MIC_D, width=max(1, int(3 * k)))
    # 拾音格栅线
    for y in (70, 86, 102):
        d.line(r(114, y, 142, y), fill=MIC_D, width=max(1, int(3 * k)))
    # U 形支架 + 立柱 + 底座
    d.arc(r(84, 84, 172, 160), start=20, end=160, fill=MIC, width=max(2, int(10 * k)))
    d.line(r(128, 152, 128, 186), fill=MIC, width=max(2, int(10 * k)))
    d.line(r(100, 190, 156, 190), fill=MIC, width=max(2, int(10 * k)))

    # 右侧两道声波弧
    d.arc(r(160, 70, 210, 130), start=-55, end=55, fill=WAVE, width=max(1, int(7 * k)))
    d.arc(r(176, 52, 236, 148), start=-55, end=55, fill=WAVE, width=max(1, int(6 * k)))

    # 右下角「zc」琥珀圆徽（留 2px 深色描边与底分开）
    bx, by, br = 206 * k, 206 * k, 34 * k
    d.ellipse([bx - br - 2 * k, by - br - 2 * k, bx + br + 2 * k, by + br + 2 * k],
              fill=BG)
    d.ellipse([bx - br, by - br, bx + br, by + br], fill=BADGE)
    f = font(int(34 * k)) if size >= 48 else None
    txt = "zc"
    if f is not None:
        bb = d.textbbox((0, 0), txt, font=f)
        d.text((bx - (bb[2] - bb[0]) / 2 - bb[0], by - (bb[3] - bb[1]) / 2 - bb[1]),
               txt, font=f, fill=BADGE_T)
    else:
        # 16/24px 太小放不下字：只留琥珀点作为签名色
        d.ellipse([bx - br * 0.7, by - br * 0.7, bx + br * 0.7, by + br * 0.7], fill=BADGE)
    return im


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = render(256)
    imgs = [base.resize((s, s), Image.LANCZOS) if s != 256 else base for s in sizes]
    imgs[0].save(OUT, sizes=[(s, s) for s in sizes], append_images=imgs[1:])
    print("已生成 %s（%d 个尺寸）" % (OUT, len(sizes)))


if __name__ == "__main__":
    main()
