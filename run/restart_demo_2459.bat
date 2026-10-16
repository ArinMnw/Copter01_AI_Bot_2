@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\restart_demo_2459.ps1"
if errorlevel 1 pause
