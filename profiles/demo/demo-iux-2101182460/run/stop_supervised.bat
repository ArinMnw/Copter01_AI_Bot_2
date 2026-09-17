@echo off
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
title Copter Gold Bot - STOP (demo-iux-2101182460)

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182460
pause
