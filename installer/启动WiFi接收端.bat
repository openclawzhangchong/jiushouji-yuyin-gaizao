@echo off
cd /d "%~dp0"
title mic-bridge receiver (WiFi)
mic-bridge-receiver.exe --bind 0.0.0.0
pause
