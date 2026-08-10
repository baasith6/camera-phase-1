# Publishes a newly built ONEVO/ONETIX connector installer:
#   1. Uploads the real EXE to Vercel Blob (gets a real url/sha256/size -
#      never a guessed/copy-pasted one).
#   2. Rewrites latest.json and index.html with those real values.
#   3. Deploys this installer-site folder to Vercel production.
#
# Usage (from repo root or anywhere):
#   cd installer-site
#   .\publish-installer-site.ps1 -ExePath "..\connector\dist\ONEVO-Connector-Setup-1.1.20.exe" -Version "1.1.20"

param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$SiteDir = $PSScriptRoot

if (-not (Test-Path $ExePath)) { throw "EXE not found: $ExePath" }
$ExePath = (Resolve-Path $ExePath).Path

# --- Load BLOB_READ_WRITE_TOKEN from .env.local (Vercel CLI writes this) ---
$envLocal = Join-Path $SiteDir ".env.local"
if (-not (Test-Path $envLocal)) { throw "Missing $envLocal (run 'vercel link' / 'vercel env pull' first)." }
$tokenLine = Select-String -Path $envLocal -Pattern '^BLOB_READ_WRITE_TOKEN="?([^"]+)"?' | Select-Object -First 1
if (-not $tokenLine) { throw "BLOB_READ_WRITE_TOKEN not found in $envLocal" }
$env:BLOB_READ_WRITE_TOKEN = $tokenLine.Matches.Groups[1].Value
Write-Host "==> Loaded BLOB_READ_WRITE_TOKEN from .env.local"

Push-Location $SiteDir
try {
    # --- Ensure @vercel/blob is installed ---
    if (-not (Test-Path (Join-Path $SiteDir "node_modules\@vercel\blob"))) {
        Write-Host "==> Installing @vercel/blob..."
        npm install @vercel/blob --no-save
        if ($LASTEXITCODE -ne 0) { throw "npm install @vercel/blob failed" }
    }

    # --- Upload to Vercel Blob, get real url/sha256/size ---
    Write-Host "==> Uploading $ExePath to Vercel Blob (this can take a while for 100+ MB)..."
    $raw = node publish.mjs $ExePath $Version
    if ($LASTEXITCODE -ne 0) { throw "publish.mjs failed:`n$raw" }
    $result = $raw | Select-Object -Last 1 | ConvertFrom-Json
    Write-Host "    url:    $($result.url)"
    Write-Host "    sha256: $($result.sha256)"
    Write-Host "    size:   $([math]::Round($result.size / 1MB, 1)) MB"

    # --- Update latest.json with real values ---
    $latestJson = [ordered]@{
        version     = $Version
        fileName    = "ONEVO-Connector-Setup-$Version.exe"
        downloadUrl = $result.url
        sizeBytes   = $result.size
        sha256      = $result.sha256
    }
    ($latestJson | ConvertTo-Json -Depth 5) | Set-Content -Path (Join-Path $SiteDir "latest.json") -Encoding UTF8
    Write-Host "==> Updated latest.json"

    # --- Update index.html (version, filename, size, download link, branding) ---
    $indexPath = Join-Path $SiteDir "index.html"
    $html = Get-Content -Path $indexPath -Raw
    $sizeMb = [math]::Round($result.size / 1MB, 1)
    $html = $html -replace 'ONEVO Connector Download', 'ONETIX Connector Download'
    $html = $html -replace '<h1>ONEVO Connector</h1>', '<h1>ONETIX Connector</h1>'
    $html = $html -replace '<span class="value">1\.1\.\d+</span>', "<span class=""value"">$Version</span>"
    $html = $html -replace 'ONEVO-Connector-Setup-[\d\.]+\.exe', "ONEVO-Connector-Setup-$Version.exe"
    $html = $html -replace '<span class="value">[\d\.]+ MB</span>', "<span class=""value"">$sizeMb MB</span>"
    $html = $html -replace 'href="https://[^"]+"\s*\n?\s*download>', "href=""$($result.url)""`n            download>"
    $html = $html -replace '© ONEVO\. All rights reserved\.', '&copy; ONETIX. All rights reserved.'
    Set-Content -Path $indexPath -Value $html -Encoding UTF8
    Write-Host "==> Updated index.html"

    # --- Deploy to Vercel production ---
    Write-Host "==> Deploying to Vercel (production)..."
    $env:NO_UPDATE_NOTIFIER = "1"
    $env:VERCEL_CLI_NO_UPDATE_NOTIFIER = "1"
    $vercelCmd = Get-Command vercel -ErrorAction SilentlyContinue
    if ($vercelCmd) {
        vercel deploy --prod --yes 2>&1 | Tee-Object -Variable deployOutput
    } else {
        npx vercel deploy --prod --yes 2>&1 | Tee-Object -Variable deployOutput
    }
    if (($LASTEXITCODE -ne 0) -and (-not ($deployOutput -join "`n" -match 'Ready in'))) {
        throw "vercel deploy failed"
    }

    Write-Host ""
    Write-Host "OK - published $Version"
    Write-Host "    Download: $($result.url)"
} finally {
    Pop-Location
}
