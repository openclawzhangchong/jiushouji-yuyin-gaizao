package com.zcstudy.micbridge;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Paint;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

/**
 * modern 变体（Android 16 / API 36）的 Activity，覆盖 legacy 的 app/src 同名类。
 * 与 legacy 的差异只有 Android 13+ 适配，功能与界面保持不变：
 *   1) targetSdk 35+ 强制 edge-to-edge：按 systemBars/刘海 insets 给根视图补 padding；
 *   2) targetSdk 23+ 起 RECORD_AUDIO 变成运行时权限，开始送话前先申请；
 *   3) Android 13+ 读取 /sdcard 下的 demo.wav 需 READ_MEDIA_AUDIO，外放自测前申请。
 * legacy 变体不会编译本文件，旧机型行为完全不变。
 */
public class MainActivity extends Activity {

    public static final String DEMO_DEFAULT = "/sdcard/Music/demo.wav";
    private static final int REQ_MIC = 101;
    private static final int REQ_READ = 102;
    private String demoPath = DEMO_DEFAULT;

    private Bridge bridge;
    private TextView tvState, tvData, tvHint;
    private Button btnToggle, btnTone, btnSrc;
    private LevelView level;
    private final Handler hud = new Handler();

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            paint();
            hud.postDelayed(this, 50);
        }
    };

    @Override
    protected void onCreate(Bundle b) {
        // aapt2 配老存根会静默丢掉 manifest 里的 android:theme，主题只能在代码里设
        setTheme(android.R.style.Theme_DeviceDefault);
        super.onCreate(b);
        String lanArg = null;
        if (getIntent() != null) {
            String d = getIntent().getStringExtra("demo");
            if (d != null && d.length() > 0) demoPath = d;
            // 无人值守配 WiFi 目标：--es lan 192.168.168.250；--es lan "" 等于清掉（只用 USB）
            if (getIntent().hasExtra("lan")) lanArg = getIntent().getStringExtra("lan");
        }
        bridge = new Bridge(this);
        bridge.lanHost = prefs().getString("lan_host", "");
        if (lanArg != null) {
            bridge.lanHost = lanArg.trim();
            prefs().edit().putString("lan_host", bridge.lanHost).apply();
        }
        ScrollView root = build();
        setContentView(root);
        applyEdgeToEdge(root);
        paint();
        // 无人值守：am start -n com.zcstudy.micbridge.a16/com.zcstudy.micbridge.MainActivity --ez auto true [--es act selftest]
        // 注意 am 的 --ez 只认 true/false，写 1 会被解析成 false，所以给了 act 就当作要自动起
        if (getIntent() != null
                && (getIntent().getBooleanExtra("auto", false)
                    || getIntent().getStringExtra("act") != null)) {
            hud.postDelayed(new Runnable() {
                @Override public void run() { if (!bridge.isRunning()) toggle(); }
            }, 300);
            if ("selftest".equals(getIntent().getStringExtra("act"))) {
                hud.postDelayed(new Runnable() {
                    @Override public void run() { selfTest(); }
                }, 2500);
            }
        }
    }

    private ScrollView build() {
        Context c = this;
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(LinearLayout.VERTICAL);
        int p = dp(16);
        box.setPadding(p, p, p, p);

        tvState = new TextView(c);
        tvState.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        tvState.setText("未启动");
        box.addView(tvState);

        level = new LevelView(c);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(46));
        lp.setMargins(0, dp(10), 0, dp(10));
        box.addView(level, lp);

        tvData = new TextView(c);
        tvData.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        box.addView(tvData);

        btnToggle = new Button(c);
        btnToggle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        btnToggle.setText("开始送话");
        btnToggle.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { toggle(); }
        });
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(76));
        bp.setMargins(0, dp(14), 0, 0);
        box.addView(btnToggle, bp);

        btnTone = new Button(c);
        btnTone.setText("标定音 0.3s（不经麦克风）");
        btnTone.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { bridge.injectTone(300); }
        });
        box.addView(btnTone);

        Button btnDemo = new Button(c);
        btnDemo.setText("外放自测（平板自己播 " + demoPath + "）");
        btnDemo.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { selfTest(); }
        });
        box.addView(btnDemo);

        btnSrc = new Button(c);
        btnSrc.setText("音源：" + Bridge.srcName(bridge.source) + "（点击切换）");
        btnSrc.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { switchSource(); }
        });
        box.addView(btnSrc);

        Button btnLan = new Button(c);
        btnLan.setText("WiFi 兜底：电脑 IP = " + (bridge.lanHost.isEmpty() ? "未设置" : bridge.lanHost));
        btnLan.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { askLanHost(btnLan); }
        });
        box.addView(btnLan);

        tvHint = new TextView(c);
        tvHint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        tvHint.setTextColor(Color.DKGRAY);
        tvHint.setText("电脑端先跑 pc_receiver.py（它会做 adb reverse）。"
                + "本 app 连的是平板自己的 127.0.0.1:" + Bridge.PORT + "。");
        box.addView(tvHint);

        ScrollView sv = new ScrollView(c);
        sv.addView(box);
        return sv;
    }

    /** Android 15+ 对 targetSdk 35+ 强制 edge-to-edge；按系统栏/刘海 insets 补 padding。 */
    private void applyEdgeToEdge(final ScrollView root) {
        root.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override public WindowInsets onApplyWindowInsets(View v, WindowInsets in) {
                int l, t, r, b;
                if (Build.VERSION.SDK_INT >= 30) {
                    Insets i = in.getInsets(
                            WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                    l = i.left; t = i.top; r = i.right; b = i.bottom;
                } else {
                    l = in.getSystemWindowInsetLeft();
                    t = in.getSystemWindowInsetTop();
                    r = in.getSystemWindowInsetRight();
                    b = in.getSystemWindowInsetBottom();
                }
                v.setPadding(l, t, r, b);
                return in;
            }
        });
        root.requestApplyInsets();
    }

    /** RECORD_AUDIO 在 targetSdk 23+ 是运行时权限；旧机型仍按安装时授权处理。 */
    private boolean hasPermission(String perm) {
        if (Build.VERSION.SDK_INT < 23) return true;
        return checkSelfPermission(perm) == PackageManager.PERMISSION_GRANTED;
    }

    /** Android 13+ 共享存储音频权限换成 READ_MEDIA_AUDIO（legacy 的旧权限在新系统上已无效）。 */
    private String readAudioPermission() {
        return Build.VERSION.SDK_INT >= 33
                ? Manifest.permission.READ_MEDIA_AUDIO
                : Manifest.permission.READ_EXTERNAL_STORAGE;
    }

    private void toggle() {
        if (bridge.isRunning()) {
            bridge.stop();
            btnToggle.setText("开始送话");
        } else {
            if (!hasPermission(Manifest.permission.RECORD_AUDIO)) {
                bridge.state = "等待麦克风授权";
                requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                paint();
                return;
            }
            bridge.start();
            btnToggle.setText("停止送话");
        }
        paint();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] granted) {
        super.onRequestPermissionsResult(code, perms, granted);
        boolean ok = granted.length > 0 && granted[0] == PackageManager.PERMISSION_GRANTED;
        if (code == REQ_MIC) {
            if (ok) toggle();
            else {
                bridge.state = "麦克风权限被拒绝";
                paint();
                log("RECORD_AUDIO 被拒绝，无法采麦");
            }
        } else if (code == REQ_READ) {
            if (ok) selfTest();
            else log("读取音频权限被拒绝，外放自测不可用；可 adb push 到应用私有目录");
        }
    }

    private void switchSource() {
        boolean wasRunning = bridge.isRunning();
        if (wasRunning) bridge.stop();
        bridge.source = bridge.source == MediaRecorder.AudioSource.VOICE_COMMUNICATION
                ? MediaRecorder.AudioSource.VOICE_RECOGNITION
                : MediaRecorder.AudioSource.VOICE_COMMUNICATION;
        btnSrc.setText("音源：" + Bridge.srcName(bridge.source) + "（点击切换）");
        if (wasRunning) {
            bridge.start();
            btnToggle.setText("停止送话");
        }
    }

    /**
     * 平板自己外放已知音频，自己的麦克风再听进去 —— 不依赖人、也不依赖电脑有没有喇叭，
     * 能把"采麦->推流->虚拟麦->录音->ASR"整条链一次验完。思路同 test_ptt.sh 的声学回环。
     */
    private void selfTest() {
        if (!hasPermission(readAudioPermission())) {
            requestPermissions(new String[]{readAudioPermission()}, REQ_READ);
            log("外放自测需要读取音频权限（" + readAudioPermission() + "）");
            return;
        }
        final File f = new File(demoPath);
        if (!f.exists()) {
            log("自测失败：找不到 " + demoPath + "，先 adb push demo.wav 过去");
            return;
        }
        new Thread(new Runnable() {
            @Override public void run() {
                AudioTrack at = null;
                try {
                    byte[] all = readAll(f);
                    int[] fmt = parseWav(all);          // {sr, ch, bits, dataOff, dataLen}
                    if (fmt[1] != 1 || fmt[2] != 16)
                        throw new IOException("只支持16bit单声道，实际 ch=" + fmt[1] + " bits=" + fmt[2]);
                    int sr = fmt[0], off = fmt[3], len = fmt[4];
                    at = new AudioTrack(AudioManager.STREAM_MUSIC, sr,
                            AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
                            sr * 4, AudioTrack.MODE_STREAM);
                    at.setStereoVolume(1f, 1f);
                    at.play();
                    byte[] blk = new byte[sr / 5 * 2];   // 200ms
                    int sent = 0;
                    while (sent < len) {
                        int n = Math.min(blk.length, len - sent);
                        System.arraycopy(all, off + sent, blk, 0, n);
                        at.write(blk, 0, n - (n & 1));
                        sent += n;
                    }
                    log("自测外放结束 sr=" + sr + " 时长 " + (len / 2.0 / sr) + "s");
                } catch (Exception e) {
                    log("自测外放异常：" + e);
                } finally {
                    if (at != null) {
                        try { at.stop(); } catch (Exception ignored) { }
                        at.release();
                    }
                }
            }
        }, "SelfTest").start();
    }

    private static void log(String s) {
        android.util.Log.i(Bridge.TAG, s);
    }

    private static byte[] readAll(File f) throws IOException {
        FileInputStream in = new FileInputStream(f);
        try {
            int cap = (int) Math.min(f.length(), 32 * 1024 * 1024);
            byte[] b = new byte[cap];
            int n = 0, r;
            while (n < cap && (r = in.read(b, n, cap - n)) > 0) n += r;
            if (n < cap) {
                byte[] t = new byte[n];
                System.arraycopy(b, 0, t, 0, n);
                return t;
            }
            return b;
        } finally {
            in.close();
        }
    }

    /** 逐块走 RIFF，不假设头一定是 44 字节。 */
    private static int[] parseWav(byte[] a) throws IOException {
        if (a.length < 12) throw new IOException("文件太短");
        int off = 12, sr = 0, ch = 0, bits = 0, dataOff = -1, dataLen = 0;
        while (off + 8 <= a.length) {
            String id = new String(a, off, 4);
            int sz = le32(a, off + 4);
            int body = off + 8;
            if (body + sz > a.length) sz = a.length - body;
            if (id.equals("fmt ")) {
                ch = le16(a, body + 2);
                sr = le32(a, body + 4);
                bits = le16(a, body + 14);
            } else if (id.equals("data")) {
                dataOff = body;
                dataLen = sz;
            }
            off = body + sz + (sz & 1);
        }
        if (sr == 0 || dataOff < 0) throw new IOException("WAV 缺 fmt/data 块");
        return new int[]{sr, ch, bits, dataOff, dataLen};
    }

    private static int le16(byte[] b, int o) {
        return (b[o] & 0xff) | ((b[o + 1] & 0xff) << 8);
    }

    private static int le32(byte[] b, int o) {
        return (b[o] & 0xff) | ((b[o + 1] & 0xff) << 8)
                | ((b[o + 2] & 0xff) << 16) | ((b[o + 3] & 0xff) << 24);
    }

    private SharedPreferences prefs() {
        return getSharedPreferences("micbridge", Context.MODE_PRIVATE);
    }

    /** WiFi 兜底目标只能手填：平板和电脑现在跨网段且电脑反向 ping 不通，广播/mDNS 发现不了。 */
    private void askLanHost(final Button btn) {
        final EditText e = new EditText(this);
        e.setSingleLine();
        e.setText(bridge.lanHost);
        e.setHint("电脑局域网 IP，如 192.168.168.250");
        new AlertDialog.Builder(this)
                .setTitle("WiFi 兜底地址（端口 " + Bridge.PORT + "）")
                .setView(e)
                .setPositiveButton("保存", new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int id) {
                        String v = e.getText().toString().trim();
                        bridge.lanHost = v;
                        prefs().edit().putString("lan_host", v).apply();
                        btn.setText("WiFi 兜底：电脑 IP = " + (v.length() == 0 ? "未设置" : v));
                        if (bridge.isRunning()) {          // 重选链路
                            bridge.stop();
                            bridge.start();
                        }
                        paint();
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void paint() {
        long up = bridge.isRunning()
                ? (SystemClock.elapsedRealtime() - bridge.startedAt) / 1000 : 0;
        tvState.setText(bridge.state);
        tvState.setTextColor(bridge.state.equals("采麦中") ? Color.rgb(0, 150, 60) : Color.DKGRAY);
        tvData.setText("上行 " + bridge.bytesTotal + " B　"
                + bridge.lastRate + " B/s　峰值 " + bridge.peak + "/32767\n"
                + "链路 " + bridge.link + "　" + bridge.pongState() + "\n"
                + "运行 " + up + "s　重连 " + bridge.reconnects
                + "　欠采 " + bridge.shortReads + "　音源 " + Bridge.srcName(bridge.source));
        level.setPeak(bridge.peak);
    }

    @Override
    protected void onResume() {
        super.onResume();
        hud.post(tick);
    }

    @Override
    protected void onPause() {
        super.onPause();
        hud.removeCallbacks(tick);   // 只是停界面刷新，推流线程和 wakelock 不动
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        bridge.stop();
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    /** 28 段电平，和 ptt 版一致的自绘路子；峰值是窗口内最大值，所以靠衰减让它动起来。 */
    private static class LevelView extends View {
        private final Paint dim = new Paint();
        private final Paint green = new Paint();
        private final Paint amber = new Paint();
        private final Paint red = new Paint();
        private float lit = 0f;
        private long lastNs;

        LevelView(Context c) {
            super(c);
            dim.setColor(Color.rgb(225, 225, 225));
            green.setColor(Color.rgb(0, 180, 90));
            amber.setColor(Color.rgb(230, 180, 0));
            red.setColor(Color.rgb(220, 40, 40));
        }

        void setPeak(long peak) {
            long now = System.nanoTime();
            if (lastNs != 0) {
                float dt = (now - lastNs) / 1e9f;
                lit -= dt * 14f;
                if (lit < 0) lit = 0;
            }
            lastNs = now;
            float want = (float) Math.min(peak, 32767) / 32767f * 28f;
            if (want > lit) lit = want;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas cv) {
            int n = 28;
            float slot = getWidth() / (float) n;
            float bw = slot * 0.78f;
            int h = getHeight();
            for (int i = 0; i < n; i++) {
                float l = i * slot + (slot - bw) / 2f;
                Paint q = i < lit ? (i > 22 ? red : (i > 16 ? amber : green)) : dim;
                cv.drawRect(l, 0, l + bw, h, q);
            }
        }
    }
}
