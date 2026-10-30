# SPIKE (throwaway) —— 端到端验证：冒充手机的 UDP 流 -> CABLE Input -> CABLE Output 采集 -> 量化
# 跑法: python probe_pc.py [wav] [取前几秒] [采集设备] [播放设备] [latency] [blocksize]
import subprocess, sys, time, wave, os, socket
import numpy as np
import sounddevice as sd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else r"E:\github项目\yuyin-shuru-trial\test\jfk.wav"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
CAP_DEV = int(sys.argv[3]) if len(sys.argv) > 3 else 9
PLAY_DEV = int(sys.argv[4]) if len(sys.argv) > 4 else 15
LAT = None if len(sys.argv) <= 5 or sys.argv[5] == "default" else (
    sys.argv[5] if sys.argv[5] in ("low", "high") else float(sys.argv[5]))
BLOCK = int(sys.argv[6]) if len(sys.argv) > 6 else 256
SR = 16000
PACK_MS, CLICK_S = 20, 1.0

wf = wave.open(SRC, "rb")
assert wf.getnchannels() == 1 and wf.getsampwidth() == 2, "素材需 16bit 单声道"
raw = wf.readframes(int(wf.getframerate() * SECS))
wf.close()

chunks = []


def incb(indata, frames, t, status):
    chunks.append(indata.copy())


CAP_S = SECS + 3
rp = subprocess.Popen([sys.executable, os.path.join(HERE, "receiver.py"),
                       str(PLAY_DEV), str(CAP_S + 6), str(BLOCK),
                       sys.argv[5] if len(sys.argv) > 5 else "default"],
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(0.8)

with sd.InputStream(samplerate=SR, channels=1, dtype="float32", device=CAP_DEV,
                    blocksize=BLOCK, latency=LAT, callback=incb):
    t_cap = time.perf_counter()
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    step = SR * 2 * PACK_MS // 1000
    frames_ = [raw[i:i + step] for i in range(0, len(raw), step)]
    click_i = int(CLICK_S * 1000 / PACK_MS)
    t_click = None
    for i, f in enumerate(frames_):
        while time.perf_counter() - t_cap < i * PACK_MS / 1000:
            time.sleep(0.0005)
        if i == click_i:
            t_click = time.perf_counter()
            f = b"\xff\x7f" + b"\x00\x00" * (step // 2 - 1)
        u.sendto(f, ("127.0.0.1", 5005))
    u.sendto(b"EOF\n", ("127.0.0.1", 5005))
    u.close()
    while time.perf_counter() - t_cap < CAP_S:
        time.sleep(0.05)

out = rp.communicate(timeout=40)[0]
mono = np.vstack(chunks)[:, 0] if chunks else np.zeros(0, np.float32)
n_have = len(mono)
print(f"[采集] {n_have/SR:.2f}s  device#{CAP_DEV} block={BLOCK} latency={LAT or 'default'}")

k = int(np.argmax(np.abs(mono)))
lat_ms = (t_cap + k / SR - t_click) * 1000

# 严格保真度：源信号与采集做 FFT 互相关找最佳对齐，再算重叠段皮尔逊 r
seg = mono[int(CLICK_S * SR) + 800:]
a = np.frombuffer(raw[:int(SR * SECS)], dtype="<i2").astype(np.float64) / 32768
m = min(len(seg), len(a))
if m > 0:
    fa = np.fft.rfft(a[:m], n=1 << int(np.ceil(np.log2(2 * m))))
    fs = np.fft.rfft(seg[:m], n=1 << int(np.ceil(np.log2(2 * m))))
    xc = np.fft.irfft(fs * np.conj(fa), n=1 << int(np.ceil(np.log2(2 * m))))
    lag = int(np.argmax(xc[:m]))
    s = seg[lag:lag + m]
    s = s[:len(a[:m])]
    r = float(np.corrcoef(s, a[:len(s)])[0, 1])
    resid = float(np.sqrt(np.mean((s - a[:len(s)]) ** 2)) / np.sqrt(np.mean(a[:len(s)] ** 2)))
else:
    lag, r, resid = 0, float("nan"), float("nan")

w = wave.open(os.path.join(HERE, "captured_mic.wav"), "wb")
w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes())
w.close()

print("=" * 66)
print(f"素材 {os.path.basename(SRC)} 取前 {SECS}s   采集总长 {n_have/SR:.2f}s")
print(f"端到端延迟(发出冲激->在CABLE Output出现) = {lat_ms:.1f} ms")
print(f"冲激幅度 {float(np.abs(mono[k])):.4f} (发出 1.0000)   起始底噪RMS {float(np.sqrt(np.mean(mono[:int(0.4*SR)]**2))):.6f}")
print(f"保真度请用 fidelity.py 复检（本脚本不做对齐计算）")
print("-" * 66)
print(out.strip())
print("=" * 66)
