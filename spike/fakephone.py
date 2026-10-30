# SPIKE (throwaway) —— 结论出来后可直接删，不作为正式实现
# 作用：冒充"旧平板"，把一个真实语音 WAV 按 20ms/包 的节奏用 UDP 推给 receiver.py
import socket, sys, time, wave

SRC = sys.argv[1] if len(sys.argv) > 1 else r"E:\github项目\yuyin-shuru-trial\test\jfk.wav"
DST = ("127.0.0.1", 5005)
PACK_MS = 20

wf = wave.open(SRC, "rb")
sr, ch, sw = wf.getframerate(), wf.getchannels(), wf.getsampwidth()
raw = wf.readframes(wf.getnframes())
wf.close()
assert ch == 1 and sw == 2, "素材需 16bit 单声道"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
step = sr * 2 * PACK_MS // 1000
click_at = 1000 // PACK_MS  # 第 1 秒处插一个满量程冲激，用来量端到端延迟
frames = [raw[i:i + step] for i in range(0, len(raw), step)]

print(f"素材 {SRC}\n  {sr}Hz {ch}ch {sw*8}bit  总长 {len(raw)/2/sr:.2f}s  包数 {len(frames)}x{PACK_MS}ms")
t0 = time.perf_counter()
click_ts = None
for i, f in enumerate(frames):
    if i == click_at:
        click_ts = time.perf_counter()
        f = b"\xff\x7f" + b"\x00\x00" * (step // 2 - 1)  # 冲激：单个满量程采样
    elif time.perf_counter() - t0 < i * PACK_MS / 1000 - 0.004:
        time.sleep(0.002)
    sock.sendto(f, DST)
sock.sendto(b"EOF\n", DST)
print(f"  冲激发出时刻(相对开始) = {click_ts - t0:.4f}s")
sock.close()
