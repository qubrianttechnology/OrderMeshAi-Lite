# Stop only the recorded temporary tunnel and restore its local settings.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$statePath = Join-Path $projectRoot '.local\tunnel-process.json'
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $tunnelProcess = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
    if ($tunnelProcess) {
        $expectedStart = [DateTime]::Parse($state.started_at).ToUniversalTime()
        if ($tunnelProcess.StartTime.ToUniversalTime().Ticks -ne $expectedStart.Ticks -or $tunnelProcess.Path -ne $state.executable) {
            throw 'The saved PID belongs to a different process. Nothing was stopped.'
        }
        Stop-Process -Id $tunnelProcess.Id
        Write-Output 'Temporary HTTPS tunnel stopped.'
    }
}
Push-Location $projectRoot
try {
    & .\.venv\Scripts\python.exe .\scripts\restore_https_settings.py
    if ($LASTEXITCODE -ne 0) {throw 'Could not restore local settings.'}
    & .\Start-OrderMesh.ps1 -Restart
} finally {
    Pop-Location
}
