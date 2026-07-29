# Deploy ONEVO stack to Azure VM via tarball + docker compose build on VM.
param(
  [string]$VmHost = "20.193.69.220",
  [string]$VmUser = "azureuser",
  [string]$VmAppDir = "/opt/onevo/app",
  [string]$BackendUrl = "http://20.193.69.220:8081",
  [string]$SshKeyPath = "",
  [string]$PythonPath = "",
  [string]$IsccPath = "",
  [switch]$SkipInstaller,
  [switch]$SkipBuild,
  [switch]$UseGpu
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tarball = Join-Path $env:TEMP "onevo-deploy.tar.gz"

function Prepare-SshKey([string]$KeyPath) {
  if (-not $KeyPath -or -not (Test-Path $KeyPath)) {
    throw "SSH key not found (pass -SshKeyPath or configure default ~/.ssh key). Got: '$KeyPath'"
  }
  $dest = Join-Path $env:TEMP ("onevo-deploy-key-{0}" -f [Guid]::NewGuid().ToString("N"))
  $raw = [IO.File]::ReadAllText($KeyPath) -replace "`r`n", "`n" -replace "`r", "`n"
  if (-not $raw.EndsWith("`n")) { $raw += "`n" }
  [IO.File]::WriteAllText($dest, $raw)
  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  & icacls $dest /inheritance:r /grant:r "${identity}:(R)" | Out-Null
  return $dest
}

function Invoke-Checked {
  param([string]$Label, [scriptblock]$Command)
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Label failed (exit $LASTEXITCODE)"
  }
}

function Get-SshArgs([string]$KeyPath) {
  if ($KeyPath -and (Test-Path $KeyPath)) {
    return @("-i", $KeyPath, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes")
  }
  return @("-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes")
}

$preparedKey = $null
if ($SshKeyPath) { $preparedKey = Prepare-SshKey $SshKeyPath }
$sshArgs = Get-SshArgs $preparedKey
$scpArgs = @($sshArgs) + @("${VmUser}@${VmHost}:")

Write-Host "==> Packaging app (excluding large artifacts)..."
if (Test-Path $tarball) { Remove-Item $tarball -Force }

Push-Location $root
try {
  tar --exclude="connector/dist" `
      --exclude="dashboard/node_modules" `
      --exclude="dashboard/dist" `
      --exclude="backend/bin" `
      --exclude="backend/obj" `
      --exclude="installer-site/*.exe" `
      --exclude=".git" `
      --exclude=".cursor" `
      -czf $tarball `
      backend dashboard connector cloud-ai `
      docker-compose.yml docker-compose.prod.yml docker-compose.gpu.yml docker-compose.acr.yml `
      installer-site infra/mvp scripts

  tar -tzf $tarball | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Tarball verification failed" }
  $sizeMb = [math]::Round((Get-Item $tarball).Length / 1MB, 1)
  Write-Host "    Tarball OK ($sizeMb MB)"
} finally {
  Pop-Location
}

Write-Host "==> Uploading to ${VmUser}@${VmHost}..."
Invoke-Checked "SCP tarball" { scp @sshArgs $tarball "${VmUser}@${VmHost}:/tmp/onevo-deploy.tar.gz" }

$installerExe = $null
if (-not $SkipInstaller) {
  Write-Host "==> Ensuring installer tools (ffmpeg, WinSW)..."
  & (Join-Path $root "scripts\ensure-installer-tools.ps1")
  Write-Host "==> Building Windows installer..."
  $installerArgs = @{ BackendUrl = $BackendUrl; AllowHttp = $true }
  if ($PythonPath) { $installerArgs.PythonPath = $PythonPath }
  if ($IsccPath) { $installerArgs.IsccPath = $IsccPath }
  & (Join-Path $root "scripts\build-installer.ps1") @installerArgs
  $installerExe = Get-ChildItem (Join-Path $root "connector\dist\ONEVO-Connector-Setup-*.exe") |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $installerExe) { throw "Installer EXE not found after build" }
  Invoke-Checked "SCP installer" { scp @sshArgs $installerExe.FullName "${VmUser}@${VmHost}:/tmp/$($installerExe.Name)" }
  $installerRemoteName = $installerExe.Name
} else {
  $installerRemoteName = ""
}

$gpuFlag = if ($UseGpu) { "true" } else { "false" }
$buildCmd = if ($SkipBuild) {
  "docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans"
} else {
  "DEPLOY_MODE=local USE_GPU=$gpuFlag bash infra/mvp/deploy.sh"
}

$remoteScript = @"
set -e
cd $VmAppDir
echo '==> Extracting deploy archive...'
tar -xzf /tmp/onevo-deploy.tar.gz
chmod +x infra/mvp/deploy.sh
if [ -n "$installerRemoteName" ] && [ -f "/tmp/$installerRemoteName" ]; then
  mkdir -p installer-site connector/dist
  cp "/tmp/$installerRemoteName" "installer-site/$installerRemoteName"
  cp "/tmp/$installerRemoteName" "connector/dist/$installerRemoteName"
  ls -lh "installer-site/$installerRemoteName"
fi
echo '==> Deploying containers...'
export ONEVO_DIR=$VmAppDir
$buildCmd
echo '==> Health check...'
curl -sf http://127.0.0.1:8081/api/health
echo
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
"@ -replace "`r`n", "`n"

Write-Host "==> Running remote deploy..."
try {
  Invoke-Checked "SSH deploy" {
    $remoteScript | ssh @sshArgs "${VmUser}@${VmHost}" "bash -s"
  }
} finally {
  if ($preparedKey -and (Test-Path $preparedKey)) { Remove-Item $preparedKey -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
Write-Host "Deploy complete."
Write-Host "  Dashboard: http://${VmHost}:4200"
Write-Host "  API:       http://${VmHost}:8081/api/health"
