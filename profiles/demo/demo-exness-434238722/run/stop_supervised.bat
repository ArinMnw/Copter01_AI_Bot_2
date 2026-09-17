@echo off
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
title Copter Gold Bot - STOP (demo-exness-434238722)

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-434238722
pause
