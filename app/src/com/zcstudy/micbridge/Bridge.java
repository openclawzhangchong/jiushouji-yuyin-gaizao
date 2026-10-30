package com.zcstudy.micbridge;

import android.content.Context;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;

/** 采麦 -> TCP 推流。链路对端是 adb reverse 过来的 PC 接收服务，所以固定连本机回环。 */
public class Bridge implements Runnable {

    public static final String TAG = "MICBRIDGE";
    public static final int RATE = 16000;
    public static final int CHUNK = 320;          // 20ms
    public static final int PORT = 5005;
    public static final int TONE_HZ = 1000;
    public static final int TONE_AMP = 8000;

    private final Context ctx;
    private volatile boolean running;
    private volatile long calUntilNs;
    private volatile long calWallMs;
    /** MTK 上 VOICE_COMMUNICATION 会挂平台回声处理；做 A/B 用，运行时改要在停->_start 之间。 */
    public volatile int source = MediaRecorder.AudioSource.VOICE_COMMUNICATION;
    private Thread th;
    private PowerManager.WakeLock wl;

    public volatile String state = "未启动";
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
                s = new Socket();
                s.connect(new InetSocketAddress("127.0.0.1", PORT), 3000);
                s.setTcpNoDelay(true);
                final OutputStream out = s.getOutputStream();

                int min = AudioRecord.getMinBufferSize(RATE,
                        AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
                if (min <= 0) throw new IOException("getMinBufferSize=" + min);
                rec = new AudioRecord(source,
                        RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                        min * 4);
                if (rec.getState() != AudioRecord.STATE_INITIALIZED)
                    throw new IOException("AudioRecord 初始化失败 min=" + min);

                state = "采麦中";
                Log.i(TAG, "已连 127.0.0.1:" + PORT + " 音源=" + srcName(source)
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
                                + " 状态 " + state);
                        winStart = now;
                        winBytes = 0;
                        winPeak = 0;
                    }
                }
            } catch (IOException e) {
                reconnects++;
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
