@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev-up.ps1" %*
exit /b %ERRORLEVEL%
