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

# Never terminate this stop command or the shells that launched it.
function Get-StopProtectedProcessIds([int]$StartPid = $PID) {
    $protected = [Collections.Generic.HashSet[int]]::new()
    $byId = @{}
    try {
        foreach ($process in Get-CimInstance Win32_Process -ErrorAction Stop) {
            $byId[[int]$process.ProcessId] = $process
        }
    } catch {}
    $ancestorPid = $StartPid
    while ($ancestorPid -gt 0 -and $protected.Add($ancestorPid)) {
        $ancestor = $byId[$ancestorPid]
        if (-not $ancestor) { break }
        $ancestorPid = [int]$ancestor.ParentProcessId
    }
    return ,$protected
}

$StopProtectedProcessIds = Get-StopProtectedProcessIds

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

function Stop-Mt5Terminal([string]$ExePath) {
    if (-not $ExePath) { return }
    try {
        if (-not (Test-Path $ExePath)) { return }
        $full = [IO.Path]::GetFullPath($ExePath)
        $procs = @(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -ieq $full) })
        foreach ($p in $procs) {
            Stop-Process -Id ([int]$p.ProcessId) -Force -ErrorAction SilentlyContinue
            Write-Host "ปิด MT5 terminal: pid=$($p.ProcessId) ($full)"
        }
    } catch {
        Write-Host "WARN: ปิด MT5 terminal ไม่สำเร็จ ($ExePath): $_"
    }
}

function Stop-ProcessTreeLocal(
    [int]$RootPid,
    [datetime]$ExpectedCreated = [datetime]::MinValue,
    [Collections.Generic.HashSet[int]]$Visited = $null
) {
    if ($RootPid -le 0 -or $StopProtectedProcessIds.Contains($RootPid)) { return }
    if ($null -eq $Visited) { $Visited = [Collections.Generic.HashSet[int]]::new() }
    if (-not $Visited.Add($RootPid)) { return }
    try {
        $root = Get-CimInstance Win32_Process -Filter "ProcessId=$RootPid" -ErrorAction Stop
        if (-not $root -or -not $root.CreationDate) { return }
        $created = [datetime]$root.CreationDate
        if ($ExpectedCreated -ne [datetime]::MinValue -and $created -ne $ExpectedCreated) { return }

        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootPid" -ErrorAction Stop)
        foreach ($child in $children) {
            # ParentProcessId survives its original parent. A reused PID can make
            # an older, unrelated explorer.exe look like a bot's child.
            if (-not $child.CreationDate -or $child.CreationDate -lt $created) { continue }
            Stop-ProcessTreeLocal ([int]$child.ProcessId) ([datetime]$child.CreationDate) $Visited
        }

        # Recheck identity after visiting children, in case the PID was reused.
        $current = Get-CimInstance Win32_Process -Filter "ProcessId=$RootPid" -ErrorAction Stop
        if ($current -and $current.CreationDate -eq $created) {
            Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
            Write-Host "ปิด pid=$RootPid ($($root.Name))"
        }
    } catch {}
}

function Stop-RecordedProcessTree([int]$RecordedPid, [datetime]$RecordedAt) {
    $recorded = Get-CimInstance Win32_Process -Filter "ProcessId=$RecordedPid" -ErrorAction SilentlyContinue
    if (-not $recorded -or -not $recorded.CreationDate) { return }
    if ($recorded.CreationDate -gt $RecordedAt) {
        Write-Host "WARN: stale PID $RecordedPid in state file; skipping reused process"
        return
    }
    Stop-ProcessTreeLocal $RecordedPid ([datetime]$recorded.CreationDate)
}

function Stop-LtsSupervisorForProfile([string]$ProfileName, [string]$RepoRoot = $PSScriptRoot) {
    $portfolios = @{
        'demo-exness-416273786' = 'LTS_AUS3'
        'demo-exness-414252716' = 'LTS_AHR3'
    }
    $portfolio = $portfolios[$ProfileName]
    if (-not $portfolio) { return }
    $wrapperPath = [regex]::Escape((Join-Path $RepoRoot 'run_supervised_lts.ps1'))
    $workerPath = [regex]::Escape((Join-Path $RepoRoot 'strategy\demo_portfolio\backtest-sim\supervisor_lts_avengers.py'))
    $portfolioPattern = '(?:^|\s)--?portfolio\s+"?' + [regex]::Escape($portfolio) + '(?=["\s]|$)'
    $ltsProcesses = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe' OR Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.CommandLine -match $wrapperPath -or $_.CommandLine -match $workerPath) -and
            $_.CommandLine -match $portfolioPattern
        } | Sort-Object @{ Expression = { $_.CommandLine -match $workerPath } })
    foreach ($ltsProcess in $ltsProcesses) {
        if ($ltsProcess.CreationDate) {
            Stop-ProcessTreeLocal ([int]$ltsProcess.ProcessId) ([datetime]$ltsProcess.CreationDate)
        }
    }
}

if (-not $OnlyCloseWindow) {
    # These profiles launch an additional wrapper and worker outside supervisor.lock.
    Stop-LtsSupervisorForProfile $Profile

    # ปิด supervisor (ถ้ายังรันอยู่)
    if (Test-Path $LockFile) {
        try {
            $lockRecordedAt = (Get-Item -LiteralPath $LockFile -ErrorAction Stop).LastWriteTime
            $lockPid = [int](Get-Content $LockFile -TotalCount 1 -ErrorAction Stop)
            Stop-RecordedProcessTree $lockPid $lockRecordedAt
        } catch {}
    }

    # ปิด main.py แยกต่างหาก เผื่อกลายเป็น orphan ไปแล้ว (ไม่มี supervisor คุม)
    if (Test-Path $HeartbeatFile) {
        try {
            $hbRecordedAt = (Get-Item -LiteralPath $HeartbeatFile -ErrorAction Stop).LastWriteTime
            $hbPid = $null
            foreach ($line in Get-Content $HeartbeatFile -ErrorAction Stop) {
                if ($line -match '^pid=(\d+)') { $hbPid = [int]$Matches[1]; break }
            }
            if ($hbPid) { Stop-RecordedProcessTree $hbPid $hbRecordedAt }
        } catch {}
    }

    # ปิด MT5 terminal ของ profile นี้ด้วย (เหมือน profiles\...\run\close_mt5.bat
    # แต่รวมเข้ามาในสคริปต์เดียวกันเลย ไม่ต้องเรียกแยก) — profile ใช้ terminal64.exe
    # แบบ portable ในโฟลเดอร์ profile เอง (profile.env: MT5_PATH=mt5\terminal64.exe)
    # ส่วน root/main ไม่มี profile.env ใช้ MT5 ที่ติดตั้งแบบ global แทน (ตรงกับ
    # ค่า default ของ config.py: C:\MT5\terminal64.exe หรือ Program Files)
    if ($Profile) {
        Stop-Mt5Terminal (Join-Path $RuntimeDir "mt5\terminal64.exe")
    } else {
        Stop-Mt5Terminal "C:\MT5\terminal64.exe"
        Stop-Mt5Terminal "C:\Program Files\MetaTrader 5\terminal64.exe"
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
            Where-Object {
                $_.CommandLine -match $escapedBat -and
                -not $StopProtectedProcessIds.Contains([int]$_.ProcessId)
            })
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
