@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if defined BOT_PROFILE (
    for /f "delims=" %%T in ('python get_profile_title.py %BOT_PROFILE%') do title %%T
) else (
    title Copter Gold Bot (Supervised)
)

echo ==================================
echo   Copter Gold Bot - Supervised
echo   (auto-restart on crash / hang)
echo ==================================

python notify_start.py

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1"
pause
