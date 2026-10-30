#!/bin/bash
# 无 Gradle / 无 Android Studio 出包：aapt2 -> javac -> d8 -> zipalign -> apksigner
# 沿用 xiaole-ptt-android5-2027/build.sh 的成熟流程，只是这台的工具链不在 D:/android-build
#
# 路径两种写法不能混：程序本身和 PATH 用 POSIX 风格（/c/...），
# 传给原生 exe 的参数用 Windows 风格（C:/...），否则 JVM 打不开文件。
# ★ 工具链必须放在纯 ASCII 路径：aapt2 会 stat 不到「E:/github项目/...」里的 android.jar。
set -e
ROOT=/c/android-build
W_ROOT="C:/android-build"
JDK="$ROOT/jdk17"
BT="$ROOT/android-14"                  # build-tools_r34-windows.zip 解出来的目录名就是 android-14
AJ="$W_ROOT/android-5.0.1/android.jar" # android-21_r02.zip 解出来的目录名是 android-5.0.1
KS="$W_ROOT/micbridge.keystore"
export JAVA_HOME="C:\\android-build\\jdk17"
export PATH="$JDK/bin:$PATH"
cd "$(dirname "$0")"

MODULE=${MODULE:-mic-bridge}
VER=${VER:-0.1.0}
VC=${VC:-1}
PKG=com.zcstudy.micbridge

rm -rf out && mkdir -p out/gen out/classes out/dexout

echo "[1/6] aapt2 compile 资源"
"$BT/aapt2.exe" compile --dir app/res -o out/compiled.zip

echo "[2/6] aapt2 link (minSdk 21 / targetSdk 22)"
# 资源用位置参数传，不能用 -R：-R 是 overlay 语义，定义新名字会报
# "resource string/app_name does not override an existing resource"
"$BT/aapt2.exe" link -o out/base.apk \
    -I "$AJ" --manifest app/AndroidManifest.xml out/compiled.zip \
    --java out/gen --min-sdk-version 21 --target-sdk-version 22 \
    --version-code "$VC" --version-name "$VER"

echo "[3/6] javac"
mkdir -p out/classes
javac --release 8 -nowarn -encoding UTF-8 \
    -classpath "$AJ" -d out/classes $(find app/src out/gen -name "*.java")

echo "[4/6] d8"
( cd out/classes && "$JDK/bin/jar.exe" cf ../classes.zip . )
"$BT/d8.bat" --lib "$AJ" --min-api 21 --output out/dexout out/classes.zip

echo "[5/6] 打包 + zipalign"
cp out/base.apk out/unsigned.apk
( cd out/dexout && "$JDK/bin/jar.exe" uf ../unsigned.apk classes.dex )
"$BT/zipalign.exe" -p -f 4 out/unsigned.apk out/aligned.apk

echo "[6/6] 签名"
if [ ! -f "$KS" ]; then
  "$JDK/bin/keytool.exe" -genkeypair -keystore "$KS" -alias micbridge \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android -dname "CN=MicBridge, OU=Dev, O=ZC, L=QZ, C=CN"
fi
"$BT/apksigner.bat" sign --ks "$KS" --ks-pass pass:android \
    --key-pass pass:android --out "$MODULE.apk" out/aligned.apk
# 注意：这里不能 `| head`，SIGPIPE 会让 set -e 把成功的构建误判为失败
"$BT/apksigner.bat" verify --verbose "$MODULE.apk" > out/verify.txt 2>&1
grep -c 'Verifies' out/verify.txt > /dev/null

# 出包前自证：包里的 versionName/versionCode 必须和这份脚本写的一致
"$BT/aapt2.exe" dump badging "$MODULE.apk" > out/badging.txt 2>&1
BADGE=$(head -1 out/badging.txt)
echo "包内版本：$BADGE"
case "$BADGE" in
  *"'$VC'"*"'$VER'"*) ;;
  *) echo "!! 与 VC=$VC VER=$VER 不符，拒绝出包"; exit 1 ;;
esac
mkdir -p release
REL="release/$MODULE-$VER.apk"
if [ -f "$REL" ] && [ -z "$FORCE_RELEASE" ]; then
  echo "!! $REL 已存在，拒绝覆盖（确实要重发请 FORCE_RELEASE=1）"
else
  cp "$MODULE.apk" "$REL"
fi
ls -la "$MODULE.apk" release/
