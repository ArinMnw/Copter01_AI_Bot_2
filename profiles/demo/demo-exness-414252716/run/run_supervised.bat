@echo off
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
set BOT_PROFILE=demo-exness-414252716
for /f "delims=" %%T in ('python get_profile_title.py %BOT_PROFILE%') do title %%T
echo ==================================
echo   Copter Gold Bot - demo-exness-414252716
echo   (auto-restart on crash / hang)
echo ==================================
python notify_start.py
start "LTS_AHR3 Supervisor (backtest-driven order)" powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised_lts.ps1" -Portfolio LTS_AHR3
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1" -Profile %BOT_PROFILE%
pause
