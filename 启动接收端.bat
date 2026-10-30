@echo off
rem mic-bridge receiver launcher. Close this window to stop the virtual microphone feed.
rem Needs: VB-Cable installed, tablet connected with USB debugging authorized, adb installed.
rem Run setup_windows.ps1 first on a fresh machine (it installs adb + VB-Cable + the .venv).
chcp 65001 >nul
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%LOCALAPPDATA%\Temp\jjsound\probe-venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [mic-bridge] python = %PY%
"%PY%" pc_receiver.py %*
pause
