# 独立进程：从 CABLE Output 录 N 秒，测包络/频谱，证明此刻确实有声音进来（不重启接收端）
import sys, time
import numpy as np, sounddevice as sd, wave
N = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
SR = 16000
dev = None
for i, d in enumerate(sd.query_devices()):
    if "CABLE Output" in d["name"] and d["max_input_channels"] > 0 and d["hostapi"] == 1:
        dev = i; break
chunks = []
def cb(ind, fr, t, st): chunks.append(ind.copy())
with sd.InputStream(samplerate=SR, channels=1, dtype="float32", device=dev, callback=cb, blocksize=1600):
    time.sleep(N)
x = np.concatenate([c.reshape(-1) for c in chunks])
print("录到 %.1fs  峰值 %.4f  RMS %.5f  (%.1f dBFS)" % (
    len(x)/SR, np.max(np.abs(x)), np.sqrt(np.mean(x**2)), 20*np.log10(np.sqrt(np.mean(x**2))+1e-12)))
win = int(0.2*SR)
env = [20*np.log10(np.sqrt(np.mean(x[i:i+win]**2))+1e-12) for i in range(0, len(x)-win, win)]
print("每0.2s包络 dBFS: " + " ".join("%.0f" % v for v in env))
F = np.abs(np.fft.rfft(x*np.hanning(len(x)))); fr = np.fft.rfftfreq(len(x), 1/SR)
for a,b in [(50,300),(300,1000),(1000,2000),(2000,4000)]:
    print("  %4d-%4dHz 能量 %.2f" % (a,b,float(F[(fr>=a)&(fr<b)].mean())))
w = wave.open("cap_probe.wav","wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(x,-1,1)*32767).astype("<i2").tobytes()); w.close()
print("已存 cap_probe.wav")
