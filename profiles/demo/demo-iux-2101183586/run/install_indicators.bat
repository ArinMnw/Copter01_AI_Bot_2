@echo off
setlocal
set "ROOT=%~dp0..\..\..\.."
set "PROFILE_DIR=%~dp0.."
set "SRC=%ROOT%\mql5"
set "DST=%PROFILE_DIR%\mt5\MQL5\Indicators\Copter"

if not exist "%DST%" mkdir "%DST%"
copy /Y "%SRC%\*.mq5" "%DST%\" >nul
echo Copied indicators to "%DST%"
echo Open MetaEditor/MT5 Navigator and compile or refresh indicators if needed.
