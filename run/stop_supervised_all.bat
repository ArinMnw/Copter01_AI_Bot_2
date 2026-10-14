@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Copter Gold Bot - STOP ALL (root + 13 profiles)

echo ==================================
echo   Copter Gold Bot - Stop ALL
echo   (root/main + 13 demo profiles)
echo ==================================
echo.
echo Phase 1/2: stopping every instance...
echo.

echo [1/14] root/main...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -SkipWindowClose

echo [2/14] demo-exness-416010472...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-416010472 -SkipWindowClose

echo [3/14] demo-exness-433881786...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-433881786 -SkipWindowClose

echo [4/14] demo-iux-2101182459...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182459 -SkipWindowClose

echo [5/14] demo-iux-2101182460...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182460 -SkipWindowClose

echo [6/14] demo-iux-2101182461...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182461 -SkipWindowClose

echo [7/14] demo-iux-2101183586...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101183586 -SkipWindowClose

echo [8/14] demo-iux-2101183587...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101183587 -SkipWindowClose

echo [9/14] demo-exness-416273786 (AUS3)...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-416273786 -SkipWindowClose

echo [10/14] demo-exness-414252716 (AHR3)...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-414252716 -SkipWindowClose

echo [11/14] demo-exness-434237129 (S20 Institutional)...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-434237129 -SkipWindowClose

echo [12/14] demo-exness-434238722 (15 ML Groups)...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-434238722 -SkipWindowClose

echo [13/14] demo-vantage-26253671...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-vantage-26253671 -SkipWindowClose

echo [14/14] demo-vantage-26257644...
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-vantage-26257644 -SkipWindowClose

echo.
echo Phase 2/2: closing leftover windows...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-416010472 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-433881786 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182459 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182460 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101182461 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101183586 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-iux-2101183587 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-416273786 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-414252716 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-434237129 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-exness-434238722 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-vantage-26253671 -OnlyCloseWindow
powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\stop_supervised.ps1" -Profile demo-vantage-26257644 -OnlyCloseWindow

echo.
echo ==================================
echo   All 14 instances stopped and
echo   leftover windows closed.
echo   marker written for each -- guard
echo   script will NOT auto-restart them.
echo ==================================
pause
