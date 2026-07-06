@echo off
setlocal
set "MT5_EXE=C:\Program Files\MetaTrader 5\terminal64.exe"

if not exist "%MT5_EXE%" (
  echo MT5 not found: "%MT5_EXE%"
  exit /b 1
)

start "MT5 MAIN" "%MT5_EXE%"
