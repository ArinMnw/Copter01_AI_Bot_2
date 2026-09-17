@echo off
REM Archive DEMO profile logs to monthly files.
chcp 65001 >nul
cd /d "%~dp0..\..\..\.."
echo.
echo [archive_logs] Archiving DEMO IUX 2101114448 logs to monthly files...
echo.
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python archive_logs_by_month.py --profile demo-iux-2101114448 %*
) else (
    py archive_logs_by_month.py --profile demo-iux-2101114448 %*
)
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
    echo [archive_logs] Done.
) else (
    echo [archive_logs] Error exit code %RC%
)
echo.
pause
