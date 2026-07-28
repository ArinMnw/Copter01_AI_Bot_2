@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Copter Gold Bot - STOP (root/main)

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1"
pause
