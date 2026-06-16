@echo off
title Copter Gold Bot (Supervised)
cd /d "%~dp0"
echo ==================================
echo   Copter Gold Bot - Supervised
echo   (auto-restart on crash / hang)
echo ==================================
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0run_supervised.ps1"
pause
