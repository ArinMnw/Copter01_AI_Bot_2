# Run with: powershell -NoProfile -File tests\test_stop_supervised.ps1
# All process queries and termination calls are mocked; no real processes stop.
$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path (Join-Path $PSScriptRoot '..\stop_supervised.ps1')).Path
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($sourcePath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

$functionNames = @('Get-StopProtectedProcessIds', 'Stop-ProcessTreeLocal', 'Stop-RecordedProcessTree', 'Stop-LtsSupervisorForProfile')
foreach ($definition in $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    if ($definition.Name -in $functionNames) { Invoke-Expression $definition.Extent.Text }
}

function Get-CimInstance([string]$ClassName, [string]$Filter, [string]$ErrorAction) {
    if ($ClassName -ne 'Win32_Process') { throw "Unexpected class: $ClassName" }
    if (-not $Filter) { return @($global:StopTestProcesses.Values) }
    if ($Filter -match '^ProcessId=(\d+)$') {
        $queryId = [int]$Matches[1]
        if (-not $global:StopTestQueries.ContainsKey($queryId)) { $global:StopTestQueries[$queryId] = 0 }
        $global:StopTestQueries[$queryId]++
        if ($queryId -eq $global:StopTestReuseId -and $global:StopTestQueries[$queryId] -eq $global:StopTestReuseOnQuery) {
            $global:StopTestProcesses[$queryId].CreationDate = $global:StopTestBaseTime.AddMinutes(30)
        }
        return $global:StopTestProcesses[$queryId]
    }
    if ($Filter -match '^ParentProcessId=(\d+)$') {
        $parentId = [int]$Matches[1]
        return @($global:StopTestProcesses.Values | Where-Object { $_.ParentProcessId -eq $parentId })
    }
    if ($Filter -eq "Name='cmd.exe'") {
        return @($global:StopTestProcesses.Values | Where-Object { $_.Name -eq 'cmd.exe' })
    }
    if ($Filter -eq "Name='powershell.exe' OR Name='pwsh.exe' OR Name='python.exe' OR Name='pythonw.exe'") {
        return @($global:StopTestProcesses.Values)
    }
    throw "Unexpected process filter: $Filter"
}

function Stop-Process([int]$Id, [switch]$Force, [string]$ErrorAction) {
    $global:StopTestStopped.Add($Id)
    $global:StopTestProcesses.Remove($Id)
}

function New-TestProcess([int]$Id, [int]$Parent, [int]$Minute, [string]$Name = 'python.exe') {
    [pscustomobject]@{
        ProcessId = $Id
        ParentProcessId = $Parent
        CreationDate = $global:StopTestBaseTime.AddMinutes($Minute)
        Name = $Name
        CommandLine = ''
    }
}

function Reset-TestProcesses([object[]]$Items) {
    $global:StopTestProcesses = @{}
    foreach ($item in $Items) { $global:StopTestProcesses[[int]$item.ProcessId] = $item }
    $global:StopTestStopped = [Collections.Generic.List[int]]::new()
    $script:StopProtectedProcessIds = [Collections.Generic.HashSet[int]]::new()
    $global:StopTestQueries = @{}
    $global:StopTestReuseId = 0
    $global:StopTestReuseOnQuery = 0
}

function Assert-Stopped([string]$Expected, [string]$Case) {
    $actual = $global:StopTestStopped -join ','
    if ($actual -ne $Expected) { throw "${Case}: expected [$Expected], got [$actual]" }
    Write-Host "PASS: $Case"
}

$global:StopTestBaseTime = [datetime]'2026-10-15T00:00:00'

# Regression: an older explorer.exe retains the PID of a dead parent, which
# Windows later assigns to a bot's Python child. Its entire branch must survive.
Reset-TestProcesses @(
    (New-TestProcess 1 0 0),
    (New-TestProcess 2 1 2),
    (New-TestProcess 3 2 -10 'explorer.exe'),
    (New-TestProcess 4 2 3),
    (New-TestProcess 5 3 4 'cmd.exe')
)
Stop-ProcessTreeLocal 1
Assert-Stopped '4,2,1' 'old explorer branch survives; real children stop before parents'

Reset-TestProcesses @((New-TestProcess 1 0 0), (New-TestProcess 2 1 1), (New-TestProcess 3 2 2))
$script:StopProtectedProcessIds = Get-StopProtectedProcessIds 3
Stop-ProcessTreeLocal 1
Stop-ProcessTreeLocal 2
Stop-ProcessTreeLocal 3
Assert-Stopped '' 'stopper and all ancestors survive'

Reset-TestProcesses @((New-TestProcess 2 1 1))
Stop-ProcessTreeLocal 1
Assert-Stopped '' 'missing root PID does not adopt orphan children'

Reset-TestProcesses @((New-TestProcess 1 0 20))
Stop-RecordedProcessTree 1 ($global:StopTestBaseTime.AddMinutes(10))
Assert-Stopped '' 'PID newer than lock or heartbeat is skipped'

Reset-TestProcesses @((New-TestProcess 1 0 5))
Stop-RecordedProcessTree 1 ($global:StopTestBaseTime.AddMinutes(10))
Assert-Stopped '1' 'live PID recorded in state still stops'

Reset-TestProcesses @((New-TestProcess 1 0 0), (New-TestProcess 2 1 1))
$global:StopTestReuseId = 2
$global:StopTestReuseOnQuery = 1
Stop-ProcessTreeLocal 1
Assert-Stopped '1' 'child PID reused after enumeration survives'

Reset-TestProcesses @((New-TestProcess 1 0 0), (New-TestProcess 2 1 1))
$global:StopTestReuseId = 1
$global:StopTestReuseOnQuery = 2
Stop-ProcessTreeLocal 1
Assert-Stopped '2' 'parent PID reused during traversal survives'

Reset-TestProcesses @((New-TestProcess 1 2 0), (New-TestProcess 2 1 0))
Stop-ProcessTreeLocal 1
Assert-Stopped '2,1' 'cyclic parent links terminate without recursion loops'

Reset-TestProcesses @((New-TestProcess 1 0 0))
$global:StopTestProcesses[1].CreationDate = $null
Stop-ProcessTreeLocal 1
Assert-Stopped '' 'unknown creation time never authorizes termination'

# Exercise the actual window-cleanup branch with mocked cmd.exe processes.
$protectedShell = New-TestProcess 101 0 -1 'cmd.exe'
$staleShell = New-TestProcess 102 0 -1 'cmd.exe'
$launcherPath = Join-Path (Split-Path (Resolve-Path $sourcePath)) 'run\run_supervised.bat'
$protectedShell.CommandLine = 'cmd.exe /c "' + $launcherPath + '"'
$staleShell.CommandLine = $protectedShell.CommandLine
Reset-TestProcesses @((New-TestProcess $PID 101 0 'powershell.exe'), $protectedShell, $staleShell)
& $sourcePath -OnlyCloseWindow
Assert-Stopped '102' 'window cleanup preserves caller shell and closes stale launcher'

$ltsRepoRoot = Split-Path $sourcePath
$ltsWrapperPath = Join-Path $ltsRepoRoot 'run_supervised_lts.ps1'
$ltsWorkerPath = Join-Path $ltsRepoRoot 'strategy\demo_portfolio\backtest-sim\supervisor_lts_avengers.py'
$ltsWrapper = New-TestProcess 11 0 0 'powershell.exe'
$ltsWrapper.CommandLine = 'powershell -File "' + $ltsWrapperPath + '" -Portfolio LTS_AUS3'
$ltsWorker = New-TestProcess 12 11 1
$ltsWorker.CommandLine = 'python "' + $ltsWorkerPath + '" --portfolio LTS_AUS3'
$otherPortfolio = New-TestProcess 13 0 0 'powershell.exe'
$otherPortfolio.CommandLine = 'powershell -File "' + $ltsWrapperPath + '" -Portfolio LTS_AHR3'
$otherRepo = New-TestProcess 14 0 0 'powershell.exe'
$otherRepo.CommandLine = 'powershell -File "C:\another-repo\run_supervised_lts.ps1" -Portfolio LTS_AUS3'
Reset-TestProcesses @($ltsWrapper, $ltsWorker, $otherPortfolio, $otherRepo)
Stop-LtsSupervisorForProfile 'demo-exness-416273786' $ltsRepoRoot
Assert-Stopped '12,11' 'profile stop includes its LTS wrapper and worker, preserving other profiles and repositories'

$ltsWorker.ParentProcessId = 999
Reset-TestProcesses @($ltsWorker, $otherPortfolio)
Stop-LtsSupervisorForProfile 'demo-exness-416273786' $ltsRepoRoot
Assert-Stopped '12' 'orphan LTS worker stops after its wrapper has exited'

Reset-TestProcesses @($otherPortfolio)
Stop-LtsSupervisorForProfile 'demo-exness-416010472' $ltsRepoRoot
Assert-Stopped '' 'ordinary profile stop preserves LTS workers'

# Exercise the real profile-stop entry point, including its default repo path.
# Marker writes and file checks are mocked to keep the repository untouched.
Reset-TestProcesses @($ltsWrapper, $ltsWorker, $otherPortfolio, $otherRepo)
$ltsWorker.ParentProcessId = 11
$global:StopTestMarkers = 0
function Set-Content([string]$Path, [string]$Value, [string]$Encoding, [switch]$Force) {
    $global:StopTestMarkers++
}
function Test-Path([string]$Path) { return $false }
try {
    & $sourcePath -Profile 'demo-exness-416273786' -SkipWindowClose
    Assert-Stopped '12,11' 'real profile-stop entry point stops its additional LTS processes'
    if ($global:StopTestMarkers -ne 1) { throw 'Stop entry point must write its marker' }
} finally {
    Remove-Item Function:\Set-Content
    Remove-Item Function:\Test-Path
}

# The startup batch files share this supervisor's stall-recovery helper.
$supervisorPath = Join-Path (Split-Path $sourcePath) 'run_supervised.ps1'
$supervisorAst = [Management.Automation.Language.Parser]::ParseFile($supervisorPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
foreach ($definition in $supervisorAst.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    if ($definition.Name -eq 'Stop-ProcessTree') { Invoke-Expression $definition.Extent.Text }
}
function Write-Log($Message) { Write-Host $Message }

Reset-TestProcesses @(
    (New-TestProcess 1 0 0),
    (New-TestProcess 2 1 2),
    (New-TestProcess 3 2 -10 'explorer.exe'),
    (New-TestProcess 4 2 3),
    (New-TestProcess 5 3 4 'cmd.exe')
)
Stop-ProcessTree 1
Assert-Stopped '4,2,1' 'supervisor stall recovery preserves the old explorer branch'

Reset-TestProcesses @((New-TestProcess 2 1 1))
Stop-ProcessTree 1
Assert-Stopped '' 'supervisor does not adopt children of a missing root'

Reset-TestProcesses @((New-TestProcess 1 0 0), (New-TestProcess 2 1 1))
$global:StopTestReuseId = 2
$global:StopTestReuseOnQuery = 1
Stop-ProcessTree 1
Assert-Stopped '1' 'supervisor skips a reused child PID'

Reset-TestProcesses @((New-TestProcess 1 0 0), (New-TestProcess 2 1 1))
$global:StopTestReuseId = 1
$global:StopTestReuseOnQuery = 2
Stop-ProcessTree 1
Assert-Stopped '2' 'supervisor skips a reused parent PID'

Reset-TestProcesses @((New-TestProcess 1 2 0), (New-TestProcess 2 1 0))
Stop-ProcessTree 1
Assert-Stopped '2,1' 'supervisor handles cyclic parent links'

Reset-TestProcesses @((New-TestProcess $PID 0 0 'powershell.exe'))
Stop-ProcessTree $PID
Assert-Stopped '' 'supervisor never terminates itself'

Write-Host 'All stop-supervised process tests passed (mocked; no real processes stopped).'
