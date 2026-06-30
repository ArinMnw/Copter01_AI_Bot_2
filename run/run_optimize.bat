@echo off
cd /d "%~dp0.."
echo ========================================================
echo   Copter Gold Bot - Walk-Forward Optimization
echo ========================================================
echo.
echo Running optimization script...
python walk_forward.py
echo.
echo Please restart the bot (run\run.bat) to apply the new settings!
echo.
pause
