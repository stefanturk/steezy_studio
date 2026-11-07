# CI on Windows: start each app the way its Start-menu shortcut does (pythonw,
# no console) and check it is still running after a while, i.e. it didn't crash
# on start. A crash's traceback is lost under pythonw, so on failure the same
# command is rerun with python.exe to show why.
param([string]$Engine, [string]$Studio, [string]$Tools)
$ErrorActionPreference = 'Stop'
$pyw = Join-Path $Engine 'python\pythonw.exe'
$py  = Join-Path $Engine 'python\python.exe'
$apps = @(
    @{ Name = 'Steezy Studio'; Args = @('-m', 'studio.gui');         Dir = $Studio },
    @{ Name = 'Beat Thief';    Args = @('gui.py');                   Dir = (Join-Path $Tools 'beat_thief') },
    @{ Name = 'Session Sync';  Args = @('-m', 'sessionsync.ui.app'); Dir = (Join-Path $Tools 'session_sync') }
)
$failed = @()
foreach ($a in $apps) {
    $p = Start-Process -FilePath $pyw -ArgumentList $a.Args -WorkingDirectory $a.Dir -PassThru
    Start-Sleep -Seconds 25
    if ($p.HasExited) {
        Write-Host "$($a.Name) exited on start (code $($p.ExitCode)). Rerunning with python.exe:"
        $ErrorActionPreference = 'Continue'
        Push-Location $a.Dir; & $py @($a.Args) 2>&1 | Select-Object -Last 40 | ForEach-Object { Write-Host "  $_" }; Pop-Location
        $ErrorActionPreference = 'Stop'
        $failed += $a.Name
    } else {
        Write-Host "$($a.Name) is running."
        Stop-Process -Id $p.Id -Force
    }
}
if ($failed.Count) { Write-Error ("Crashed on start: " + ($failed -join ', ')) }
