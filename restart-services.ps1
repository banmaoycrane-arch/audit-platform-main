# Restart finance audit platform (backend :8000, frontend :5173)
# Designed for Windows desktop shortcut (restart-services.bat → this script).
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'

function Import-UserPath {
    # -NoProfile 启动时 PATH 可能不完整；从注册表合并用户/系统 PATH
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $merged = @($machine, $user, $env:Path) | Where-Object { $_ } | ForEach-Object { $_ }
    $env:Path = ($merged -join ';')
}

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
    $candidates = @(
        (Join-Path $BackendDir '.venv\Scripts\python.exe'),
        (Join-Path $Root '.venv\Scripts\python.exe')
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw '找不到 Python。请先: cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e .'
}

function Find-CmdOnDisk {
    param([string[]]$Names)
    $dirs = @(
        $env:LOCALAPPDATA + '\pnpm',
        $env:APPDATA + '\npm',
        $env:ProgramFiles + '\nodejs',
        ${env:ProgramFiles(x86)} + '\nodejs',
        $env:LOCALAPPDATA + '\Programs\node',
        $env:USERPROFILE + '\AppData\Roaming\npm',
        $env:USERPROFILE + '\scoop\shims',
        $env:USERPROFILE + '\.local\share\pnpm'
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($dir in $dirs) {
        foreach ($name in $Names) {
            $full = Join-Path $dir $name
            if (Test-Path $full) { return $full }
        }
    }

    # where.exe 兜底（不依赖 PowerShell Get-Command）
    foreach ($name in $Names) {
        try {
            $found = & where.exe $name 2>$null | Select-Object -First 1
            if ($found -and (Test-Path $found)) { return $found }
        } catch { }
    }
    return $null
}

function Resolve-NodeExe {
    $cmd = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return Find-CmdOnDisk @('node.exe')
}

function Ensure-Pnpm {
    # 1) 已在 PATH
    $pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if ($pnpm) { return $pnpm.Source }
    $pnpm = Get-Command pnpm.exe -ErrorAction SilentlyContinue
    if ($pnpm) { return $pnpm.Source }

    # 2) 磁盘常见位置
    $onDisk = Find-CmdOnDisk @('pnpm.cmd', 'pnpm.exe', 'pnpm')
    if ($onDisk) { return $onDisk }

    # 3) 有 Node 则用 corepack / npm 安装 pnpm（项目约定 pnpm@9）
    $nodeExe = Resolve-NodeExe
    if (-not $nodeExe) {
        return $null
    }

    $nodeDir = Split-Path -Parent $nodeExe
    $corepack = Join-Path $nodeDir 'corepack.cmd'
    $npmCmd = Join-Path $nodeDir 'npm.cmd'
    if (-not (Test-Path $npmCmd)) {
        $npmCmd = Find-CmdOnDisk @('npm.cmd')
    }

    Write-Host '[info] 未找到 pnpm，尝试用 Node 自带的 corepack/npm 安装...' -ForegroundColor Yellow

    if (Test-Path $corepack) {
        try {
            & $corepack enable 2>$null | Out-Null
            & $corepack prepare pnpm@9.0.0 --activate 2>$null | Out-Null
        } catch { }
    }

    $pnpm = Find-CmdOnDisk @('pnpm.cmd', 'pnpm.exe')
    if ($pnpm) { return $pnpm }
    $pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if ($pnpm) { return $pnpm.Source }

    if ($npmCmd -and (Test-Path $npmCmd)) {
        try {
            & $npmCmd install -g pnpm@9 2>&1 | Write-Host
        } catch {
            Write-Host $_.Exception.Message -ForegroundColor Yellow
        }
    }

    Import-UserPath
    $pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if ($pnpm) { return $pnpm.Source }
    return Find-CmdOnDisk @('pnpm.cmd', 'pnpm.exe')
}

function Resolve-FrontendRunner {
    $pnpmPath = Ensure-Pnpm
    if ($pnpmPath) {
        Write-Host "[info] 使用 pnpm: $pnpmPath"
        # 首次缺依赖时自动 install
        if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
            Write-Host '[info] frontend/node_modules 不存在，正在 pnpm install...' -ForegroundColor Yellow
            & $pnpmPath --dir $FrontendDir install
            if ($LASTEXITCODE -ne 0) {
                throw 'pnpm install 失败，请手动: cd frontend; pnpm install'
            }
        }
        return @{
            File = $pnpmPath
            Args = @('--dir', $FrontendDir, 'dev', '--host', '127.0.0.1', '--port', '5173')
            WorkDir = $Root
        }
    }

    $npmPath = Find-CmdOnDisk @('npm.cmd')
    if (-not $npmPath) {
        $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if ($npmCmd) { $npmPath = $npmCmd.Source }
    }
    if ($npmPath) {
        Write-Host "[info] 未找到 pnpm，回退 npm: $npmPath" -ForegroundColor Yellow
        if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
            Write-Host '[info] frontend/node_modules 不存在，正在 npm install...' -ForegroundColor Yellow
            Push-Location $FrontendDir
            try { & $npmPath install } finally { Pop-Location }
        }
        return @{
            File = $npmPath
            Args = @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173')
            WorkDir = $FrontendDir
        }
    }

    $msg = @"
找不到 pnpm / npm，无法启动前端。

请任选一种方式安装后，重新双击「重启财务审计服务」：

1) 安装 Node.js LTS（含 npm）: https://nodejs.org/
   安装完成后打开新的 PowerShell，执行:
     corepack enable
     corepack prepare pnpm@9.0.0 --activate

2) 或已安装 Node 时，在 PowerShell 执行:
     npm install -g pnpm@9

当前探测到的 Node: $(if (Resolve-NodeExe) { Resolve-NodeExe } else { '未找到' })
"@
    throw $msg
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

Import-UserPath

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
# Args 含路径时需正确引号，避免空格路径断裂
$argLine = ($frontend.Args | ForEach-Object {
    if ($_ -match '\s') { '"{0}"' -f $_ } else { $_ }
}) -join ' '
$frontendCmd = "cd /d `"$($frontend.WorkDir)`" && `"$($frontend.File)`" $argLine"
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
