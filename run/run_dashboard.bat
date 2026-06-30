@echo off
cd /d "%~dp0.."
echo ========================================================
echo   Copter Gold Bot - Web Dashboard
echo ========================================================
echo.
echo Checking for required libraries...
pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo [Installing Streamlit and Pandas...]
    pip install streamlit pandas
)

echo.
echo Starting the dashboard...
echo Please do not close this window while viewing the dashboard.
echo.
streamlit run dashboard.py
pause
