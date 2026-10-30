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
PONG = b"P"                          # 协议：每 2 秒回写 1 字节，平板 6 秒收不到就重选链路
PONG_EVERY = 2.0
GAP_MS = 50.0                        # 包间隔超过这个值算一次"网络打嗝"
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
    ap.add_argument("--bind", default="auto",
                    help="auto=优先只监听回环(配合 adb reverse，不额外开防火墙)；"
                         "0.0.0.0 或某个网卡 IP = 同时接受平板从局域网连进来")
    ap.add_argument("--water-lan", type=float, default=250.0,
                    help="WiFi 链路的目标水位 ms（实测该网段 RTT 常见 15-30ms 但会尖到 240ms）")
    ap.add_argument("--max-water-lan", type=float, default=700.0,
                    help="WiFi 链路的丢最老阈值 ms")
    ap.add_argument("--no-lan-water", action="store_true",
                    help="WiFi 链路也用 USB 那套水位（想在网络质量好时压延迟用）")
    ap.add_argument("--record", type=float, default=0, help="从 CABLE Output 录 N 秒存 verify.wav")
    ap.add_argument("--recv-bytes", type=int, default=3200,
                    help="单次最多读多少字节。65536 会一口吞掉 2 秒音频，把预缓冲直接顶过头")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        for i, d in enumerate(sd.query_devices()):
            print("%2d  ha%d  in%d out%d  %s" % (i, d["hostapi"], d["max_input_channels"],
                                                 d["max_output_channels"], d["name"]))
        return 0

    adb = find_adb()          # WiFi 模式的远端电脑没有平板数据线，没有 adb 也要能跑

    out_idx, out_name = (a.out, "(指定)") if a.out is not None else pick("CABLE Input", False)
    lat = None if a.latency == "default" else (
        a.latency if a.latency in ("low", "high") else float(a.latency))

    print("adb      : %s" % (adb if adb else "没有（纯 WiFi 模式，不做 adb reverse）"))
    print("灌入设备 : #%s %s @%dHz mono  latency=%s block=%d帧" %
          (out_idx, out_name, SR, a.latency, a.block))
    print("水位     : 目标 %.0fms，超 %.0fms 丢最老" % (a.water, a.max_water))

    # 只在监听地址真的覆盖回环时才下发 adb reverse。
    # 否则回环桩会"先接受、后失败"，平板会以为 USB 通了而永远轮不到 WiFi。
    want_loopback = a.bind in ("auto", "127.0.0.1", "0.0.0.0")
    if adb and want_loopback:
        print(run_adb(adb, "reverse", "tcp:%d" % PORT, "tcp:%d" % PORT).strip()
              or "adb reverse tcp:%d tcp:%d 已下发" % (PORT, PORT))
    elif adb:
        print("（绑定 %s 不含回环，跳过 adb reverse —— 这是纯 WiFi 模式）" % a.bind)

    buf = collections.deque()
    lock = threading.Lock()
    st = dict(recv=0, underrun=0, drop=0, conns=0, client=None, alive=True,
              link="?", water=a.water, max_water=a.max_water,
              last_rx=0.0, gap50=0, gap200=0, gapmax=0.0, pkts=0, pongs=0)

    def depth_ms():
        return sum(len(x) for x in buf) * 1000.0 / SR

    def cb(outdata, frames, t, status):
        # 水位真正参与控制：刚连上或饿过一回时先憋着不出声，把缓冲攒到目标水位再放。
        # WiFi 链路靠它吸收尖峰（实测该网段会偶发 150-250ms 的包间隔）。
        # 只在"能攒得起来"的前提下等：水位已经顶到 max_water 还不够 target，
        # 说明发送端本身就慢（或水位设太大），这时必须放音，否则会永远卡在静音。
        d = depth_ms()
        if d < st["water"] and d < st["max_water"]:
            outdata[:, 0] = 0
            return
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
                st["underrun"] += 1        # 饿了不用再手动计时：上面的水位判据会自动把放音卡住

    def ponger(conn):
        """协议：每 2 秒回写 1 字节。平板 6 秒收不到就判定链路废掉并重选（USB/WiFi）。
        只写不读；写失败说明对端已经没了，退出线程即可。"""
        while st["alive"] and st["client"] is conn:
            time.sleep(PONG_EVERY)
            try:
                conn.sendall(PONG)
                st["pongs"] += 1
            except OSError:
                return

    def reader(conn, addr):
        st["conns"] += 1
        st["client"] = conn
        loopback = addr[0] in ("127.0.0.1", "::1")
        if loopback:
            st["link"] = "USB(adb reverse) <- %s" % addr[0]
            st["water"], st["max_water"] = a.water, a.max_water
        else:
            st["link"] = "WiFi <- %s" % addr[0]
            if not a.no_lan_water:
                st["water"] = a.water_lan
                st["max_water"] = max(a.max_water_lan, a.water_lan * 2)
        st["last_rx"] = 0.0        # 新链路：重新按当前水位攒缓冲
        print("[%s] 平板已连上 %s  目标水位 %.0fms 上限 %.0fms"
              % (time.strftime("%H:%M:%S"), st["link"], st["water"], st["max_water"]),
              flush=True)
        threading.Thread(target=ponger, args=(conn,), daemon=True).start()
        try:
            while st["alive"]:
                data = conn.recv(a.recv_bytes)
                if not data:
                    break
                tnow = time.perf_counter()
                if st["last_rx"]:
                    gap = (tnow - st["last_rx"]) * 1000.0
                    if gap > GAP_MS:
                        st["gap50"] += 1
                    if gap > 200:
                        st["gap200"] += 1
                    if gap > st["gapmax"]:
                        st["gapmax"] = gap
                st["last_rx"] = tnow
                st["pkts"] += 1
                st["recv"] += len(data)
                blk = np.frombuffer(data, dtype="<i2")
                buf.append(blk)
                with lock:                      # 越积越多说明消费不动了，丢最老的保新鲜
                    while buf and depth_ms() > st["max_water"]:
                        buf.popleft()
                        st["drop"] += 1
        except OSError:
            pass
        finally:
            st["client"] = None
            st["last_rx"] = 0.0
            try:
                conn.close()
            except OSError:
                pass
            print("[%s] 平板断开" % time.strftime("%H:%M:%S"), flush=True)

    # Windows 的 SO_REUSEADDR 允许绑到**已被占用**的端口且不报错，于是会出现
    # "新接收端在打印、旧接收端在服务"这种假象。先探一下端口有没有人在听。
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.6)
    busy = probe.connect_ex(("127.0.0.1", PORT)) == 0
    probe.close()
    if busy:
        print("!! 本机 %d 端口已经有进程在监听（多半是上一个接收端没退干净）。" % PORT)
        print("   先关掉旧的再起，否则新起的这个看着像在跑、其实一个连接都收不到。")
        print("   查占用： netstat -ano | findstr :%d" % PORT)
        return 3

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 故意**不设** SO_REUSEADDR：Windows 上它允许静默重复绑定同一个端口，
    # 结果是第二个接收端"启动成功、日志在刷、却一个连接都收不到"，
    # 排查时被误当成"链路坏了"（本仓库为此栽过两次）。不设的话第二个实例直接 WSAEADDRINUSE。
    b = a.bind
    if b != "auto":
        srv.bind((b, PORT))
        bind_desc = b
    else:
        # auto 的含义随环境变：有 adb 就认定是"插线的那台电脑"，只绑回环，不动防火墙；
        # 没有 adb 说明这台是"只走 WiFi 的那台电脑"，必须绑 0.0.0.0，否则平板根本连不进来。
        if adb:
            try:
                srv.bind(("127.0.0.1", PORT))
                bind_desc = "127.0.0.1（检测到 adb，按 USB 模式只绑回环，不需要防火墙规则）"
            except OSError:
                srv.bind(("0.0.0.0", PORT))
                bind_desc = "0.0.0.0（回环被占，改全网卡）"
        else:
            srv.bind(("0.0.0.0", PORT))
            bind_desc = "0.0.0.0（没检测到 adb，按纯 WiFi 模式监听全网卡；需放行防火墙 TCP:%d）" % PORT
    srv.listen(2)
    srv.settimeout(1.0)
    print("监听     : %s:%d" % (bind_desc.split("（")[0], PORT))

    def accept_loop():
        while st["alive"]:
            try:
                conn, addr = srv.accept()      # addr 要留着：reader 靠它区分 USB 回环还是 WiFi
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
            threading.Thread(target=reader, args=(conn, addr), daemon=True).start()

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

    tlast, vlast, vpkts = time.time(), st["recv"], st["pkts"]
    try:
        with sd.OutputStream(samplerate=SR, channels=1, dtype="int16",
                             device=out_idx, callback=cb, blocksize=a.block, latency=lat):
            while st["alive"]:
                time.sleep(2.0)
                now = time.time()
                rate = (st["recv"] - vlast) / max(now - tlast, 1e-6)
                dpk = st["pkts"] - vpkts
                tlast, vlast, vpkts = now, st["recv"], st["pkts"]
                if want_loopback and adb and st["client"] is None and device_present(adb):
                    run_adb(adb, "reverse", "tcp:%d" % PORT, "tcp:%d" % PORT)
                with lock:
                    w = depth_ms()
                print("[%s] %s 水位%.0fms %dB/s 包间隔 本窗>%.0fms:%d/%d >200ms:%d 最大%.0fms "
                      "累计%.1fs 欠载%d 丢块%d 心跳%d 连接%d"
                      % (time.strftime("%H:%M:%S"),
                         "推流中" if st["client"] else "等设备连",
                         w, rate, GAP_MS, st["gap50"] if dpk else 0, dpk,
                         st["gap200"], st["gapmax"],
                         st["recv"] / 2 / SR,
                         st["underrun"], st["drop"], st["pongs"], st["conns"]), flush=True)
                st["gap50"] = st["gap200"] = 0
                st["gapmax"] = 0.0
                if a.record and time.time() - t_rec >= a.record:
                    break
    except KeyboardInterrupt:
        print("\nCtrl-C，收尾")
    finally:
        st["alive"] = False
        if adb:
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
