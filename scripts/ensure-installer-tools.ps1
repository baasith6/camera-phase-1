# Ensure connector/installer/tools has ffmpeg.exe and WinSW-x64.exe (gitignored).
param(
  [string]$ToolsDir = "",
  [string]$CacheDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $ToolsDir) { $ToolsDir = Join-Path $root "connector\installer\tools" }
if (-not $CacheDir) { $CacheDir = Join-Path $env:ProgramData "onevo\installer-tools" }

New-Item -ItemType Directory -Force -Path $ToolsDir, $CacheDir | Out-Null

$ffmpegDest = Join-Path $ToolsDir "ffmpeg.exe"
$winswDest = Join-Path $ToolsDir "WinSW-x64.exe"
$ffmpegCache = Join-Path $CacheDir "ffmpeg.exe"
$winswCache = Join-Path $CacheDir "WinSW-x64.exe"

$ffmpegZipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$winswUrl = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"

function Copy-IfMissing([string]$Source, [string]$Dest, [string]$Label) {
  if (Test-Path $Dest) { return }
  if (-not (Test-Path $Source)) { throw "Missing cached $Label at $Source" }
  Copy-Item -Force $Source $Dest
  Write-Host "    Copied $Label -> $Dest"
}

function Download-File([string]$Url, [string]$Dest) {
  Write-Host "    Downloading $Url ..."
  Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
}

if (-not (Test-Path $ffmpegCache)) {
  $zipPath = Join-Path $CacheDir "ffmpeg-release-essentials.zip"
  Download-File $ffmpegZipUrl $zipPath
  $extractDir = Join-Path $CacheDir "ffmpeg-extract"
  if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
  Expand-Archive -Path $zipPath -DestinationPath $extractDir
  $ffmpegBin = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" |
    Where-Object { $_.FullName -match '\\bin\\ffmpeg\.exe$' } |
    Select-Object -First 1
  if (-not $ffmpegBin) { throw "ffmpeg.exe not found inside downloaded archive" }
  Copy-Item -Force $ffmpegBin.FullName $ffmpegCache
  Remove-Item $extractDir -Recurse -Force
  Remove-Item $zipPath -Force
  Write-Host "    Cached ffmpeg.exe"
}

if (-not (Test-Path $winswCache)) {
  Download-File $winswUrl $winswCache
  Write-Host "    Cached WinSW-x64.exe"
}

Copy-IfMissing $ffmpegCache $ffmpegDest "ffmpeg.exe"
Copy-IfMissing $winswCache $winswDest "WinSW-x64.exe"
Write-Host "Installer tools ready in $ToolsDir"
