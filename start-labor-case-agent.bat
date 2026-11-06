@echo off
setlocal

set "APP_EXE=%LOCALAPPDATA%\Labor Case Agent\labor-case-agent-desktop.exe"
set "INSTALLER=%~dp0dist\LaborCaseAgent-UserSetup.exe"
if not exist "%INSTALLER%" set "INSTALLER=%~dp0dist\LaborCaseAgent.exe"

if /I "%~1"=="--check" goto check

tasklist /FI "IMAGENAME eq labor-case-agent-desktop.exe" 2>nul | find /I "labor-case-agent-desktop.exe" >nul
if not errorlevel 1 (
  echo Labor Case Agent is already running.
  timeout /t 2 /nobreak >nul
  exit /b 0
)

if exist "%APP_EXE%" goto launch
if not exist "%INSTALLER%" goto missing

echo Labor Case Agent is not installed. Opening the installer...
start "" /wait "%INSTALLER%"

if not exist "%APP_EXE%" (
  echo.
  echo The installed application was not found. Installation may have been cancelled.
  pause
  exit /b 1
)

:launch
echo Starting Labor Case Agent...
start "" "%APP_EXE%"
exit /b 0

:missing
echo The installed application and installer were not found.
echo Expected installer: %INSTALLER%
echo.
echo Build the installer first or restore dist\LaborCaseAgent.exe.
pause
exit /b 1

:check
if exist "%APP_EXE%" (
  echo INSTALLED_OK=%APP_EXE%
) else (
  echo INSTALLED_MISSING=%APP_EXE%
)
if exist "%INSTALLER%" (
  echo INSTALLER_OK=%INSTALLER%
) else (
  echo INSTALLER_MISSING=%INSTALLER%
)
exit /b 0
