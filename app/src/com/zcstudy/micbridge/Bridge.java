package com.zcstudy.micbridge;

import android.content.Context;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;

/**
 * 采麦 -> TCP 推流。两条腿：优先 USB（adb reverse 把本机回环口搬到电脑），
 * 其次 WiFi（直连手填的电脑局域网 IP）。谁先通用谁，连上后靠 PC 回写的心跳字节判活。
 */
public class Bridge implements Runnable {

    public static final String TAG = "MICBRIDGE";
    public static final int RATE = 16000;
    public static final int CHUNK = 320;          // 20ms
    public static final int PORT = 5005;
    public static final int TONE_HZ = 1000;
    public static final int TONE_AMP = 8000;
    public static final long PONG_TIMEOUT_MS = 6000;
    /** 连上之后多久必须见到第一个心跳字节。超过就当对端是黑洞。 */
    public static final long PONG_FIRST_MS = 10000;

    private final Context ctx;
    private volatile boolean running;
    private volatile long calUntilNs;
    private volatile long calWallMs;
    /** MTK 上 VOICE_COMMUNICATION 会挂平台回声处理；做 A/B 用，运行时改要在停->_start 之间。 */
    public volatile int source = MediaRecorder.AudioSource.VOICE_COMMUNICATION;
    /** 电脑的局域网 IP，空表示未配置（只用 USB）。 */
    public volatile String lanHost = "";
    private Thread th;
    private PowerManager.WakeLock wl;
    private volatile long lastPongMs;
    /** 只有真的收到过至少一个心跳字节才启用超时判定，否则配上新 App + 旧接收端会反复误断线。 */
    private volatile boolean pongSeen;
    private volatile boolean sessionPong;
    private volatile boolean sessionStarted;
    /** 哪条链路先试。连上却从没收到过心跳（黑洞）就翻一次，避免在假通的链路上无限空转。 */
    private volatile boolean usbFirst = true;

    public volatile String state = "未启动";
    public volatile String link = "-";
    public volatile long bytesTotal, shortReads, reconnects, peak, lastRate;
    public volatile long startedAt;

    public Bridge(Context c) {
        ctx = c.getApplicationContext();
    }

    public void start() {
        if (running) return;
        running = true;
        bytesTotal = 0; shortReads = 0; reconnects = 0; peak = 0;
        startedAt = SystemClock.elapsedRealtime();
        th = new Thread(this, "MicBridge");
        th.start();
    }

    public void stop() {
        running = false;
        if (th != null) {
            try { th.join(1500); } catch (InterruptedException ignored) { }
            th = null;
        }
        state = "已停止";
    }

    public boolean isRunning() {
        return running;
    }

    /** 注入 TONE_MS 毫秒 1kHz 标定音，绕过麦克风直达上行流，用来量纯链路延迟。 */
    public void injectTone(int ms) {
        calWallMs = System.currentTimeMillis();
        calUntilNs = System.nanoTime() + ms * 1000000L;
        Log.i(TAG, "标定起 wallms=" + calWallMs + " 时长=" + ms + "ms");
    }

    public long getCalWallMs() {
        return calWallMs;
    }

    @Override
    public void run() {
        acquireWake();
        int backoff = 1000;
        while (running) {
            Socket s = null;
            AudioRecord rec = null;
            try {
                s = connectAny();
                final OutputStream out = s.getOutputStream();
                startPongReader(s.getInputStream());

                int min = AudioRecord.getMinBufferSize(RATE,
                        AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
                if (min <= 0) throw new IOException("getMinBufferSize=" + min);
                rec = new AudioRecord(source,
                        RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                        min * 4);
                if (rec.getState() != AudioRecord.STATE_INITIALIZED)
                    throw new IOException("AudioRecord 初始化失败 min=" + min);

                state = "采麦中 · " + link;
                sessionStarted = true;
                Log.i(TAG, "已连 " + link + " 音源=" + srcName(source)
                        + " minBuf=" + min + " 用=" + (min * 4));
                backoff = 1000;
                rec.startRecording();

                short[] samples = new short[CHUNK];
                byte[] payload = new byte[CHUNK * 2];
                double phase = 0.0;
                final double step = 2.0 * Math.PI * TONE_HZ / RATE;
                long winStart = SystemClock.elapsedRealtime(), winBytes = 0;
                long winPeak = 0;
                boolean toneOn = false;

                while (running) {
                    int n = rec.read(samples, 0, CHUNK);
                    if (n < 0) { shortReads++; throw new IOException("read=" + n); }
                    if (n < CHUNK) shortReads++;

                    boolean tone = System.nanoTime() < calUntilNs;
                    if (tone && !toneOn) {
                        toneOn = true;
                        Log.i(TAG, "标定注入开始 距按下 "
                                + (System.currentTimeMillis() - calWallMs) + "ms");
                    }
                    if (!tone) toneOn = false;

                    long p = 0;
                    int cnt = n > 0 ? n : 0;
                    if (tone) {
                        for (int i = 0; i < cnt; i++) {
                            short v = (short) (TONE_AMP * Math.sin(phase));
                            phase += step;
                            if (phase > 2.0 * Math.PI) phase -= 2.0 * Math.PI;
                            samples[i] = v;
                        }
                    }
                    for (int i = 0; i < cnt; i++) {
                        int a = Math.abs((int) samples[i]);
                        if (a > p) p = a;
                    }
                    if (p > winPeak) winPeak = p;

                    int bytes = cnt * 2;
                    for (int i = 0; i < cnt; i++) {
                        payload[i * 2] = (byte) (samples[i] & 0xff);
                        payload[i * 2 + 1] = (byte) ((samples[i] >> 8) & 0xff);
                    }
                    out.write(payload, 0, bytes);
                    bytesTotal += bytes;
                    winBytes += bytes;

                    // TCP 连上只代表进了对端内核 backlog，不代表有人读走。
                    // 实测踩过：接收端 accept 线程崩了，平板照样报"已连 USB、速率 32000B/s"，
                    // 数据全写进缓冲区喂了黑洞。所以心跳是硬要求：连上 10 秒内必须见到第一个，
                    // 之后 6 秒一个都不能缺。
                    long sincePong = SystemClock.elapsedRealtime() - lastPongMs;
                    long limit = pongSeen ? PONG_TIMEOUT_MS : PONG_FIRST_MS;
                    if (sincePong > limit)
                        throw new IOException(pongSeen
                                ? "PC 心跳断了 " + sincePong + "ms"
                                : "PC 从没回过心跳(" + sincePong + "ms)，数据可能进了黑洞");

                    long now = SystemClock.elapsedRealtime();
                    if (now - winStart >= 5000) {
                        lastRate = winBytes * 1000 / (now - winStart);
                        peak = winPeak;
                        Log.i(TAG, "心跳 已推 " + (now - startedAt) / 1000 + "s"
                                + " 累计 " + bytesTotal + "B"
                                + " 速率 " + lastRate + "B/s"
                                + " 峰值 " + winPeak
                                + " 欠采 " + shortReads
                                + " 重连 " + reconnects
                                + " 链路 " + link
                                + " 状态 " + state);
                        winStart = now;
                        winBytes = 0;
                        winPeak = 0;
                    }
                }
            } catch (IOException e) {
                reconnects++;
                // 连上但从没收到过心跳 = 假通（对端只是把数据吞进内核缓冲区）。
                // 下一轮换先试另一条腿，别在假通的链路上无限空转。
                if (sessionStarted && !sessionPong) {
                    usbFirst = !"USB".equals(link);
                    Log.i(TAG, "本轮 " + link + " 从未收到心跳，下轮先试 "
                            + (usbFirst ? "USB" : "WiFi"));
                }
                sessionStarted = false;
                state = "等待电脑端 (" + e.getMessage() + ")";
                Log.i(TAG, "断开/连不上：" + e + "  " + backoff + "ms 后重试");
                try { Thread.sleep(backoff); } catch (InterruptedException ignored) { }
                backoff = Math.min(backoff * 2, 5000);
            } finally {
                if (rec != null) {
                    try { rec.stop(); } catch (Exception ignored) { }
                    try { rec.release(); } catch (Exception ignored) { }
                }
                if (s != null) {
                    try { s.close(); } catch (Exception ignored) { }
                }
            }
        }
        releaseWake();
        state = "已停止";
        link = "-";
    }

    /** USB 优先：adb reverse 把本机回环的 PORT 搬到电脑；不通再试用户配置的局域网 IP。 */
    private Socket tryConnect(String host, int timeoutMs) throws IOException {
        Socket so = new Socket();
        try {
            so.connect(new InetSocketAddress(host, PORT), timeoutMs);
            so.setTcpNoDelay(true);
        } catch (IOException e) {
            try { so.close(); } catch (Exception ignored) { }
            throw e;
        }
        link = "127.0.0.1".equals(host) ? "USB" : "WiFi@" + host;
        return so;
    }

    /** 按当前优先级依次试两条腿；lanHost 没配就只有 USB 一条。 */
    private Socket connectAny() throws IOException {
        String h = lanHost == null ? "" : lanHost.trim();
        IOException last = new IOException("没有可用目标（WiFi 地址未设置）");
        for (int i = 0; i < 2; i++) {
            boolean thisUsb = usbFirst ? (i == 0) : (i == 1);
            String host = thisUsb ? "127.0.0.1" : h;
            if (host.length() == 0) {
                continue;
            }
            try {
                return tryConnect(host, thisUsb ? 1200 : 1500);
            } catch (IOException e) {
                last = e;
            }
        }
        throw last;
    }

    private void startPongReader(final InputStream in) {
        lastPongMs = SystemClock.elapsedRealtime();
        pongSeen = false;
        sessionPong = false;
        Thread t = new Thread(new Runnable() {
            @Override public void run() {
                byte[] b = new byte[1];
                try {
                    while (running && in.read(b) >= 0) {
                        lastPongMs = SystemClock.elapsedRealtime();
                        pongSeen = true;
                        sessionPong = true;
                    }
                } catch (IOException ignored) { }
            }
        }, "PongReader");
        t.setDaemon(true);
        t.start();
    }

    public String pongState() {
        if (!"采麦中".equals(state) && !state.startsWith("采麦中")) return "还没连上";
        if (!pongSeen) return "还没收到第一个心跳（对端可能没在收）";
        long dt = SystemClock.elapsedRealtime() - lastPongMs;
        if (dt > PONG_TIMEOUT_MS) return "心跳超时 " + dt + "ms";
        return "心跳正常 距上次 " + dt + "ms";
    }

    private void acquireWake() {
        if (wl != null) return;
        PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
        wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "micbridge:up");
        wl.setReferenceCounted(false);
        wl.acquire();
    }

    private void releaseWake() {
        if (wl != null && wl.isHeld()) wl.release();
        wl = null;
    }

    public static String srcName(int s) {
        if (s == MediaRecorder.AudioSource.VOICE_COMMUNICATION) return "VOICE_COMMUNICATION";
        if (s == MediaRecorder.AudioSource.VOICE_RECOGNITION) return "VOICE_RECOGNITION";
        if (s == MediaRecorder.AudioSource.MIC) return "MIC";
        return "src" + s;
    }
}
