@echo off
REM archive_logs.bat -- archive bot/system/error logs to monthly files
REM Usage: archive_logs.bat [--dry-run]
REM Stop the bot first to avoid file-lock errors
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo [archive_logs] Archiving logs to monthly files...
echo.
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python archive_logs_by_month.py %*
) else (
    py archive_logs_by_month.py %*
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
