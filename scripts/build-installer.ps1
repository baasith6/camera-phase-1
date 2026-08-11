# Wrapper for connector/installer/build.ps1 — builds the canonical ONETIX installer EXE.
param(
  [Parameter(Mandatory = $true)]
  [string]$BackendUrl,
  [string]$PythonPath = "",
  [string]$IsccPath = "",
  [switch]$AllowHttp
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $root "connector\installer\build.ps1"

if (-not (Test-Path $buildScript)) {
  throw "Missing $buildScript"
}

Write-Host "Building ONETIX connector installer for $BackendUrl ..."
$buildArgs = @{ BackendUrl = $BackendUrl }
if ($PythonPath) { $buildArgs.PythonPath = $PythonPath }
if ($IsccPath) { $buildArgs.IsccPath = $IsccPath }
if ($AllowHttp) { $buildArgs.AllowHttp = $true }
& $buildScript @buildArgs

$dist = Join-Path $root "connector\dist"
$version = (Select-String -Path (Join-Path $root "connector\installer\onevo-connector.iss") `
  -Pattern '#define AppVersion "([^"]+)"' | Select-Object -First 1).Matches.Groups[1].Value
$setup = Get-Item (Join-Path $dist "ONETIX-Connector-Setup-$version.exe")
Write-Host "Built: $($setup.FullName) ($([math]::Round($setup.Length / 1MB, 1)) MB)"

Write-Host "Mount connector/dist into backend (docker-compose) or copy to ConnectorInstaller__Path."
