# Cooperative restart/start of the approved demo profile only. Never force-kill.
param([int]$TimeoutSec = 120)
$ErrorActionPreference = 'Stop'
$taskProfileName = 'demo-iux-2101182459'
$taskDirectory = Join-Path $PSScriptRoot 'profiles\demo\demo-iux-2101182459'
$taskHeartbeat = Join-Path $taskDirectory 'bot_heartbeat.txt'
$taskRequest = Join-Path $taskDirectory 'bot_restart_request.json'
$taskAck = Join-Path $taskDirectory 'bot_restart_ack.json'
$taskLock = Join-Path $taskDirectory 'supervisor.lock'
$taskStarted = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$taskOldPid = 0
$taskRequestId = [guid]::NewGuid().ToString('N')
$taskOperatorLock = [IO.File]::Open((Join-Path $taskDirectory 'restart_operator.lock'),
    [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)

function Read-TaskHeartbeat {
    $fields = @{}
    if (Test-Path -LiteralPath $taskHeartbeat) {
        foreach ($line in Get-Content -LiteralPath $taskHeartbeat -ErrorAction SilentlyContinue) {
            if ($line -match '^([^=]+)=(.*)$') { $fields[$Matches[1]] = $Matches[2] }
        }
    }
    return $fields
}

try {
    $taskProcesses = @(Get-CimInstance Win32_Process)
    $taskSupervisor = @($taskProcesses | Where-Object {
        $_.Name -in @('powershell.exe', 'pwsh.exe') -and
        $_.CommandLine -match [regex]::Escape((Join-Path $PSScriptRoot 'run_supervised.ps1')) -and
        $_.CommandLine -match '(?:^|\s)-Profile\s+"?demo-iux-2101182459(?=["\s]|$)'
    })
    if ($taskSupervisor.Count -gt 1) { throw 'Multiple target supervisors; review required.' }
    $taskBefore = Read-TaskHeartbeat
    if ($taskBefore['pid']) {
        $taskRecorded = $taskProcesses | Where-Object { $_.ProcessId -eq [int]$taskBefore['pid'] }
        if ($taskRecorded -and $taskRecorded.Name -eq 'python.exe' -and
            $taskRecorded.CommandLine -match 'main\.py' -and
            $taskRecorded.CreationDate -le (Get-Item -LiteralPath $taskHeartbeat).LastWriteTime) {
            $taskOldPid = [int]$taskRecorded.ProcessId
        }
    }
    if ($taskOldPid) {
        if ($taskSupervisor.Count -ne 1) { throw 'Existing bot has no target supervisor; review required.' }
        $taskParent = $taskProcesses | Where-Object { $_.ProcessId -eq $taskRecorded.ParentProcessId }
        if ($taskRecorded.ParentProcessId -ne $taskSupervisor[0].ProcessId -and
            (-not $taskParent -or $taskParent.ParentProcessId -ne $taskSupervisor[0].ProcessId)) {
            throw 'Heartbeat bot does not belong to the target supervisor.'
        }
        $payload = @{ profile=$taskProfileName; pid=$taskOldPid; created_epoch=$taskStarted; request_id=$taskRequestId }
        $taskTmp = "$taskRequest.$PID.tmp"
        [IO.File]::WriteAllText($taskTmp, ($payload | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $taskTmp -Destination $taskRequest -Force
        Write-Output "Cooperative restart requested for demo 2459 pid=$taskOldPid"
    } elseif ($taskSupervisor.Count -eq 0) {
        # The supervisor loads profile.env itself. Keep the current worker mode;
        # credentials never appear in arguments or output.
        $taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
        $taskLogDir = Join-Path $taskDirectory 'logs'
        $env:PYTHONIOENCODING = 'utf-8'
        $taskLaunch = @('-NoProfile','-ExecutionPolicy','Bypass','-File',
            ('"' + (Join-Path $PSScriptRoot 'run_supervised.ps1') + '"'),'-Profile',$taskProfileName)
        $taskNewSupervisor = Start-Process -FilePath 'powershell.exe' -ArgumentList $taskLaunch -WindowStyle Hidden -PassThru `
            -WorkingDirectory $PSScriptRoot `
            -RedirectStandardOutput (Join-Path $taskLogDir "restart_2459_$taskStamp.stdout.log") `
            -RedirectStandardError (Join-Path $taskLogDir "restart_2459_$taskStamp.stderr.log")
        Write-Output "Started target supervisor pid=$($taskNewSupervisor.Id)"
    } else {
        Write-Output 'Existing target supervisor is starting the bot; waiting without launching a duplicate.'
    }
    $taskDeadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $taskDeadline) {
        Start-Sleep -Seconds 2
        $taskFields = Read-TaskHeartbeat
        if (-not $taskFields['pid'] -or [int]$taskFields['pid'] -eq $taskOldPid -or
            [long]$taskFields['ts'] -lt $taskStarted -or $taskFields['mt5_ok'] -ne '1' -or
            [long]$taskFields['last_scan'] -le 0 -or
            ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [long]$taskFields['ts']) -gt 30) { continue }
        $taskMain = Get-CimInstance Win32_Process -Filter "ProcessId=$($taskFields['pid'])"
        if (-not $taskMain -or $taskMain.CommandLine -notmatch 'main\.py') { continue }
        if ($taskOldPid) {
            if (-not (Test-Path -LiteralPath $taskAck)) { continue }
            $taskAcknowledged = Get-Content -LiteralPath $taskAck -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($taskAcknowledged.request_id -ne $taskRequestId -or
                $taskAcknowledged.pid -ne $taskOldPid -or -not $taskAcknowledged.worker_stopped) { continue }
        }
        Write-Output "READY demo2459 main_pid=$($taskFields['pid']) mt5_ok=1 auto=$($taskFields['auto']) bkk=$($taskFields['bkk'])"
        return
    }
    throw 'No verified restart completion before timeout; no force-kill fallback was attempted.'
} finally {
    $taskOperatorLock.Dispose()
}
