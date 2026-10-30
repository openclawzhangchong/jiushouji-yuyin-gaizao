# SPIKE (throwaway) —— PC 接收端：UDP 收流 -> 播进 CABLE Input
# 正式实现可能要换 TCP/WebSocket + 抖动缓冲，这里只求"能不能成"
import collections, socket, sys, threading, time
import numpy as np
import sounddevice as sd

SR, CH = 16000, 1
OUT_DEV = int(sys.argv[1]) if len(sys.argv) > 1 else 15   # CABLE Input (DirectSound)
TTL_S = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
BLOCK = int(sys.argv[3]) if len(sys.argv) > 3 else 256
LAT_OUT = None if len(sys.argv) <= 4 or sys.argv[4] == "default" else (sys.argv[4] if sys.argv[4] in ("low","high") else float(sys.argv[4]))

q = collections.deque()
stat = dict(rx=0, pkts=0, underrun=0, eof=False)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.settimeout(0.5)
stop = threading.Event()


def net():
    while not stop.is_set():
        try:
            data, _ = sock.recvfrom(65564)
        except socket.timeout:
            continue
        if data == b"EOF\n":
            stat["eof"] = True
            break
        stat["rx"] += len(data)
        stat["pkts"] += 1
        q.append(np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0)


def cb(outdata, frames, t, status):
    got = 0
    while got < frames:
        try:
            blk = q.popleft()
        except IndexError:
            break
        n = min(len(blk), frames - got)
        outdata[got:got + n, 0] = blk[:n]
        if n < len(blk):
            q.appendleft(blk[n:])
        got += n
    if got < frames and not stat["eof"]:
        stat["underrun"] += 1


threading.Thread(target=net, daemon=True).start()
print(f"receiver: UDP:5005 -> 设备 #{OUT_DEV} @ {SR}Hz mono, 最长 {TTL_S}s", flush=True)
with sd.OutputStream(samplerate=SR, channels=CH, dtype="float32", device=OUT_DEV,
                     callback=cb, blocksize=BLOCK, latency=LAT_OUT):
    t_end = time.perf_counter() + TTL_S
    while time.perf_counter() < t_end and not (stat["eof"] and not q):
        time.sleep(0.05)
    time.sleep(0.3)  # 把尾音放干净

print(f"STATS|pkts={stat['pkts']}|bytes={stat['rx']}|audio_s={stat['rx']/2/SR:.2f}"
      f"|leftover_ms={sum(len(x) for x in q)/SR*1000:.0f}|underrun={stat['underrun']}")
sock.close()
