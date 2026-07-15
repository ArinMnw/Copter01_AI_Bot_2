@echo off
title Copter Gold Bot
cd /d "%~dp0.."
set "BOT_PROFILE=demo-iux-2101114448"
set "BOT_PROFILE_ENV="
echo ============================
echo   Copter Gold Bot Starting
echo ============================
python main.py
pause
