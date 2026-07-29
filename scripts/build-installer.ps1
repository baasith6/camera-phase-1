# Wrapper for connector/installer/build.ps1 — builds ONEVO-Connector-Setup EXE.
param(
  [Parameter(Mandatory = $true)]
  [string]$BackendUrl,
  [string]$PythonPath = "",
  [switch]$AllowHttp
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $root "connector\installer\build.ps1"

if (-not (Test-Path $buildScript)) {
  throw "Missing $buildScript"
}

Write-Host "Building ONEVO connector installer for $BackendUrl ..."
$buildArgs = @{ BackendUrl = $BackendUrl }
if ($PythonPath) { $buildArgs.PythonPath = $PythonPath }
if ($AllowHttp) { $buildArgs.AllowHttp = $true }
& $buildScript @buildArgs

$dist = Join-Path $root "connector\dist"
Get-ChildItem $dist -Filter "ONEVO-Connector-Setup-*.exe" | ForEach-Object {
  Write-Host "Built: $($_.FullName) ($([math]::Round($_.Length / 1MB, 1)) MB)"
}

Write-Host "Mount connector/dist into backend (docker-compose) or copy to ConnectorInstaller__Path."
