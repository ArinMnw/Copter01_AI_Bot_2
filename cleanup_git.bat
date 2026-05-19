@echo off
REM ============================================================
REM  cleanup_git.bat — Manual cleanup สำหรับ .git folder
REM  ใช้เมื่อ .git บวมเกินที่ auto-gc จัดการได้
REM  - ลบ reflog entries ทั้งหมด
REM  - pack objects แบบ aggressive
REM  - prune unreachable blobs
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo  Git Cleanup Script
echo ============================================================
echo.

REM ── เช็คขนาดก่อน ──
echo [1/4] ขนาด .git ปัจจุบัน:
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "$size = (Get-ChildItem -Recurse -Force '.git' | Measure-Object -Property Length -Sum).Sum / 1MB; '{0:N1} MB' -f $size"') do echo       %%a
echo.

REM ── คำเตือน ──
echo [2/4] กำลังจะทำ:
echo        - git reflog expire --expire=now --all
echo        - git gc --aggressive --prune=now
echo.
echo        ไฟล์ใน logs/ และ working tree จะไม่ถูกแตะ
echo        (ทำเฉพาะใน .git folder)
echo.
set /p CONFIRM="ทำต่อหรือไม่? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo ยกเลิก
    exit /b 0
)

REM ── ทำ ──
echo.
echo [3/4] ล้าง reflog ...
git reflog expire --expire=now --all
if errorlevel 1 (
    echo Error: reflog expire ล้มเหลว
    exit /b 1
)

echo        รัน gc --aggressive --prune=now ^(อาจใช้เวลานาน^) ...
git gc --aggressive --prune=now
if errorlevel 1 (
    echo Error: gc ล้มเหลว
    exit /b 1
)

REM ── เช็คขนาดหลัง ──
echo.
echo [4/4] ขนาด .git หลัง cleanup:
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "$size = (Get-ChildItem -Recurse -Force '.git' | Measure-Object -Property Length -Sum).Sum / 1MB; '{0:N1} MB' -f $size"') do echo       %%a
echo.

echo ============================================================
echo  เสร็จเรียบร้อย!
echo ============================================================
pause
