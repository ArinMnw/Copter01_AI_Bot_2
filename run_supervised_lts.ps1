# run_supervised_lts.ps1 — crash-restart wrapper for supervisor_lts_avengers.py
# ------------------------------------------------------------------
# supervisor_lts_avengers.py คือตัวที่รัน backtest จริงทุก 15 นาที (:00/:15/:30/:45+1s)
# แล้วเข้า order live ตามผล — ใช้ได้แค่กับ LTS_AUS3/LTS_AHR3 (ดู choices ในตัว script)
# ตัว script เองเป็น while-loop เปล่าๆ ไม่มี auto-restart ถ้า crash — wrapper นี้ทำหน้าที่
# แค่ "ตายแล้วรันใหม่" (ไม่มี heartbeat/hang-detection แบบ run_supervised.ps1 หลัก เพราะ
# supervisor_lts_avengers.py ไม่ได้เขียน heartbeat file — ถ้าต้องการเพิ่มทีหลังค่อยทำ)
#
# state (current_start/processed) เก็บอยู่ในไฟล์ .supervisor_lts_<portfolio>_state.json
# ใน profile dir ของพอร์ตนั้นอยู่แล้ว (resume เองทุกครั้งที่ start ใหม่ ไม่ต้องพึ่ง -Start
# ตรงนี้ยกเว้นครั้งแรกสุดที่ยังไม่มี state)
#
# วิธีรัน:  powershell -ExecutionPolicy Bypass -NoProfile -File run_supervised_lts.ps1 -Portfolio LTS_AUS3
# หยุด:    ปิดหน้าต่างนี้ หรือ Ctrl+C (supervisor_lts_avengers.py ที่รันอยู่จะกลายเป็น orphan
#          แต่ยังทำงานต่อ — ปิดเองผ่าน Task Manager ถ้าต้องการปิดจริง)

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("LTS_AUS3", "LTS_AHR3")]
    [string]$Portfolio,
    [int]$RestartGap = 10
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$ScriptPath = Join-Path $PSScriptRoot "strategy\demo_portfolio\backtest-sim\supervisor_lts_avengers.py"
$LogDir = Join-Path $PSScriptRoot "logs\lts_supervisor_wrapper"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "$Portfolio.log"

function Write-Log($msg) {
    $ts   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    try { Add-Content -Path $LogFile -Value $line -Encoding UTF8 } catch {}
}

# fallback --start ใช้แค่ตอนยังไม่เคยมี state file มาก่อน (รันครั้งแรกสุดของพอร์ตนี้เท่านั้น)
# หลังจากนั้น supervisor_lts_avengers.py resume จาก state file เองทุกครั้ง ค่านี้จึงแทบไม่มีผล
$FallbackStart = (Get-Date).AddDays(-1).ToString("dd-MM-yyyy HH:mm")

Write-Log "LTS Supervisor wrapper started (portfolio=$Portfolio, fallback_start=$FallbackStart, restart_gap=${RestartGap}s)"

while ($true) {
    Write-Log "Launching: python supervisor_lts_avengers.py --portfolio $Portfolio --start `"$FallbackStart`""
    & python $ScriptPath --portfolio $Portfolio --start $FallbackStart
    Write-Log "supervisor_lts_avengers.py ($Portfolio) exited (code=$LASTEXITCODE) -> restart in ${RestartGap}s"
    Start-Sleep -Seconds $RestartGap
}
