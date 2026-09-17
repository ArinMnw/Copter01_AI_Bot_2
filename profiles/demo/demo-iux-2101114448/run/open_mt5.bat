@echo off
setlocal
set "PROFILE_DIR=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%PROFILE_DIR%\mt5\config\common.ini'; if (Test-Path $p) { $e=[Text.Encoding]::Default; $t=[IO.File]::ReadAllText($p,$e); if ($t -notmatch '(?m)^\[Experts\]') { $t=$t.TrimEnd()+\"`r`n[Experts]`r`nAllowDllImport=0`r`nEnabled=1`r`nAccount=0`r`nProfile=0`r`nChart=0`r`nApi=0`r`nDisableOpenCL=`r`nWebRequest=0`r`nWebRequestUrl=`r`n\" } else { $t=[regex]::Replace($t,'(?m)^Enabled=\d+','Enabled=1',1); $t=[regex]::Replace($t,'(?m)^Account=\d+','Account=0',1); $t=[regex]::Replace($t,'(?m)^Profile=\d+','Profile=0',1) }; [IO.File]::WriteAllText($p,$t,$e) }"
start "MT5 DEMO IUX 2101114448" "%PROFILE_DIR%\mt5\terminal64.exe" /portable /login:2101114448 /password:cop04TERZ_18 /server:IUXMarkets-Demo
