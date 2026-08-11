@echo off
setlocal
rem Auto-build the ONETIX installer when missing or stale, then start Docker.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev-up.ps1" %*
exit /b %ERRORLEVEL%
