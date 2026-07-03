@echo off
title Copter Gold Bot DEMO IUX 2101114448 (Supervised)
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."

echo ==================================
echo   Copter Gold Bot - DEMO IUX 2101114448
echo   (auto-restart on crash / hang)
echo ==================================

set BOT_PROFILE=demo-iux-2101114448

:: แจ้ง Telegram ว่า bot เริ่มทำงาน (ส่ง + pin message)
python notify_start.py

:: เวลาปัจจุบัน format DD-MM-YYYY HH:MM สำหรับ S20.12 supervisor
for /f "tokens=1-5 delims=/ " %%a in ('echo %date%') do set D=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ('echo %time%') do (set HH=%%a & set MM=%%b)
set HH=%HH: =%
set START_TIME=%D% %HH%:%MM%

:: เปิด S20.12 supervisor ใน window แยก (state file อยู่ใน profile dir อัตโนมัติ)
start "S20.12 Supervisor [DEMO]" python strategy/s20.12/backtest-sim/supervisor_s20_12.py ^
  --start "%START_TIME%" --compound 2 --tf all

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1" -Profile demo-iux-2101114448
pause
