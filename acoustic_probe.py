#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""声学回环验收：电脑外放已知音频 -> 平板麦克风听进去 -> adb reverse 推回 -> CABLE Output 录下 -> 分析。

不依赖人配合，也不得出"人到底说没说话"这种扯不清的结论（同 xiaole-ptt 的 test_ptt.sh 思路）。
先放 2 秒 1kHz 提示音探路，确认扬声器->麦克风这条声学路径真的通，再放已知中文。
"""
import os, subprocess, sys, time, wave
import numpy as np
import sounddevice as sd

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
DEMO = r"E:\github项目\yuyin-shuru-trial\test\demo.wav"
RECS = r"C:\Users\Administrator\AppData\Local\Temp\jjsound\recv_acoustic.log"
SR = 16000
TOTAL = 45


def play(path_or_tone, secs, label):
    if path_or_tone == "tone":
        t = np.arange(int(SR * secs)) / SR
        x = (0.6 * np.sin(2 * np.pi * 1000 * t) * 32767).astype("<i2")
        data = x
    else:
        w = wave.open(path_or_tone, "rb")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    sd.play(data, samplerate=SR, blocking=True)
    print("  放完 %s (%.1fs)" % (label, len(data) / SR), flush=True)


def main():
    d = sd.query_devices(kind="output")
    print("外放走的默认输出设备: #%s %s" % (d.get("index"), d["name"]), flush=True)
    if "cable" in d["name"].lower():
        print("!! 默认输出就是 CABLE，那这条测试验不到麦克风，先把默认输出改成真扬声器")
        return 2
    print("起接收端（同时从 CABLE Output 录 %ds）" % TOTAL, flush=True)
    rp = subprocess.Popen([PY, os.path.join(HERE, "pc_receiver.py"), "--record", str(TOTAL)],
                          stdout=open(RECS, "w"), stderr=subprocess.STDOUT)
    time.sleep(8)
    print("提示音探路…", flush=True)
    play("tone", 2.0, "1kHz 提示音")
    time.sleep(2)
    print("放已知中文…", flush=True)
    play(DEMO, 0, "demo.wav")
    time.sleep(4)
    rp.wait(timeout=90)

    vp = os.path.join(HERE, "verify.wav")
    if not os.path.exists(vp):
        print("!! 没生成 verify.wav")
        print(open(RECS, encoding="utf-8", errors="replace").read()[-1500:])
        return 1
    w = wave.open(vp, "rb")
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
    print("\nverify.wav %.1fs @%dHz" % (len(x) / SR, w.getframerate()))

    win = int(0.1 * SR)
    env = np.array([np.sqrt(np.mean(x[i:i + win] ** 2)) for i in range(0, len(x) - win, win)])
    print("包络(每0.1s RMS) 最大 %.4f  整段RMS %.5f" % (env.max(), np.sqrt(np.mean(x ** 2))))
    loud = np.where(env > env.max() * 0.25)[0]
    if len(loud):
        print("有声段: %.1fs ~ %.1fs（共 %d 个 0.1s 窗）"
              % (loud[0] * 0.1, (loud[-1] + 1) * 0.1, len(loud)))

    # 1kHz 提示音在哪一段：按窗做 Goertzel
    def g(seg, f):
        n = len(seg)
        if n < 32:
            return 0.0
        k = int(round(n * f / SR)); a = 2 * np.cos(2 * np.pi * k / n)
        p1 = p2 = 0.0
        for v in seg:
            p1, p2 = a * p1 - p2 + v, p1
        return np.sqrt(abs(p1 * p1 + p2 * p2 - a * p1 * p2)) / n

    segs = [(i * 0.1, g(x[i * win:(i + 1) * win], 1000), np.sqrt(np.mean(x[i * win:(i + 1) * win] ** 2)))
            for i in range(len(env))]
    hits = [(t, m, r) for t, m, r in segs if m > 0.02 and r > 0.02]
    print("1kHz 成分显著的窗口: %d 个" % len(hits))
    for t, m, r in hits[:30]:
        print("   t=%.1fs 1kHz幅度=%.4f rms=%.4f" % (t, m, r))
    print("\n接收端尾部日志：")
    print("".join(open(RECS, encoding="utf-8", errors="replace").readlines()[-8:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
