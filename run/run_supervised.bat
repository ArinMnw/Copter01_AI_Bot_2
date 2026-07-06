@echo off
title Copter Gold Bot (Supervised)
chcp 65001 >nul
cd /d "%~dp0.."

echo ==================================
echo   Copter Gold Bot - Supervised
echo   (auto-restart on crash / hang)
echo ==================================

python notify_start.py

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1"
pause
