@echo off
title Copter Gold Bot (Supervised)
chcp 65001 >nul
cd /d "%~dp0.."

echo ==================================
echo   Copter Gold Bot - Supervised
echo   (auto-restart on crash / hang)
echo ==================================

python notify_start.py

for /f "tokens=1-5 delims=/ " %%a in ('echo %date%') do set D=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ('echo %time%') do (set HH=%%a & set MM=%%b)
set HH=%HH: =%
set /a MM=%MM%-1
if %MM% LSS 0 (set MM=59 & set /a HH=%HH%-1)
if %HH% LSS 0 set HH=23
if %MM% LSS 10 set MM=0%MM%
if %HH% LSS 10 set HH=0%HH%
set START_TIME=%D% %HH%:%MM%

del /f /q ".supervisor_s2012_state" 2>nul

start "S20.12 Supervisor" python strategy/s20.12/backtest-sim/supervisor_s20_12.py ^
  --start "%START_TIME%" --compound 2 --tf all

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1"
pause
