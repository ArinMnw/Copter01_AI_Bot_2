@echo off
setlocal
if not "%MT5_PATH%"=="" (
  set "MT5_EXE=%MT5_PATH%"
) else if exist "C:\MT5\terminal64.exe" (
  set "MT5_EXE=C:\MT5\terminal64.exe"
) else (
  set "MT5_EXE=C:\Program Files\MetaTrader 5\terminal64.exe"
)

if not exist "%MT5_EXE%" (
  echo MT5 not found: "%MT5_EXE%"
  exit /b 1
)

start "MT5 MAIN" "%MT5_EXE%"
