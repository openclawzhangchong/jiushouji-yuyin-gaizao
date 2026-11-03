#!/bin/bash
# modern 变体构建：Android 16 / API 36（targetSdk 36）。
#
# ★ 与 legacy 并存，不共用任何产物路径：
#   legacy：build.sh  ->  out/  +  mic-bridge.apk  +  release/mic-bridge-<VER>.apk（minSdk21 / targetSdk22，旧机首选）
#   modern：本脚本    ->  out-a16/ + release/mic-bridge-a16-<VER>.apk（minSdk21 / targetSdk36）
#   本源代码、app/AndroidManifest.xml、app/src、app/res、build.sh 与旧工具链全部不读不写，
#   因此不可能覆盖或破坏旧 APK。
#
# 依赖工具链（与 legacy 独立；本机已装在纯 ASCII 路径 C:\android-build）：
#   JDK 17              C:\android-build\jdk17
#   build-tools 36.0.0  C:\android-build\android-16   （build-tools_r36_windows.zip 解出来的目录名）
#   Platform 36         C:\android-build\android-36\android.jar（platform-36_r02.zip 解出来的目录名）
#   签名                C:\android-build\micbridge.keystore（与 legacy 同一把钥匙，alias=micbridge）
#
# 缺工具链时手动下载（版本已校验 SHA-1，均为官方仓库文件）：
#   curl -L -o bt36.zip https://dl.google.com/android/repository/build-tools_r36_windows.zip      # sha1 f16ccffd34de8790dede813a6c7d8e2c11a27b50
#   curl -L -o p36.zip  https://dl.google.com/android/repository/platform-36_r02.zip              # sha1 2c1a80dd4d9f7d0e6dd336ec603d9b5c55a6f576
set -e
ROOT=/c/android-build
W_ROOT="C:/android-build"
JDK="$ROOT/jdk17"
BT="$ROOT/android-16"
AJ="$W_ROOT/android-36/android.jar"
KS="$W_ROOT/micbridge.keystore"
export JAVA_HOME="C:\\android-build\\jdk17"
export PATH="$JDK/bin:$PATH"
cd "$(dirname "$0")"

MODERN=app/src-modern
OUT=out-a16
MODULE=mic-bridge-a16
VER=${VER:-0.6.0}
VC=${VC:-9}
VN="$VER-a16"          # 版本名带 -a16，装机列表里一眼能和 legacy 区分
PKG=com.zcstudy.micbridge.a16

for f in "$JDK/bin/javac.exe" "$BT/aapt2.exe" "$AJ"; do
  [ -e "$f" ] || { echo "!! 缺工具链：$f（见本文件顶部下载说明）"; exit 1; }
done

rm -rf "$OUT" && mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dexout"

echo "[1/6] aapt2 compile（modern 资源）"
"$BT/aapt2.exe" compile --dir "$MODERN/res" -o "$OUT/compiled.zip"

echo "[2/6] aapt2 link (minSdk 21 / targetSdk 36 / pkg $PKG)"
"$BT/aapt2.exe" link -o "$OUT/base.apk" \
    -I "$AJ" --manifest "$MODERN/AndroidManifest.xml" "$OUT/compiled.zip" \
    --java "$OUT/gen" --min-sdk-version 21 --target-sdk-version 36 \
    --version-code "$VC" --version-name "$VN"

echo "[3/6] javac（modern MainActivity 覆盖 legacy 同名类，Bridge 共用）"
SRC=$(find "$MODERN/java" -name "*.java"; find app/src -name "*.java" ! -name "MainActivity.java")
javac --release 8 -nowarn -encoding UTF-8 -classpath "$AJ" -d "$OUT/classes" \
    $SRC $(find "$OUT/gen" -name "*.java")

echo "[4/6] d8"
( cd "$OUT/classes" && "$JDK/bin/jar.exe" cf ../classes.zip . )
"$BT/d8.bat" --lib "$AJ" --min-api 21 --output "$OUT/dexout" "$OUT/classes.zip"

echo "[5/6] 打包 + zipalign（-P 16：按 16KB 页对齐，Android 15+ 16KB page size 要求）"
cp "$OUT/base.apk" "$OUT/unsigned.apk"
( cd "$OUT/dexout" && "$JDK/bin/jar.exe" uf ../unsigned.apk classes.dex )
# build-tools 36 里 -p 与 -P 互斥：-P 16 已经表示按 16KB 页对齐（同时保证 4 字节对齐）
"$BT/zipalign.exe" -P 16 -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
"$BT/zipalign.exe" -c -P 16 4 "$OUT/aligned.apk"
if "$JDK/bin/jar.exe" tf "$OUT/aligned.apk" | grep -q '^lib/'; then
  echo "!! 包内有 native 库，需逐个确认 16KB 页对齐（llvm-readelf -l 看 LOAD 段）"
  "$JDK/bin/jar.exe" tf "$OUT/aligned.apk" | grep '^lib/' || true
else
  echo "   无 native 库（纯 Java），16KB 页对齐要求不适用，仍已按 16KB 对齐打包"
fi

echo "[6/6] 签名（复用 legacy 的 keystore，同一把钥匙）"
if [ ! -f "$KS" ]; then
  "$JDK/bin/keytool.exe" -genkeypair -keystore "$KS" -alias micbridge \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android -dname "CN=MicBridge, OU=Dev, O=ZC, L=QZ, C=CN"
fi
"$BT/apksigner.bat" sign --ks "$KS" --ks-pass pass:android \
    --key-pass pass:android --out "$OUT/$MODULE.apk" "$OUT/aligned.apk"
"$BT/apksigner.bat" verify --verbose "$OUT/$MODULE.apk" > "$OUT/verify.txt" 2>&1
grep -c 'Verifies' "$OUT/verify.txt" > /dev/null

# 出包前自证：targetSdk 必须真是 36，且包名/版本与本脚本一致
"$BT/aapt2.exe" dump badging "$OUT/$MODULE.apk" > "$OUT/badging.txt" 2>&1
BADGE=$(head -1 "$OUT/badging.txt")
echo "包内版本：$BADGE"
case "$BADGE" in
  *"'$PKG'"*"'$VC'"*"'$VN'"*) ;;
  *) echo "!! 与 PKG=$PKG VC=$VC VN=$VN 不符，拒绝出包"; exit 1 ;;
esac
grep -q "targetSdkVersion:'36'" "$OUT/badging.txt" || {
  echo "!! targetSdkVersion 不是 36，拒绝出包"; exit 1; }

mkdir -p release
REL="release/$MODULE-$VER.apk"
if [ -f "$REL" ] && [ -z "$FORCE_RELEASE" ]; then
  echo "!! $REL 已存在，拒绝覆盖（确实要重发请 FORCE_RELEASE=1）"
else
  cp "$OUT/$MODULE.apk" "$REL"
fi
echo "legacy 产物未触碰：release/mic-bridge-*.apk、mic-bridge.apk、out/"
ls -la "$OUT/$MODULE.apk"
[ -f "$REL" ] && ls -la "$REL"
