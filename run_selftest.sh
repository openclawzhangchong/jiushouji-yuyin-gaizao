#!/bin/bash
# 无人值守回归：平板自己外放已知音频 -> 自己的麦克风听回来 -> USB -> CABLE Output 录下 -> 出数字。
#
# 为什么不让电脑放声音：这台主机的显示器（MG2461VI）没有扬声器，电脑外放是静音的，
# 只会得到"全零/底噪"的假失败。必须让平板自己播、自己听。
#
# 跑法： bash run_selftest.sh [素材路径] [录音秒数]
#   素材默认 /sdcard/Music/loop2.wav.off（≈10.9s 已知中文，平板上现成留着）
#   判据三条：心跳速率≈32000B/s 且欠采0 / 外放段峰值≥-4dBFS / ASR 逐字复现原文
set -u

CLIP=${1:-/sdcard/Music/loop2.wav.off}
RECS=${2:-34}
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=${LOG:-$HERE/out_selftest.log}

# adb：winget 装的 PlatformTools 不在新 shell 的 PATH 里，按已知路径找，再退回 PATH
ADB="$LOCALAPPDATA/Microsoft/WinGet/Packages/Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe/platform-tools/adb.exe"
[ -f "$ADB" ] || ADB=adb

PY=""
for c in "$HERE/.venv/Scripts/python.exe" "$HERE/../jiushouji-yuyin-gaizao-build/venv/Scripts/python.exe" python; do
  if command -v "$c" >/dev/null 2>&1 || [ -f "$c" ]; then PY="$c"; break; fi
done
echo "adb = $ADB"
echo "py  = $PY"
echo "素材= $CLIP"

"$ADB" devices -l | sed -n '2,3p'
if ! "$ADB" shell ls "$CLIP" >/dev/null 2>&1; then
  echo "!! 平板上没有 $CLIP"
  echo "   要么用现成的（adb shell ls /sdcard/Music），要么推进一个 16bit 单声道 wav："
  echo "   MSYS_NO_PATHCONV=1 adb push E:/路径/demo.wav /sdcard/Music/demo.wav"
  echo "   然后： bash run_selftest.sh /sdcard/Music/demo.wav"
  exit 1
fi

"$ADB" logcat -c
"$ADB" shell am force-stop com.zcstudy.micbridge

# 接收端自己开 16k 单声道采集；--record 会同时从 CABLE Output 录 RECS 秒并写 verify.wav
"$PY" "$HERE/pc_receiver.py" --record "$RECS" > "$HERE/out_receiver.log" 2>&1 &
RP=$!
sleep 5

# 注意 --ez 只认 true/false，写 1 会被解析成 false
MSYS_NO_PATHCONV=1 "$ADB" shell am start -n com.zcstudy.micbridge/.MainActivity \
    --ez auto true --es act selftest --es demo "$CLIP" >/dev/null

sleep $((RECS + 6))
kill "$RP" 2>/dev/null; wait "$RP" 2>/dev/null

echo
echo "=== 平板心跳（速率应≈32000B/s，欠采应为 0）==="
"$ADB" logcat -d -v brief -s MICBRIDGE:V 2>&1 | tr -d '\r' | grep -E "已连|心跳|自测|断开" | tail -12
echo
echo "=== 接收端 ==="
tail -6 "$HERE/out_receiver.log"
echo
echo "=== 包络与频谱 ==="
"$PY" "$HERE/look.py" 2>&1 | head -8
echo
echo "=== 识别（期望逐字复现素材原文）==="
# ws-transcribe.mjs 是 CapsWriter 试点留下的现成客户端脚本，在仓库外的同级目录
WS=""
for c in "$HERE/../yuyin-shuru-trial/test/ws-transcribe.mjs" \
         "$(dirname "$HERE")/yuyin-shuru-trial/test/ws-transcribe.mjs" \
         "/e/github项目/yuyin-shuru-trial/test/ws-transcribe.mjs"; do
  [ -f "$c" ] && WS="$c" && break
done
if [ -n "$WS" ] && [ -f "$HERE/verify.wav" ]; then
  # 先确认 ASR 服务在跑（6016），没跑就只给命令不擅自启动别人的程序
  if ! netstat -ano 2>/dev/null | grep -q ":6016.*LISTENING"; then
    echo "!! ASR 服务没在跑。先启动 CapsWriter 的 start_server.exe，再跑："
    echo "   node \"$WS\" \"$HERE\\verify.wav\" zh"
  else
    node "$WS" "$(cygpath -w "$HERE/verify.wav" 2>/dev/null || echo "$HERE/verify.wav")" zh 2>&1 | tail -6
  fi
else
  echo "没找到 ws-transcribe.mjs 或 verify.wav。素材录好后手动跑："
  echo "  node <yuyin-shuru-trial>/test/ws-transcribe.mjs verify.wav zh"
fi
echo
echo "日志： $LOG / out_receiver.log / verify.wav"
