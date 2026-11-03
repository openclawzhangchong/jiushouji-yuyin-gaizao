package com.zcstudy.micbridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/**
 * modern 变体的保活前台服务（legacy 不编译本类）。
 *
 * Android 11+ 起，退到后台/息屏的普通进程即使持有 PARTIAL_WAKE_LOCK，AudioService 也会
 * 把录音判为 silenced（AudioRecord 读到全 0），dumpsys audio 的 RecordActivityMonitor 里
 * 能看到 "silenced:true"。只有 foregroundServiceType=microphone 的前台服务能继续采麦。
 * 本类只负责把进程抬到前台，采麦/推流仍由 MainActivity 里的 Bridge 线程执行。
 */
public class MicService extends Service {

    private static final String CHANNEL = "micbridge_push";
    private static final int NOTIFY_ID = 1;

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "送话状态",
                    NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }
        Notification n = b.setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentTitle("麦克风桥正在送话")
                .setContentText("息屏后仍继续采麦并推流")
                .setOngoing(true)
                .build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFY_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        } else {
            startForeground(NOTIFY_ID, n);
        }
    }

    @Override
    public int onStartCommand(Intent i, int flags, int startId) {
        return START_NOT_STICKY;
    }
}
