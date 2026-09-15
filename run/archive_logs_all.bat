@echo off
REM run\archive_logs_all.bat -- archive logs to monthly files for the MAIN instance
REM AND every profile under profiles\demo\* and profiles\real\* — wraps the
REM same archive_logs_by_month.py that each individual run\archive_logs.bat
REM (root and per-profile) calls, so results are identical to running them
REM one by one, just automated across all of them in one go.
REM Usage: run\archive_logs_all.bat [--dry-run]
REM Stop all running bot instances first to avoid file-lock errors.
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0.."

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYCMD=python"
) else (
    set "PYCMD=py"
)

set FAILCOUNT=0

echo.
echo ============================================================
echo [archive_logs_all] Main instance
echo ============================================================
%PYCMD% archive_logs_by_month.py %*
if not !ERRORLEVEL!==0 (
    echo [archive_logs_all] Main instance FAILED ^(exit !ERRORLEVEL!^)
    set /a FAILCOUNT+=1
)

for /d %%P in ("profiles\demo\*") do (
    if exist "%%P\profile.env" (
        echo.
        echo ============================================================
        echo [archive_logs_all] Profile: %%~nxP
        echo ============================================================
        %PYCMD% archive_logs_by_month.py --profile %%~nxP %*
        if not !ERRORLEVEL!==0 (
            echo [archive_logs_all] %%~nxP FAILED
            set /a FAILCOUNT+=1
        )
    )
)

for /d %%P in ("profiles\real\*") do (
    if exist "%%P\profile.env" (
        echo.
        echo ============================================================
        echo [archive_logs_all] Profile: %%~nxP
        echo ============================================================
        %PYCMD% archive_logs_by_month.py --profile %%~nxP %*
        if not !ERRORLEVEL!==0 (
            echo [archive_logs_all] %%~nxP FAILED
            set /a FAILCOUNT+=1
        )
    )
)

echo.
echo ============================================================
if !FAILCOUNT!==0 (
    echo [archive_logs_all] Done. All instances archived successfully.
) else (
    echo [archive_logs_all] Done with !FAILCOUNT! failure^(s^) - see log above.
)
echo ============================================================
echo.
pause
