# Restart finance audit platform (backend :8000, frontend :5173)
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'

function Stop-ListenersOnPort {
    param([int]$Port)
    $pattern = ":$Port\s"
    netstat -ano | Select-String $pattern | Select-String 'LISTENING' | ForEach-Object {
        $parts = ($_.Line -split '\s+') | Where-Object { $_ }
        $procId = $parts[-1]
        if ($procId -match '^\d+$') {
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-PythonExe {
    $venvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) { return $venvPython }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw 'Python not found. Run: cd backend; python -m venv .venv; python -m pip install -e .'
}

function Resolve-FrontendRunner {
    $pnpmCmd = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if ($pnpmCmd) {
        return @{
            File = $pnpmCmd.Source
            Args = @('--dir', $FrontendDir, 'dev', '--host', '127.0.0.1', '--port', '5173')
            WorkDir = $Root
        }
    }
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npmCmd) {
        return @{
            File = $npmCmd.Source
            Args = @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173')
            WorkDir = $FrontendDir
        }
    }
    throw 'pnpm or npm not found; cannot start frontend'
}

function Test-BackendImport {
    param([string]$PythonExe)
    Push-Location $BackendDir
    try {
        & $PythonExe -c "from app.main import app" 2>&1 | Out-String | Write-Host
        if ($LASTEXITCODE -ne 0) {
            throw 'Backend import failed. Run: cd backend; .\.venv\Scripts\python.exe -m pip install -e .'
        }
    } finally {
        Pop-Location
    }
}

function Test-HttpOk {
    param([string]$Url, [int]$TimeoutSec = 2)
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
    } catch {
        return $false
    }
}

Write-Host '============================================'
Write-Host '  Finance Audit Platform - Restart Services'
Write-Host '============================================'
Write-Host ''

Write-Host '[1/5] Stop backend listeners on port 8000...'
Stop-ListenersOnPort -Port 8000

Write-Host '[2/5] Stop frontend listeners on port 5173...'
Stop-ListenersOnPort -Port 5173
Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host 'Old processes cleared.'
Write-Host ''

$pythonExe = Resolve-PythonExe
$frontend = Resolve-FrontendRunner

Write-Host '[3/5] Verify backend dependencies...'
try {
    Test-BackendImport -PythonExe $pythonExe
    Write-Host 'Backend import OK.'
} catch {
    Write-Host ''
    Write-Host 'ERROR: Backend cannot start.' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ''
    Write-Host 'Fix: cd backend'
    Write-Host '     .\.venv\Scripts\python.exe -m pip install -e .'
    Write-Host ''
    Read-Host 'Press Enter to exit'
    exit 1
}
Write-Host ''

Write-Host '[4/5] Start backend http://127.0.0.1:8000 ...'
$backendCmd = "cd /d `"$BackendDir`" && `"$pythonExe`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $backendCmd -WindowStyle Normal

Write-Host '[5/5] Start frontend http://127.0.0.1:5173 ...'
$frontendCmd = "cd /d `"$($frontend.WorkDir)`" && `"$($frontend.File)`" $($frontend.Args -join ' ')"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $frontendCmd -WindowStyle Normal

Write-Host ''
Write-Host 'Waiting for services (up to 20s)...'
$backendOk = $false
$frontendOk = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 2
    if (-not $backendOk) { $backendOk = Test-HttpOk 'http://127.0.0.1:8000/health' }
    if (-not $frontendOk) { $frontendOk = Test-HttpOk 'http://127.0.0.1:5173/' }
    if ($backendOk -and $frontendOk) { break }
}

Write-Host ''
Write-Host '============================================'
if ($backendOk -and $frontendOk) {
    Write-Host '  Services started successfully' -ForegroundColor Green
} else {
    Write-Host '  Startup incomplete - check CMD windows' -ForegroundColor Yellow
    if (-not $backendOk) { Write-Host '  Backend  :8000 NOT responding (see backend CMD window)' -ForegroundColor Red }
    if (-not $frontendOk) { Write-Host '  Frontend :5173 NOT responding (see frontend CMD window)' -ForegroundColor Red }
}
Write-Host '============================================'
Write-Host ''
Write-Host '  Backend:  http://127.0.0.1:8000'
Write-Host '  Frontend: http://127.0.0.1:5173/login'
Write-Host '  Health:   http://127.0.0.1:8000/health'
Write-Host ''
Write-Host 'Two CMD windows stay open; close them to stop services.'
Write-Host ''

if ($frontendOk) {
    Start-Process 'http://127.0.0.1:5173/login'
}

Write-Host 'Press Enter to close this window (services keep running)...'
Read-Host | Out-Null
