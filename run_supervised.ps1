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
    # ปล่อยว่างไว้ = auto-detect (ดู Resolve-Python ด้านล่าง) — ระบุเองได้ถ้าต้องการ
    # บังคับ interpreter ตัวใดตัวหนึ่งเจาะจง (เช่น -Python "py" -PythonArgs "-3.11")
    [string]$Python,
    [string]$PythonArgs
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Test-PythonCandidate([string]$exe, [string[]]$extraArgs) {
    # คืน $true ถ้า interpreter ตัวนี้เรียกได้จริง และมี dependency หลักของบอทครบ
    # (MetaTrader5/telegram/apscheduler) — กัน false positive จากแค่ "เจอ exe"
    # แต่ดันเป็น venv ของเครื่องมืออื่นที่ไม่เกี่ยวกับบอทนี้
    try {
        $argList = @($extraArgs) + @("-c", "import MetaTrader5, telegram, apscheduler")
        & $exe @argList *>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-Python {
    # ลองหลาย candidate ตามลำดับ เพราะเครื่องต่างกัน (local PC vs VPS) อาจมี
    # "python"/"py" ผูกกับ environment ที่ลง dependency ของบอทไว้คนละตัวกัน —
    # เคยพังมาแล้วทั้ง 2 ทาง (hardcode path เครื่องเดียวพังข้ามเครื่อง, เปลี่ยนเป็น
    # "py -3" ตายตัวก็พังกับเครื่องที่ dependency อยู่ใน "python" PATH ธรรมดา)
    # จึงต้อง "ทดสอบจริง" แทนเดาเฉยๆ ว่าตัวไหนของเครื่องนี้ใช้ได้
    $candidates = @(
        @{ Exe = "python"; Args = @() },
        @{ Exe = "py";      Args = @("-3") },
        @{ Exe = "py";      Args = @() }
    )
    foreach ($c in $candidates) {
        if (Test-PythonCandidate $c.Exe $c.Args) {
            # resolve ไปเป็น python.exe ตัวจริง (sys.executable) แทนคืนแค่
            # "py"/"-3" ตรงๆ — ถ้าใช้ "py" เป็น $Python ตอน Start-Process, py.exe
            # จะเป็น parent process แล้ว spawn python.exe ตัวจริงเป็น child แยก PID
            # ทำให้ตอน kill-on-stall (Stop-Process -Id $proc.Id) ฆ่าได้แค่ py.exe
            # ตัว python.exe ที่รัน main.py จริง (ค้างอยู่) จะรอดเป็น orphan แล้ว
            # supervisor ไป spawn อีกตัวซ้อน เกิด process ซ้ำ (เคสจริง: Telegram
            # getUpdates Conflict) — ต้อง resolve ให้ $proc.Id ตรงกับ python.exe จริง
            try {
                $checkArgs = @($c.Args) + @("-c", "import sys; print(sys.executable)")
                $realExe = (& $c.Exe @checkArgs 2>$null | Select-Object -Last 1)
                if ($realExe) { $realExe = $realExe.Trim() }
                if ($realExe -and (Test-Path $realExe)) {
                    return @{ Exe = $realExe; Args = @() }
                }
            } catch {}
            return $c   # fallback เผื่อ resolve sys.executable ไม่ได้ (ไม่ควรเกิด)
        }
    }
    Write-Log "WARN: ไม่มี python candidate ไหนผ่านการเช็ค dependency เลย — ใช้ 'python' เป็น fallback (จะ error ชัดเจนใน log ถ้าผิดจริง)"
    return $candidates[0]
}

$HeartbeatFile = Join-Path $PSScriptRoot "bot_heartbeat.txt"
$LogDir        = Join-Path $PSScriptRoot "logs"
$LogFile       = Join-Path $LogDir "supervisor.log"
$LockFile      = Join-Path $PSScriptRoot "supervisor.lock"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Log($msg) {
    $ts   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    try { Add-Content -Path $LogFile -Value $line -Encoding UTF8 } catch {}
}

# ── Single-instance lock ──────────────────────────────────────────
# เคยมี supervisor 2 ตัวรันพร้อมกัน (คนละ Windows user account ก็ได้ — เช่น
# Copter + Administrator) ทำให้ main.py spawn ขึ้นมา 2 instance พร้อมกัน แล้ว
# Telegram getUpdates ชนกัน (Conflict: terminated by other getUpdates request)
# กันด้วย lock file เก็บ PID ของ supervisor.ps1 ตัวเอง — ถ้ามีไฟล์ lock อยู่แล้ว
# และ PID นั้นยังมี process จริงรันอยู่ (ไม่ใช่ lock ค้างจากตัวที่ตายไปแล้ว) ให้
# ปฏิเสธการ start ซ้ำ ไม่ว่าจะรันจาก user ไหนก็ตาม (อ่านไฟล์ได้ก็เห็น lock เดียวกัน)
if (Test-Path $LockFile) {
    try {
        $lockPid = [int](Get-Content $LockFile -TotalCount 1 -ErrorAction Stop)
        $existing = Get-Process -Id $lockPid -ErrorAction SilentlyContinue
        if ($existing -and $existing.ProcessName -match 'powershell') {
            Write-Log "ERROR: พบ supervisor ตัวอื่นรันอยู่แล้ว (pid=$lockPid) — เลิกรัน ตัวนี้เพื่อกัน main.py ซ้อน 2 instance (Telegram getUpdates Conflict)"
            exit 1
        }
        Write-Log "WARN: lock file ค้างจาก pid=$lockPid (ตายไปแล้ว) — เคลียร์แล้วรันต่อ"
    } catch {
        Write-Log "WARN: อ่าน lock file ไม่ได้ ($_) — เคลียร์แล้วรันต่อ"
    }
}
try { Set-Content -Path $LockFile -Value $PID -Encoding ASCII } catch {}

function Read-HeartbeatTs {
    # คืน epoch (long) จากบรรทัด ts=... ของ heartbeat; คืน $null ถ้าอ่านไม่ได้
    if (-not (Test-Path $HeartbeatFile)) { return $null }
    try {
        $line = Get-Content $HeartbeatFile -TotalCount 1 -ErrorAction Stop
        if ($line -match '^ts=(\d+)') { return [long]$Matches[1] }
    } catch { return $null }
    return $null
}

if (-not $PSBoundParameters.ContainsKey('Python')) {
    $resolved   = Resolve-Python
    $Python     = $resolved.Exe
    $PythonArgs = $resolved.Args -join ' '
}
$PythonArgList = @($PythonArgs -split ' ' | Where-Object { $_ -ne '' })
$PythonCmdLabel = (@($Python) + $PythonArgList) -join ' '

Write-Log "Supervisor started (stale=$StaleSec s, check=$CheckEvery s, grace=$GraceSec s, python='$PythonCmdLabel')"

try {
while ($true) {
    # ลบ heartbeat เก่าก่อน start เพื่อไม่ให้อ่าน ts ค้างจากรอบก่อนมาตัดสินผิด
    if (Test-Path $HeartbeatFile) { Remove-Item $HeartbeatFile -Force -ErrorAction SilentlyContinue }

    Write-Log "Launching: $PythonCmdLabel main.py"
    try {
        $proc = Start-Process -FilePath $Python -ArgumentList ($PythonArgList + @("main.py")) -PassThru -NoNewWindow
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
} finally {
    # คืน lock เสมอไม่ว่าจะออกจาก loop ด้วย Ctrl+C หรือ error ใดๆ
    # กันรอบถัดไป start ไม่ติดเพราะเจอ lock ค้างของตัวเองที่ตายไปแล้ว
    try { if ((Get-Content $LockFile -ErrorAction SilentlyContinue) -eq "$PID") { Remove-Item $LockFile -Force -ErrorAction SilentlyContinue } } catch {}
}
