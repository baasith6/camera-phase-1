[CmdletBinding()]
param(
  [string]$BackendUrl = "http://localhost:8081",
  [string]$PythonPath = "",
  [string]$IsccPath = "",
  [switch]$ForceInstallerBuild,
  [switch]$SkipInstallerBuild,
  [switch]$AllowHttp,
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$issPath = Join-Path $repoRoot "connector\installer\onevo-connector.iss"
$distDir = Join-Path $repoRoot "connector\dist"
$fingerprintPath = Join-Path $distDir ".installer-build.json"

function Read-InstallerVersion {
  $match = Select-String -Path $issPath -Pattern '#define AppVersion "([^"]+)"' | Select-Object -First 1
  if (-not $match) { throw "AppVersion was not found in $issPath" }
  return $match.Matches.Groups[1].Value
}

function Get-BuildFingerprint([string]$Url) {
  $inputs = @(
    (Join-Path $repoRoot "connector\app"),
    (Join-Path $repoRoot "connector\onevo_launcher.py"),
    (Join-Path $repoRoot "connector\requirements.txt"),
    (Join-Path $repoRoot "connector\requirements-build.txt"),
    (Join-Path $repoRoot "connector\installer\onevo-connector.spec"),
    (Join-Path $repoRoot "connector\installer\onevo-connector.iss"),
    (Join-Path $repoRoot "connector\installer\winsw\onevo-connector-service.xml"),
    (Join-Path $repoRoot "connector\installer\assets")
  )
  $files = foreach ($input in $inputs) {
    if (Test-Path -LiteralPath $input -PathType Container) {
      Get-ChildItem -LiteralPath $input -Recurse -File |
        Where-Object { $_.FullName -notmatch '\\(__pycache__|dist|build)\\' }
    } elseif (Test-Path -LiteralPath $input -PathType Leaf) { Get-Item -LiteralPath $input }
  }
  $lines = @("backendUrl=$($Url.Trim().TrimEnd('/'))")
  foreach ($file in ($files | Sort-Object FullName -Unique)) {
    $relative = $file.FullName.Substring($repoRoot.Length).TrimStart('\')
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    $lines += "$relative=$hash"
  }
  $payload = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
  $sha = [Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($sha.ComputeHash($payload))).Replace('-', '').ToLowerInvariant() }
  finally { $sha.Dispose() }
}

function Installer-IsCurrent([string]$InstallerPath, [string]$Fingerprint) {
  if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) { return $false }
  if (-not (Test-Path -LiteralPath $fingerprintPath -PathType Leaf)) { return $false }
  try {
    $metadata = Get-Content -LiteralPath $fingerprintPath -Raw | ConvertFrom-Json
    return $metadata.fingerprint -eq $Fingerprint -and
      $metadata.sha256 -eq (Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerPath).Hash.ToLowerInvariant()
  } catch { return $false }
}

if ($env:OS -ne "Windows_NT") {
  throw "The ONETIX Windows installer must be built on a Windows host. Run this script from Windows Docker Desktop."
}

$version = Read-InstallerVersion
$installerPath = Join-Path $distDir "ONETIX-Connector-Setup-$version-rev18.exe"
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
$fingerprint = Get-BuildFingerprint $BackendUrl
$needsBuild = $ForceInstallerBuild -or -not (Installer-IsCurrent $installerPath $fingerprint)

if ($SkipInstallerBuild) {
  if (-not (Test-Path -LiteralPath $installerPath)) {
    throw "Installer is missing: $installerPath. Remove -SkipInstallerBuild or run .\scripts\dev-up.ps1."
  }
  Write-Host "==> Installer build skipped by request: $installerPath"
} elseif ($needsBuild) {
  Write-Host "==> Installer is missing or stale; preparing build tools..."
  & (Join-Path $PSScriptRoot "ensure-installer-tools.ps1")
  if ($LASTEXITCODE -ne 0) { throw "Installer tool preparation failed (exit $LASTEXITCODE)" }
  $buildArgs = @{ BackendUrl = $BackendUrl }
  if ($PythonPath) { $buildArgs.PythonPath = $PythonPath }
  if ($IsccPath) { $buildArgs.IsccPath = $IsccPath }
  if ($AllowHttp -or $BackendUrl -match '^http://(localhost|127\.0\.0\.1)(:\d+)?') { $buildArgs.AllowHttp = $true }
  & (Join-Path $PSScriptRoot "build-installer.ps1") @buildArgs
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $installerPath)) {
    throw "Installer build did not produce $installerPath"
  }
  $installerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installerPath).Hash.ToLowerInvariant()
  [ordered]@{
    version = $version; backendUrl = $BackendUrl.Trim().TrimEnd('/'); fingerprint = $fingerprint
    sha256 = $installerHash; sizeBytes = (Get-Item -LiteralPath $installerPath).Length
    builtAtUtc = [DateTime]::UtcNow.ToString('o')
  } | ConvertTo-Json | Set-Content -LiteralPath $fingerprintPath -Encoding UTF8
  Write-Host "==> Installer ready: $installerPath"
} else { Write-Host "==> Installer is current: $installerPath" }

Push-Location $repoRoot
try {
  Write-Host "==> Starting Docker stack..."
  if ($Foreground) { & docker compose up --build } else { & docker compose up -d --build }
  if ($LASTEXITCODE -ne 0) {
    $firstExit = $LASTEXITCODE
    Write-Warning "Docker Compose startup failed (exit $firstExit). Reconciling only this Compose project's stale/orphan containers; named volumes are preserved."
    & docker compose down --remove-orphans
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose recovery cleanup failed (exit $LASTEXITCODE)"
    }
    if ($Foreground) { & docker compose up --build } else { & docker compose up -d --build }
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose failed after project-scoped recovery (exit $LASTEXITCODE)"
    }
  }
} finally { Pop-Location }

Write-Host "==> ONETIX stack started. Dashboard: http://localhost:4200  Backend: http://localhost:8081"
