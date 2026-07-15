# Create / refresh desktop shortcut for restart-services.ps1
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$scriptPath = Join-Path $Root 'restart-services.ps1'
$batPath = Join-Path $Root 'restart-services.bat'
$shortcutPath = Join-Path $desktop '重启财务审计服务.lnk'

if (-not (Test-Path $scriptPath)) {
    throw "Script not found: $scriptPath"
}

# Remove older duplicates that point to the same restart-services.bat
Get-ChildItem -LiteralPath $desktop -Filter '*.lnk' | ForEach-Object {
    $existing = $ws.CreateShortcut($_.FullName)
    if ($existing.TargetPath -eq $batPath -and $_.FullName -ne $shortcutPath) {
        Remove-Item -LiteralPath $_.FullName -Force
        Write-Output "Removed duplicate shortcut: $($_.Name)"
    }
}

$shortcut = $ws.CreateShortcut($shortcutPath)
# Use .bat so double-click works even when PowerShell script association is restricted
$shortcut.TargetPath = $batPath
$shortcut.WorkingDirectory = $Root
$shortcut.IconLocation = 'C:\Windows\System32\shell32.dll,44'
$shortcut.Description = 'Restart backend :8000 and frontend :5173'
$shortcut.Save()

Write-Output "Shortcut created: $shortcutPath"
Write-Output "Target: $batPath"
