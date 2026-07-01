@echo off
title Copter Gold Bot DEMO IUX 2101114448 (Supervised)
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
echo ==================================
echo   Copter Gold Bot - DEMO IUX 2101114448
echo   (auto-restart on crash / hang)
echo ==================================
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1" -Profile demo-iux-2101114448
pause
