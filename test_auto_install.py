#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""不插平板也能验自动安装逻辑：造一个假的 adb（.bat 转发到 .py），
把三种状态各跑一遍，断言 pc_receiver 的 --install-apk 决策正确。

跑法： python test_auto_install.py
不需要设备、不需要 VB-Cable（--install-apk 这条分支不碰音频）。
"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STUB_DIR = os.path.join(tempfile.gettempdir(), "micbridge_stub_adb")
STUB_BAT = os.path.join(STUB_DIR, "adb.bat")

STUB_PY = r'''
import os, sys
state = os.environ.get("STUB_STATE", "absent")
args = sys.argv[1:]
if args[:1] == ["version"]:
    print("Android Debug Bridge Version 9.9.9-stub"); sys.exit(0)
if args[:1] == ["devices"]:
    print("List of devices attached"); print("STUB0001\tdevice"); sys.exit(0)
if args[:2] == ["shell", "dumpsys"]:
    if state == "absent":
        print("Package " + args[2] + " not found"); sys.exit(0)
    ver = {"same": "0.5.0", "newer": "0.9.9"}.get(state, "0.5.0")
    print("    versionName=" + ver); sys.exit(0)
if args[:1] == ["install"]:
    print("Performing Push Install"); print("	pkg: /data/local/tmp/x.apk"); print("Success")
    open(os.environ["STUB_MARK"], "a", encoding="utf-8").write("install " + args[-1] + "\n")
    sys.exit(0)
if args[:1] == ["shell"] and args[1:2] == ["am"]:
    open(os.environ["STUB_MARK"], "a", encoding="utf-8").write("start " + " ".join(args[3:]) + "\n")
    print("Starting: Intent { cmp=com.zcstudy.micbridge/.MainActivity (has extras) }")
    sys.exit(0)
sys.exit(0)
'''


def setup_stub():
    os.makedirs(STUB_DIR, exist_ok=True)
    with open(os.path.join(STUB_DIR, "adb_impl.py"), "w", encoding="utf-8") as f:
        f.write(STUB_PY)
    with open(STUB_BAT, "w", encoding="ascii") as f:
        f.write("@echo off\r\npython \"%~dp0adb_impl.py\" %*\r\n")


def run(state):
    mark = os.path.join(STUB_DIR, "mark_%s.txt" % state)
    if os.path.exists(mark):
        os.remove(mark)
    env = dict(os.environ, STUB_STATE=state, STUB_MARK=mark)
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "pc_receiver.py"),
         "--install-apk", "--adb", STUB_BAT],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=180)
    got = r.stdout + r.stderr
    acted = open(mark, encoding="utf-8").read() if os.path.exists(mark) else ""
    return got, acted


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("   " + detail if detail and not cond else ""))
    return bool(cond)


def main():
    setup_stub()
    print("假 adb 已造在", STUB_BAT)
    ok = True
    out, acts = run("absent")
    print("---- 状态：平板没装过 ----\n" + out.strip())
    ok &= check("判定为『没装过』并执行安装", "没装过" in out and "安装成功" in out)
    ok &= check("确实调用了 adb install", "install " in acts and "mic-bridge-" in acts)
    ok &= check("随后自动开始送话并带上本机 IP", "start -n" in acts and "--es lan" in acts
                and "auto true" in acts)

    out, acts = run("same")
    print("---- 状态：已是同版本 ----\n" + out.strip())
    ok &= check("跳过安装", "跳过安装" in out)
    ok &= check("没有调用 adb install", "install " not in acts)

    out, acts = run("newer")
    print("---- 状态：平板上的版本更新 ----\n" + out.strip())
    ok &= check("拒绝降级", "不降级" in out)
    ok &= check("没有调用 adb install", "install " not in acts)

    print("\n结论：", "全部通过" if ok else "有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
