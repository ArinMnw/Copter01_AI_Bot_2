@echo off
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
set BOT_PROFILE=real-vtmarket-26575165
for /f "delims=" %%T in ('python get_profile_title.py %BOT_PROFILE%') do title %%T
echo ==================================
echo   Copter Gold Bot - real-vtmarket-26575165
echo   (auto-restart on crash / hang)
echo ==================================
python notify_start.py
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1" -Profile %BOT_PROFILE%
pause
