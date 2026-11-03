# -*- mode: python ; coding: utf-8 -*-
"""免管理员安装版的打包配置（PyInstaller onedir）。

为什么用 onedir 而不是 onefile：
  onefile 每次启动都会把自身解压到 %TEMP%\\_MEIxxxx 再执行 —— "自解压到临时目录再运行"
  是杀软启发式最典型的特征之一，而且启动更慢。安装版本来就是把文件装进目录，
  用 onedir 既没有临时解包，也不会因为解包被杀软拦下来。
  （仓库里 installer/ 的 onefile 构建方式保持不变，两条链并存。）

也不开 UPX：UPX 压缩过的 PyInstaller 程序是误报重灾区。

构建：  python -m PyInstaller --noconfirm --clean ^
            --distpath dist\\windows --workpath build_tmp packaging\\mic_bridge_receiver.spec
"""
import glob
import os
import re

SPEC_DIR = os.path.abspath(SPECPATH)   # PyInstaller 已把 SPECPATH 设为本 .spec 所在目录
ROOT = os.path.dirname(SPEC_DIR)


def latest_apk():
    """内置最新版 APK（程序启动时自己也会按版本号挑；only-latest 免得把全部历史包都塞进 exe）。"""
    cands = glob.glob(os.path.join(ROOT, "release", "mic-bridge-*.apk"))

    def ver(p):
        m = re.search(r"mic-bridge-([0-9][0-9.]*)\.apk$", os.path.basename(p))
        return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)

    return max(cands, key=ver) if cands else None


APK = latest_apk()
datas = [(APK, "release")] if APK else []

# platform-tools 存在就一起带上（adb.exe + 两个 dll）；没有就退回用系统/已装 adb
PT = os.path.join(ROOT, "platform-tools")
if os.path.isdir(PT):
    datas.append((PT, "platform-tools"))

a = Analysis(
    [os.path.join(ROOT, "pc_receiver.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=["pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mic-bridge-receiver",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                       # 托盘程序，不要黑窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPEC_DIR, "mic-bridge.ico"),
    version=os.path.join(SPEC_DIR, "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Jiushouji-Mic",
)
