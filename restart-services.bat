@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Refresh PATH from registry so desktop shortcut finds node/pnpm/npm
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "MACHINE_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
if defined MACHINE_PATH set "PATH=%MACHINE_PATH%;%PATH%"
if defined USER_PATH set "PATH=%USER_PATH%;%PATH%"
if exist "%ProgramFiles%\nodejs" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%LOCALAPPDATA%\pnpm" set "PATH=%LOCALAPPDATA%\pnpm;%PATH%"
if exist "%APPDATA%\npm" set "PATH=%APPDATA%\npm;%PATH%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart-services.ps1"
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Restart failed with exit code %EXIT_CODE%.
  echo.
  echo If message says pnpm/npm not found, install Node.js LTS then run:
  echo   corepack enable
  echo   corepack prepare pnpm@9.0.0 --activate
  echo.
  pause
)
exit /b %EXIT_CODE%
