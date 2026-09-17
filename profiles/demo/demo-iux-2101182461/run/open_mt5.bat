@echo off
setlocal
set "PROFILE_DIR=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%PROFILE_DIR%\mt5\config\common.ini'; if (Test-Path $p) { $e=[Text.Encoding]::Default; $t=[IO.File]::ReadAllText($p,$e); $t=[regex]::Replace($t,'(?m)^Enabled=\d+','Enabled=1',1); $t=[regex]::Replace($t,'(?m)^Account=\d+','Account=0',1); $t=[regex]::Replace($t,'(?m)^Profile=\d+','Profile=0',1); [IO.File]::WriteAllText($p,$t,$e) }"
start "MT5 DEMO IUX 2101182461" "%PROFILE_DIR%\mt5\terminal64.exe" /portable /login:2101182461 /password:cop04TERZ_ /server:IUXMarkets-Demo
