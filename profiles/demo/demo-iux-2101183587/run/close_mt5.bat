@echo off
setlocal
set "PROFILE_DIR=%~dp0.."
set "EXE=%PROFILE_DIR%\mt5\terminal64.exe"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe = [IO.Path]::GetFullPath('%EXE%'); Get-CimInstance Win32_Process -Filter \"name='terminal64.exe'\" | Where-Object { $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -ieq $exe) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

