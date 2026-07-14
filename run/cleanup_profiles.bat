@echo off
title MT5 Profile Cleanup Helper
chcp 65001 >nul
cd /d "%~dp0"

echo ===========================================
echo   MT5 Profiles Disk Space Cleanup Utility
echo ===========================================
echo.
python "%~dp0cleanup_mt5_profiles.py"
echo.
pause
