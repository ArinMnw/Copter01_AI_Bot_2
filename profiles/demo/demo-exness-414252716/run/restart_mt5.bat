@echo off
setlocal
call "%~dp0close_mt5.bat"
timeout /t 2 /nobreak >nul
call "%~dp0open_mt5.bat"

