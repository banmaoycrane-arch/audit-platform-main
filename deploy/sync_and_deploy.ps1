# Sync local code to Aliyun and run full deploy (code + schema + web)
# Usage: .\deploy\sync_and_deploy.ps1
# Optional: -SkipBuild  (only sync files, no remote deploy)

param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$KeyItem = Get-ChildItem -Path (Join-Path $env:USERPROFILE "Desktop\xlsx\*\id_banmao.pem") -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $KeyItem) {
    throw "SSH key not found under Desktop\xlsx\*\id_banmao.pem"
}
# scp/ssh on Windows mangle non-ASCII paths; copy key to ASCII-only temp path first.
$KEY = Join-Path $env:TEMP "id_banmao.pem"
Copy-Item -LiteralPath $KeyItem.FullName -Destination $KEY -Force
Write-Host "Using SSH key: $($KeyItem.FullName)" -ForegroundColor DarkGray
$SshHost = "root@47.122.117.76"
$REMOTE = "/root/audit-platform-main"
$ROOT = Split-Path -Parent $PSScriptRoot
$TGZ = Join-Path $env:TEMP "audit-deploy.tgz"

Write-Host "=== [1/3] Pack local code ===" -ForegroundColor Cyan
Push-Location $ROOT
try {
    if (Test-Path $TGZ) { Remove-Item $TGZ -Force }
    tar -czf $TGZ `
        --exclude=node_modules `
        --exclude=.git `
        --exclude=backend/.venv `
        --exclude=backend/.env `
        --exclude=qdrant_local_storage `
        --exclude=frontend/node_modules `
        --exclude=backend/finance_audit.db `
        --exclude=backend/__pycache__ `
        .
    $sizeMb = [math]::Round((Get-Item $TGZ).Length / 1MB, 1)
    Write-Host "Created $TGZ ($sizeMb MB)"
}
finally {
    Pop-Location
}

Write-Host "=== [2/3] Upload to server ===" -ForegroundColor Cyan
scp -i $KEY -o StrictHostKeyChecking=no $TGZ "${SshHost}:/tmp/audit-deploy.tgz"

Write-Host "=== [3/3] Extract (preserve deploy/.env) ===" -ForegroundColor Cyan
ssh -i $KEY -o StrictHostKeyChecking=no $SshHost @"
set -e
cd $REMOTE
cp deploy/.env /tmp/deploy.env.bak
tar -xzf /tmp/audit-deploy.tgz
cp /tmp/deploy.env.bak deploy/.env
sed -i 's/\r$//' deploy/*.sh 2>/dev/null || true
rm -f /tmp/audit-deploy.tgz
echo EXTRACT_OK
"@

if ($SkipBuild) {
    Write-Host "SkipBuild: code synced only." -ForegroundColor Yellow
    exit 0
}

Write-Host "=== [4/4] Remote full deploy (code + schema + web) ===" -ForegroundColor Cyan
ssh -i $KEY -o StrictHostKeyChecking=no $SshHost "sh $REMOTE/deploy/prod_deploy_full.sh"

Write-Host ""
Write-Host "DONE. Open https://47.122.117.76/login and hard-refresh (Ctrl+F5)." -ForegroundColor Green
