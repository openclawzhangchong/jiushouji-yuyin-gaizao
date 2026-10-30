#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PC 接收端：把平板经 adb reverse 推来的 16k/mono/PCM16 音频播进 VB-Cable。

Windows 因此多出一个叫 CABLE Output 的麦克风，任何程序都能选它当输入设备。
  python pc_receiver.py                 # 常驻
  python pc_receiver.py --list          # 看设备索引
  python pc_receiver.py --record 10     # 顺手从 CABLE Output 录 10s 存 verify.wav
"""
import argparse, collections, os, socket, subprocess, sys, threading, time, wave
import numpy as np
import sounddevice as sd

try:
    sys.stdout.reconfigure(line_buffering=True)   # 重定向到文件/窗口都要即时可见
except Exception:
    pass

SR = 16000
PORT = 5005
ADB_CANDIDATES = [
    os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
        r"\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe"),
    "adb",
]
HERE = os.path.dirname(os.path.abspath(__file__))


def find_adb():
    for c in ADB_CANDIDATES:
        try:
            subprocess.run([c, "version"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=8, check=True)
            return c
        except Exception:
            continue
    return None


def run_adb(adb, *args):
    try:
        r = subprocess.run([adb] + list(args), capture_output=True, text=True, timeout=10)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "ERR " + str(e)


def device_present(adb):
    # 这台 5.1 的 adbd 不支持 reverse --list（protocol fault），
    # 所以只能靠设备在位变化来判断要不要重下发隧道。
    for ln in run_adb(adb, "devices").splitlines():
        p = ln.split()
        if len(p) >= 2 and p[1] == "device":
            return True
    return False


def pick(pattern, need_in, prefer=(1, 0, 3, 2)):
    """按全名挑设备。PortAudio 把名字截到 32 字符，所以只能用包含匹配。"""
    devs = sd.query_devices()
    for ha in prefer:
        for i, d in enumerate(devs):
            if d["hostapi"] != ha:
                continue
            ch = d["max_input_channels"] if need_in else d["max_output_channels"]
            if ch == 0:
                continue
            if pattern.lower() in d["name"].lower():
                return i, d["name"]
    sys.exit("找不到名字含 %r 的设备，先 --list 看看" % pattern)


def main():
    ap = argparse.ArgumentParser(description="旧平板 -> Windows 虚拟麦克风 接收端")
    ap.add_argument("--out", type=int, default=None, help="CABLE Input 的设备索引")
    ap.add_argument("--cap", type=int, default=None, help="CABLE Output 的索引（--record 用）")
    ap.add_argument("--water", type=float, default=60.0, help="目标缓冲水位 ms")
    ap.add_argument("--max-water", type=float, default=180.0, help="超过就丢最老的，防止越积越久")
    ap.add_argument("--latency", default="low", help="low / high / default / 秒数")
    ap.add_argument("--block", type=int, default=320, help="每次回调帧数，320=20ms")
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--record", type=float, default=0, help="从 CABLE Output 录 N 秒存 verify.wav")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        for i, d in enumerate(sd.query_devices()):
            print("%2d  ha%d  in%d out%d  %s" % (i, d["hostapi"], d["max_input_channels"],
                                                 d["max_output_channels"], d["name"]))
        return 0

    adb = find_adb()
    if not adb:
        print("!! 没找到 adb（先 winget install Google.PlatformTools）")
        return 2

    out_idx, out_name = (a.out, "(指定)") if a.out is not None else pick("CABLE Input", False)
    lat = None if a.latency == "default" else (
        a.latency if a.latency in ("low", "high") else float(a.latency))

    print("adb      : %s" % adb)
    print("灌入设备 : #%s %s @%dHz mono  latency=%s block=%d帧" %
          (out_idx, out_name, SR, a.latency, a.block))
    print("水位     : 目标 %.0fms，超 %.0fms 丢最老" % (a.water, a.max_water))

    print(run_adb(adb, "reverse", "tcp:%d" % PORT, "tcp:%d" % PORT).strip()
          or "adb reverse tcp:%d tcp:%d 已下发" % (PORT, PORT))

    buf = collections.deque()
    lock = threading.Lock()
    st = dict(recv=0, underrun=0, drop=0, conns=0, client=None, alive=True)

    def depth_ms():
        return sum(len(x) for x in buf) * 1000.0 / SR

    def cb(outdata, frames, t, status):
        got = 0
        while got < frames:
            with lock:
                if not buf:
                    break
                blk = buf.popleft()
            n = min(len(blk), frames - got)
            outdata[got:got + n, 0] = blk[:n]
            if n < len(blk):
                with lock:
                    buf.appendleft(blk[n:])
            got += n
        if got < frames:
            outdata[got:frames, 0] = 0
            if st["client"] is not None:
                st["underrun"] += 1

    def reader(conn):
        st["conns"] += 1
        st["client"] = conn
        print("[%s] 平板已连上" % time.strftime("%H:%M:%S"))
        try:
            while st["alive"]:
                data = conn.recv(65536)
                if not data:
                    break
                st["recv"] += len(data)
                blk = np.frombuffer(data, dtype="<i2")
                buf.append(blk)
                with lock:                      # 越积越多说明消费不动了，丢最老的保新鲜
                    while buf and depth_ms() > a.max_water:
                        buf.popleft()
                        st["drop"] += 1
        except OSError:
            pass
        finally:
            st["client"] = None
            try:
                conn.close()
            except OSError:
                pass
            print("[%s] 平板断开" % time.strftime("%H:%M:%S"))

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((a.bind, PORT))
    srv.listen(2)
    srv.settimeout(1.0)

    def accept_loop():
        while st["alive"]:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:                     # 收尾时 srv.close() 会让 accept 抛 10038
                break
            old = st["client"]
            if old is not None:                 # 只允许一路，旧连接踢掉
                try:
                    old.close()
                except OSError:
                    pass
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=reader, args=(conn,), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()

    rec, capstream, t_rec = [], None, time.time()
    if a.record:
        cap_idx, cap_name = pick("CABLE Output", True)
        print("同时录音 : #%s %s %.1fs -> verify.wav" % (cap_idx, cap_name, a.record))

        def capcb(indata, frames, t, status):
            rec.append(indata.copy())
        capstream = sd.InputStream(samplerate=SR, channels=1, dtype="int16",
                                   device=cap_idx, callback=capcb, blocksize=a.block)
        capstream.start()
        t_rec = time.time()

    tlast, vlast = time.time(), st["recv"]
    try:
        with sd.OutputStream(samplerate=SR, channels=1, dtype="int16",
                             device=out_idx, callback=cb, blocksize=a.block, latency=lat):
            while st["alive"]:
                time.sleep(2.0)
                now = time.time()
                rate = (st["recv"] - vlast) / max(now - tlast, 1e-6)
                tlast, vlast = now, st["recv"]
                if st["client"] is None and device_present(adb):
                    run_adb(adb, "reverse", "tcp:%d" % PORT, "tcp:%d" % PORT)
                with lock:
                    w = depth_ms()
                print("[%s] %s 水位%.0fms %dB/s 累计%.1fs 欠载%d 丢块%d 连接%d"
                      % (time.strftime("%H:%M:%S"),
                         "推流中" if st["client"] else "等设备连",
                         w, rate, st["recv"] / 2 / SR,
                         st["underrun"], st["drop"], st["conns"]))
                if a.record and time.time() - t_rec >= a.record:
                    break
    except KeyboardInterrupt:
        print("\nCtrl-C，收尾")
    finally:
        st["alive"] = False
        run_adb(adb, "reverse", "--remove-all")
        srv.close()
        if capstream is not None:
            capstream.stop()
        if a.record:
            if rec:
                x = np.concatenate([r.reshape(-1) for r in rec]).astype("<i2")
                w = wave.open(os.path.join(HERE, "verify.wav"), "wb")
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes(x.tobytes()); w.close()
                print("已存 verify.wav %.1fs 峰值 %d  ->  "
                      "node .../ws-transcribe.mjs \"%s\""
                      % (len(x) / SR, int(np.max(np.abs(x.astype(np.int64)))),
                         os.path.join(HERE, "verify.wav")))
            else:
                print("没录到东西")
    return 0


if __name__ == "__main__":
    sys.exit(main())
