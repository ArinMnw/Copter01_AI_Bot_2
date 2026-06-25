# run_supervised.ps1 — External supervisor for Copter Gold Bot
# ------------------------------------------------------------------
# ทำไมต้องมี: bot รันทุกอย่างบน asyncio event loop เดียว และ MetaTrader5 API
# เป็น blocking C-call ถ้า MT5 terminal ค้าง (IPC hang) → loop แข็งทั้งตัว
# รวมถึง in-process watchdog เอง → แจ้งเตือน/กู้ตัวเองไม่ได้
# supervisor นี้รันแยก process จึงรอด แล้วใช้ bot_heartbeat.txt จับ hang:
#   - main.py เขียน ts ลง heartbeat ทุก ~15s (heartbeat_job)
#   - ถ้า ts ค้างเกิน $StaleSec = loop แข็ง → kill + restart
#   - ถ้า process ตายเอง → restart
#
# วิธีรัน:  powershell -ExecutionPolicy Bypass -NoProfile -File run_supervised.ps1
#          หรือดับเบิลคลิก run_supervised.bat
# หยุด:    Ctrl+C (bot ที่รันอยู่จะกลายเป็น orphan แต่ยังเทรดต่อ — ปิดเองถ้าต้องการ)

param(
    [int]$StaleSec   = 180,   # ts ค้างเกินเท่านี้ (วินาที) = loop hang → restart
    [int]$CheckEvery = 30,    # คาบ monitor (วินาที)
    [int]$GraceSec   = 90,    # ผ่อนผันหลัง start ก่อนเริ่มเช็ค heartbeat (รอ MT5 connect/restore)
    [int]$RestartGap = 5,     # หน่วงก่อน relaunch (วินาที)
    # "python" เฉยๆ อาจ resolve ผ่าน PATH ไปโดน interpreter อื่นที่ไม่มี
    # MetaTrader5/telegram/apscheduler ติดตั้งอยู่ (เคยเกิดจริง: ไปโดน venv ของ
    # เครื่องมืออื่นที่ไม่เกี่ยวกับ bot นี้ ทำให้ main.py ขึ้น ModuleNotFoundError
    # แล้ว crash-loop ทุก ~30s) — ระบุ path เต็มของ interpreter ที่ลง dependency
    # ของ bot นี้ไว้ตรงๆ กัน PATH เปลี่ยนแล้วพังเงียบๆ
    [string]$Python  = "C:\Users\Copter\AppData\Local\Programs\Python\Python313\python.exe"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$HeartbeatFile = Join-Path $PSScriptRoot "bot_heartbeat.txt"
$LogDir        = Join-Path $PSScriptRoot "logs"
$LogFile       = Join-Path $LogDir "supervisor.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Log($msg) {
    $ts   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    try { Add-Content -Path $LogFile -Value $line -Encoding UTF8 } catch {}
}

function Read-HeartbeatTs {
    # คืน epoch (long) จากบรรทัด ts=... ของ heartbeat; คืน $null ถ้าอ่านไม่ได้
    if (-not (Test-Path $HeartbeatFile)) { return $null }
    try {
        $line = Get-Content $HeartbeatFile -TotalCount 1 -ErrorAction Stop
        if ($line -match '^ts=(\d+)') { return [long]$Matches[1] }
    } catch { return $null }
    return $null
}

Write-Log "Supervisor started (stale=$StaleSec s, check=$CheckEvery s, grace=$GraceSec s, python='$Python')"

while ($true) {
    # ลบ heartbeat เก่าก่อน start เพื่อไม่ให้อ่าน ts ค้างจากรอบก่อนมาตัดสินผิด
    if (Test-Path $HeartbeatFile) { Remove-Item $HeartbeatFile -Force -ErrorAction SilentlyContinue }

    Write-Log "Launching: $Python main.py"
    try {
        $proc = Start-Process -FilePath $Python -ArgumentList "main.py" -PassThru -NoNewWindow
    } catch {
        Write-Log "ERROR launching python: $_  — retry in $RestartGap s"
        Start-Sleep -Seconds $RestartGap
        continue
    }
    $startedAt = Get-Date
    Write-Log "main.py running (pid=$($proc.Id))"

    while ($true) {
        Start-Sleep -Seconds $CheckEvery

        # 1) process ตายเอง? → restart
        if ($proc.HasExited) {
            Write-Log "main.py exited (code=$($proc.ExitCode)) -> restart"
            break
        }

        # 2) heartbeat stale? (ข้ามช่วง grace หลัง start)
        $upSec = [int]((New-TimeSpan -Start $startedAt -End (Get-Date)).TotalSeconds)
        if ($upSec -lt $GraceSec) { continue }

        $ts = Read-HeartbeatTs
        if ($null -eq $ts) {
            Write-Log "WARN: heartbeat missing/unreadable (up=${upSec}s) — wait next cycle"
            continue
        }
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $age = [int]($now - $ts)
        if ($age -gt $StaleSec) {
            Write-Log "STALL: heartbeat age=${age}s > ${StaleSec}s (loop hang) -> kill pid=$($proc.Id) + restart"
            try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch { Write-Log "kill error: $_" }
            try { $proc.WaitForExit(10000) | Out-Null } catch {}
            break
        }
    }

    Write-Log "Restarting in $RestartGap s ..."
    Start-Sleep -Seconds $RestartGap
}
