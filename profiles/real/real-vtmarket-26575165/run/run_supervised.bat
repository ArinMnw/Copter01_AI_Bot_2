@echo off
title Copter Gold Bot REAL VTMARKET 26575165 (Supervised)
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
echo ==================================
echo   Copter Gold Bot - REAL VTMARKET 26575165
echo   (auto-restart on crash / hang)
echo ==================================
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1" -Profile real-vtmarket-26575165
pause
