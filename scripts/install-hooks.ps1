# Git Hooks 安装脚本（Windows PowerShell）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/install-hooks.ps1

$hookSource = "scripts/commit-msg-hook.sh"
$hookTarget = ".git/hooks/commit-msg"

if (-not (Test-Path ".git/hooks")) {
    New-Item -ItemType Directory -Force -Path ".git/hooks" | Out-Null
}

if (Test-Path $hookSource) {
    Copy-Item $hookSource $hookTarget -Force
    Write-Host "已安装 commit-msg hook 到 $hookTarget" -ForegroundColor Green
    Write-Host "提交信息将自动校验 Conventional Commits 规范" -ForegroundColor Cyan
} else {
    Write-Host "错误：找不到 $hookSource" -ForegroundColor Red
    exit 1
}
