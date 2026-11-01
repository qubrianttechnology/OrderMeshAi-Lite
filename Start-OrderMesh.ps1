# Start the existing local workspace. This script does not create sample users/data.
[CmdletBinding()]
param([switch]$Restart)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$apiDirectory = Join-Path $projectRoot 'services\api'
$webDirectory = Join-Path $projectRoot 'apps\web'
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
$logDirectory = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$processStatePath = Join-Path $logDirectory 'processes.json'
$trackedProcesses = @{}
if (Test-Path -LiteralPath $processStatePath) {
    $savedProcesses = Get-Content -LiteralPath $processStatePath -Raw | ConvertFrom-Json
    foreach ($property in $savedProcesses.PSObject.Properties) {
        $trackedProcesses[$property.Name] = $property.Value
    }
}

function Save-OrderMeshProcess([string]$Role, $Process) {
    $Process.Refresh()
    $trackedProcesses[$Role] = @{
        Id = $Process.Id
        StartTicks = $Process.StartTime.ToUniversalTime().Ticks.ToString()
        Executable = $Process.Path
    }
    $trackedProcesses | ConvertTo-Json | Set-Content -LiteralPath $processStatePath -Encoding UTF8
}

if ($Restart) {
    foreach ($role in @('web', 'api')) {
        if (-not $trackedProcesses.ContainsKey($role)) { continue }
        $saved = $trackedProcesses[$role]
        $running = Get-Process -Id $saved.Id -ErrorAction SilentlyContinue
        if ($running -and
            $running.StartTime.ToUniversalTime().Ticks.ToString() -eq $saved.StartTicks -and
            $running.Path -eq $saved.Executable) {
            & taskkill.exe /PID $running.Id /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Could not restart the tracked $role process." }
        }
        $trackedProcesses.Remove($role)
    }
    $trackedProcesses | ConvertTo-Json | Set-Content -LiteralPath $processStatePath -Encoding UTF8
}

function Test-OrderMeshUrl([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-OrderMeshUrl([string]$Url, [int]$TimeoutSeconds, $Process, [string]$ErrorLog) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-OrderMeshUrl $Url) { return }
        $Process.Refresh()
        if ($Process.HasExited) { throw "Server exited. Check $ErrorLog" }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Server did not become ready. Check $ErrorLog"
}

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Project Python environment is missing. Follow the setup in README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $webDirectory 'node_modules\next\dist\bin\next'))) {
    throw 'Frontend dependencies are missing. Run npm ci in apps\web.'
}
$nodeExecutable = (Get-Command node -ErrorAction Stop).Source
Push-Location $apiDirectory
try {
    $configuredAppOrigin = & $pythonExecutable -B -c "from app.config import settings; print(settings.app_origin)"
    if ($LASTEXITCODE -ne 0) { throw 'Could not read configured APP_ORIGIN.' }
    $configuredAppUri = [Uri]$configuredAppOrigin.Trim()
} finally { Pop-Location }

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

if (-not (Test-OrderMeshUrl 'http://127.0.0.1:8000/api/health')) {
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 8000 is in use by another service. Stop that service before starting OrderMesh.'
    }
    Push-Location $apiDirectory
    try {
        & $pythonExecutable -B -c "from app.config import settings; assert settings.app_env == 'development', 'This launcher requires APP_ENV=development'; print('API configuration: OK')"
        if ($LASTEXITCODE -ne 0) { throw 'Fix services\api\.env before starting the API.' }
        & $pythonExecutable -B -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. The API was not started.' }
    } finally {
        Pop-Location
    }
    $apiErrorLog = Join-Path $logDirectory 'api.stderr.log'
    $apiProcess = Start-Process -FilePath $pythonExecutable `
        -ArgumentList @('-B', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $apiDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDirectory 'api.stdout.log') `
        -RedirectStandardError $apiErrorLog
    Save-OrderMeshProcess 'api' $apiProcess
    Wait-OrderMeshUrl 'http://127.0.0.1:8000/api/health' 30 $apiProcess $apiErrorLog
    Write-Host "API started (PID $($apiProcess.Id))."
} else {
    Write-Host 'API is already running.'
}

if (-not (Test-OrderMeshUrl 'http://localhost:3000/api/health')) {
    if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 3000 is in use by another service. Stop that service before starting OrderMesh.'
    }
    $previousApiBaseUrl = $env:API_BASE_URL
    $previousTelemetry = $env:NEXT_TELEMETRY_DISABLED
    $previousDevOrigin = $env:ORDERMESH_DEV_ORIGIN
    $previousAppOrigin = $env:ORDERMESH_APP_ORIGIN
    try {
        $env:API_BASE_URL = 'http://127.0.0.1:8000'
        $env:NEXT_TELEMETRY_DISABLED = '1'
        $env:ORDERMESH_DEV_ORIGIN = $configuredAppUri.DnsSafeHost
        $env:ORDERMESH_APP_ORIGIN = $configuredAppOrigin.Trim().TrimEnd('/')
        $webErrorLog = Join-Path $logDirectory 'web.stderr.log'
        $webProcess = Start-Process -FilePath $nodeExecutable `
            -ArgumentList @('node_modules/next/dist/bin/next', 'dev', '--hostname', '127.0.0.1', '--port', '3000') `
            -WorkingDirectory $webDirectory -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logDirectory 'web.stdout.log') `
            -RedirectStandardError $webErrorLog
    } finally {
        $env:API_BASE_URL = $previousApiBaseUrl
        $env:NEXT_TELEMETRY_DISABLED = $previousTelemetry
        $env:ORDERMESH_DEV_ORIGIN = $previousDevOrigin
        $env:ORDERMESH_APP_ORIGIN = $previousAppOrigin
    }
    Save-OrderMeshProcess 'web' $webProcess
    Wait-OrderMeshUrl 'http://localhost:3000/api/health' 90 $webProcess $webErrorLog
    Write-Host "Dashboard started (PID $($webProcess.Id))."
} else {
    Write-Host 'Dashboard is already running.'
}
if (-not (Test-OrderMeshUrl 'http://localhost:3000/api/health')) {
    throw 'The dashboard is running, but its API proxy is unavailable. Check .local logs.'
}
Write-Host ('OrderMesh is ready: ' + $configuredAppOrigin.Trim().TrimEnd('/') + '/sign-in')
Write-Host 'Server logs: .local'
