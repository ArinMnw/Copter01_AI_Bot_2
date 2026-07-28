# stop_supervised.ps1 — ปิด supervisor + main.py แบบตั้งใจ (เขียน marker ก่อนเสมอ)
#
# ทำไมต้องมีตัวนี้: ทดสอบจริงแล้วพบว่า Windows Terminal (หรือ terminal สมัยใหม่)
# ปิด process โดย terminate ตรงๆ ไม่ผ่าน SetConsoleCtrlHandler เลย ทำให้ดักจับ
# "ปิดหน้าต่าง (X)" จาก in-process ไม่ได้ 100% — วิธีที่เชื่อถือได้กว่าคือ ให้ผู้ใช้
# สั่งปิดผ่านสคริปต์นี้แทนการปิดหน้าต่างตรงๆ จะได้เขียน marker ได้แน่นอนก่อนฆ่า
# process จริง ป้องกัน guard script (เช็คทุก 15 นาที) เข้าใจผิดว่าตายกะทันหัน
# แล้ว auto-restart ให้ทั้งที่ตั้งใจปิด
#
# วิธีใช้: ดับเบิลคลิก run\stop_supervised.bat (หรือ profiles\...\run\stop_supervised.bat)
param(
    [string]$Profile = "",
    [switch]$SkipWindowClose,   # หยุด process แต่ยังไม่ปิดหน้าต่าง cmd.exe ตัวแม่ (ใช้ตอน stop ทีละตัวใน stop_supervised_all.bat แล้วค่อยปิดหน้าต่างทั้งหมดทีเดียวตอนท้าย)
    [switch]$OnlyCloseWindow    # ข้ามขั้นตอน marker/kill process ทั้งหมด ปิดแค่หน้าต่าง cmd.exe ตัวแม่เท่านั้น
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

$RuntimeDir    = Resolve-ProfileDir $Profile
$LockFile      = Join-Path $RuntimeDir "supervisor.lock"
$ClosedMarker  = Join-Path $RuntimeDir "supervisor_closed.marker"
$HeartbeatFile = Join-Path $RuntimeDir "bot_heartbeat.txt"

$label = if ($Profile) { $Profile } else { "root/main" }

if (-not $OnlyCloseWindow) {
    Write-Host "กำลังปิด $label ..."

    # เขียน marker ก่อนเสมอ ไม่ว่าจะเจอ process รันอยู่จริงไหมก็ตาม — สำคัญที่สุด
    # คือ marker ต้องถูกเขียนก่อนที่จะฆ่าอะไรทั้งนั้น กัน guard script auto-restart
    try {
        Set-Content -Path $ClosedMarker -Value (Get-Date -Format "o") -Encoding ASCII -Force
        Write-Host "เขียน marker แล้ว: $ClosedMarker"
    } catch {
        Write-Host "WARN: เขียน marker ไม่สำเร็จ: $_"
    }
}

function Stop-ProcessTreeLocal([int]$RootPid) {
    if (-not $RootPid) { return }
    try {
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootPid" -ErrorAction SilentlyContinue)
        foreach ($c in $children) { Stop-ProcessTreeLocal ([int]$c.ProcessId) }
    } catch {}
    try {
        $p = Get-Process -Id $RootPid -ErrorAction SilentlyContinue
        if ($p) {
            $pname = $p.ProcessName
            Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
            Write-Host "ปิด pid=$RootPid ($pname)"
        }
    } catch {}
}

if (-not $OnlyCloseWindow) {
    # ปิด supervisor (ถ้ายังรันอยู่)
    if (Test-Path $LockFile) {
        try {
            $lockPid = [int](Get-Content $LockFile -TotalCount 1 -ErrorAction Stop)
            Stop-ProcessTreeLocal $lockPid
        } catch {}
    }

    # ปิด main.py แยกต่างหาก เผื่อกลายเป็น orphan ไปแล้ว (ไม่มี supervisor คุม)
    if (Test-Path $HeartbeatFile) {
        try {
            $hbPid = $null
            foreach ($line in Get-Content $HeartbeatFile -ErrorAction Stop) {
                if ($line -match '^pid=(\d+)') { $hbPid = [int]$Matches[1]; break }
            }
            if ($hbPid) { Stop-ProcessTreeLocal $hbPid }
        } catch {}
    }
}

# ปิดหน้าต่าง cmd.exe ตัวแม่ที่รัน run_supervised.bat ค้างไว้ด้วย (ข้ามถ้าสั่ง
# -SkipWindowClose — ใช้ตอน stop_supervised_all.bat ที่อยากหยุดให้ครบทุกตัวก่อน
# แล้วค่อยไล่ปิดหน้าต่างทั้งหมดทีเดียวตอนท้าย) — ทดสอบจริงแล้วพบ
# ว่าฆ่าแค่ supervisor.ps1/main.py ไม่พอ เพราะ .bat เรียก powershell แบบ synchronous
# (รอผลก่อน) พอ powershell ตายจะไหลไปเจอบรรทัด "pause" ต่อทันที ค้างเป็นหน้าต่าง
# ว่างเปล่ารอกดปุ่มตลอดไป — เช็คจาก command line ตรงๆ แทนไล่ parent/child เพราะ
# ถ้า supervisor ตายไปก่อนแล้ว (เคส orphan) จะหา parent ย้อนกลับไม่ได้อีก
if (-not $SkipWindowClose) {
    $batPathForThis = if ($Profile) {
        Join-Path $RuntimeDir "run\run_supervised.bat"
    } else {
        Join-Path $PSScriptRoot "run\run_supervised.bat"
    }
    try {
        $escapedBat = [regex]::Escape($batPathForThis)
        $staleShells = @(Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match $escapedBat })
        foreach ($shell in $staleShells) {
            Stop-Process -Id ([int]$shell.ProcessId) -Force -ErrorAction SilentlyContinue
            Write-Host "ปิดหน้าต่างที่ค้าง: pid=$($shell.ProcessId)"
        }
    } catch {}
    Write-Host ""
    Write-Host "ปิด $label เรียบร้อยแล้ว — จะไม่ auto-restart จนกว่าจะรัน run_supervised.bat เอง"
} else {
    Write-Host "หยุด $label แล้ว (ยังไม่ปิดหน้าต่าง — รอปิดพร้อมกันทีเดียวตอนท้าย)"
}
