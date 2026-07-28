# run_supervised_guard.ps1
# ใช้เป็น Action ของ Scheduled Task (ตัวเช็คซ้ำทุก 15 นาที) แทนการเรียก
# run_supervised.bat ตรงๆ — สคริปต์นี้เช็ค lock file ก่อนเงียบๆ (ไม่มีหน้าต่างขึ้น)
# ถ้ามี supervisor รันอยู่แล้วจะจบทันทีโดยไม่เปิดอะไรเพิ่ม
# ถ้ายังไม่มีใครรันอยู่ ถึงจะเปิด run_supervised.bat ตัวจริง (มีหน้าต่างให้เห็นตามปกติ)
#
# ยกเว้น: ถ้าเจอ supervisor_closed.marker (run_supervised.ps1 เขียนไว้ตอนปิดแบบ
# มีโอกาส cleanup — Ctrl+C/ปิดหน้าต่าง/error ปกติ) แปลว่าปิดตั้งใจ ไม่ใช่ตายกะทันหัน
# (reboot/crash/kill -9 ไม่มี marker เพราะไม่มีเวลารัน cleanup) — ถ้ามี marker
# ให้เคารพการปิดตั้งใจ ไม่ auto-restart จนกว่าจะรัน run_supervised.bat เองใหม่
param(
    [string]$Profile = ""
)

function Resolve-ProfileDir([string]$profileName) {
    if (-not $profileName) { return $PSScriptRoot }
    $candidates = @(
        (Join-Path $PSScriptRoot "profiles\$profileName"),
        (Join-Path $PSScriptRoot "profiles\demo\$profileName"),
        (Join-Path $PSScriptRoot "profiles\real\$profileName"),
        (Join-Path $PSScriptRoot "profiles\demo\accounts\$profileName"),
        (Join-Path $PSScriptRoot "profiles\real\accounts\$profileName")
    )
    foreach ($dir in $candidates) {
        if (Test-Path (Join-Path $dir "profile.env")) { return $dir }
    }
    return $candidates[0]
}

$RuntimeDir      = Resolve-ProfileDir $Profile
$LockFile        = Join-Path $RuntimeDir "supervisor.lock"
$ClosedMarker    = Join-Path $RuntimeDir "supervisor_closed.marker"
$HeartbeatFile   = Join-Path $RuntimeDir "bot_heartbeat.txt"

$alreadyRunning = $false

# 1) supervisor เองยังรันอยู่ไหม (ปกติ)
if (Test-Path $LockFile) {
    try {
        $lockPid  = [int](Get-Content $LockFile -TotalCount 1 -ErrorAction Stop)
        $existing = Get-Process -Id $lockPid -ErrorAction SilentlyContinue
        if ($existing) { $alreadyRunning = $true }
    } catch {}
}

# 2) main.py เองยังรันอยู่ไหม (เช็คแยกจาก supervisor) — เคสจริง: ปิด supervisor
# แล้ว main.py กลายเป็น orphan แต่ยังเทรดต่อ ถ้าเช็คแค่ supervisor lock
# อย่างเดียวจะเข้าใจผิดว่า "ไม่มีอะไรรันอยู่" แล้วเปิด main.py ซ้อนตัวที่ 2
# ขึ้นมา (Telegram getUpdates Conflict, ออเดอร์ซ้ำ) — ใช้ pid จาก heartbeat
# เป็นตัวเช็คตรงๆ ว่า process นั้นยังมีชีวิตอยู่จริงไหม
if (-not $alreadyRunning -and (Test-Path $HeartbeatFile)) {
    try {
        $hbPid = $null
        foreach ($line in Get-Content $HeartbeatFile -ErrorAction Stop) {
            if ($line -match '^pid=(\d+)') { $hbPid = [int]$Matches[1]; break }
        }
        if ($hbPid) {
            $hbProc = Get-Process -Id $hbPid -ErrorAction SilentlyContinue
            if ($hbProc -and $hbProc.ProcessName -match 'python') { $alreadyRunning = $true }
        }
    } catch {}
}

if ($alreadyRunning) {
    exit 0
}

# ไม่ได้รันอยู่ — เช็คว่าเป็นการปิดตั้งใจไหมก่อนตัดสินใจ restart
if (Test-Path $ClosedMarker) {
    exit 0
}

if ($Profile) {
    $batPath = Join-Path $RuntimeDir "run\run_supervised.bat"
} else {
    $batPath = Join-Path $PSScriptRoot "run\run_supervised.bat"
}

if (Test-Path $batPath) {
    Start-Process -FilePath $batPath -WorkingDirectory (Split-Path $batPath)
}
