# SPIKE (throwaway) —— 严格保真度：用冲激定位对齐点，再算重叠段皮尔逊相关
import sys, wave
import numpy as np

CAP, SRC = sys.argv[1], sys.argv[2]


def rd(p):
    w = wave.open(p, "rb")
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
    w.close()
    return x, sr


cap, csr = rd(CAP)
src, ssr = rd(SRC)
assert csr == ssr, f"采样率不同 {csr} vs {ssr}"
k = int(np.argmax(np.abs(cap)))          # 冲激位置
print(f"采集 {len(cap)/csr:.2f}s  源 {len(src)/ssr:.2f}s  冲激@{k/csr:.3f}s 幅度 {abs(cap[k]):.4f}")

# 冲激替换掉了源的第 1.0s 帧，故从源 1.15s 起比较；预测映射 idx = k + (t-1.0)*sr
t0 = 1.15
SENT_S = float(sys.argv[3]) if len(sys.argv) > 3 else 99.0   # 实际发送出去的秒数
a = src[int(t0 * ssr):int(min(SENT_S, len(src) / ssr) * ssr)]
base = k + int((t0 - 1.0) * csr)
best = (-9, 0)
for off in range(base - 800, base + 801, 20):
    n = min(len(a), len(cap) - off)
    if n < ssr:
        continue
    r = float(np.corrcoef(a[:n], cap[off:off + n])[0, 1])
    if r > best[0]:
        best = (r, off)
r, off = best
n = min(len(a), len(cap) - off)
d = a[:n] - cap[off:off + n]
print(f"最佳对齐 off={off} (预测 {base}, 差 {(off-base)/csr*1000:.1f}ms)")
print(f"重叠 {n/csr:.2f}s  皮尔逊 r={r:.4f}  残差RMS/信号RMS={float(np.sqrt(np.mean(d**2))/np.sqrt(np.mean(a[:n]**2))):.4f}")
print(f"能量比 {float(np.sum(cap[off:off+n]**2)/np.sum(a[:n]**2)):.4f}")
