# Sync this working tree to Aliyun and upgrade production Alembic to head (0035).
# Usage (repo root, Windows PowerShell):
#   .\deploy\upgrade_prod_schema_to_head.ps1
# Optional:
#   .\deploy\upgrade_prod_schema_to_head.ps1 -SkipWebRebuild

param(
    [switch]$SkipWebRebuild
)

$ErrorActionPreference = "Stop"

$KeyItem = Get-ChildItem -Path (Join-Path $env:USERPROFILE "Desktop\xlsx\*\id_banmao.pem") -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $KeyItem) {
    throw "SSH key not found under Desktop\xlsx\*\id_banmao.pem"
}

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
    if (-not (Test-Path "backend\alembic\versions\0035_document_tag_ledger_id.py")) {
        throw "Missing 0035 migration. Checkout a branch that contains 0035 first."
    }
    if (-not (Test-Path "deploy\upgrade_prod_alembic_to_head.sh")) {
        throw "Missing deploy/upgrade_prod_alembic_to_head.sh"
    }
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

Write-Host "=== [2/3] Upload + extract (preserve deploy/.env) ===" -ForegroundColor Cyan
scp -i $KEY -o StrictHostKeyChecking=no $TGZ "${SshHost}:/tmp/audit-deploy.tgz"
ssh -i $KEY -o StrictHostKeyChecking=no $SshHost @"
set -e
cd $REMOTE
cp deploy/.env /tmp/deploy.env.bak
tar -xzf /tmp/audit-deploy.tgz
cp /tmp/deploy.env.bak deploy/.env
sed -i 's/\r$//' deploy/*.sh 2>/dev/null || true
chmod +x deploy/upgrade_prod_alembic_to_head.sh deploy/prod_upgrade_alembic_head.sh
rm -f /tmp/audit-deploy.tgz
echo EXTRACT_OK
"@

Write-Host "=== [3/3] Remote rebuild + Alembic head ===" -ForegroundColor Cyan
if ($SkipWebRebuild) {
    ssh -i $KEY -o StrictHostKeyChecking=no $SshHost "SKIP_WEB=1 sh $REMOTE/deploy/prod_upgrade_alembic_head.sh"
} else {
    ssh -i $KEY -o StrictHostKeyChecking=no $SshHost "sh $REMOTE/deploy/prod_upgrade_alembic_head.sh"
}

Write-Host ""
Write-Host "DONE. Expect alembic current = 0035_document_tag_ledger_id" -ForegroundColor Green
Write-Host "Open https://47.122.117.76:8443/login and hard-refresh (Ctrl+F5)." -ForegroundColor Green
