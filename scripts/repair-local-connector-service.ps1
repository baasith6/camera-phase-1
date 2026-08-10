[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$installDir = "C:\Program Files\ONEVO\Connector"
$binDir = Join-Path $installDir "bin"
$dataDir = "C:\ProgramData\ONEVO\Connector\data"
$mediaDir = "C:\ProgramData\ONEVO\Connector\media"
$serviceExe = Join-Path $installDir "onevo-connector-service.exe"

New-Item -ItemType Directory -Force -Path $installDir, $binDir, $dataDir, $mediaDir | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "connector\dist\onevo-connector.exe") `
  -Destination (Join-Path $installDir "onevo-connector.exe") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "connector\installer\tools\ffmpeg.exe") `
  -Destination (Join-Path $binDir "ffmpeg.exe") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "connector\installer\tools\WinSW-x64.exe") `
  -Destination $serviceExe -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "connector\installer\winsw\onevo-connector-service.xml") `
  -Destination (Join-Path $installDir "onevo-connector-service.xml") -Force

$existing = Get-Service ONEVOConnector -ErrorAction SilentlyContinue
if (-not $existing) { & $serviceExe install }
& $serviceExe start

Get-Service ONEVOConnector | Select-Object Status, Name
