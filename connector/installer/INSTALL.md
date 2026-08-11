# onetix Connector — Installer Build Guide

Connector runtime already works. This packages it into
`ONETIX-Connector-Setup-1.1.20.exe` (canonical backend-served installer).

**Brand note:** The wizard shows **onetix** (fonts, logo, labels). Install
paths, AppId, and the Windows service name stay **ONEVO** so existing shops
upgrade without migration (`Program Files\ONEVO\Connector`,
`%ProgramData%\ONEVO\Connector`, service `ONEVOConnector`).

## 1. Prerequisites (one-time)

- Windows 10/11 x64
- Python 3.11 (recommended; 3.12+ may work with a matching PyInstaller)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) installed
- Windows FFmpeg build (`ffmpeg.exe`)
- WinSW x64 (`WinSW-x64.exe`)

Place the two binaries here (not in git — must be added manually):

```
connector/installer/tools/ffmpeg.exe
connector/installer/tools/WinSW-x64.exe

For local Docker development, do not populate these files manually. Run
`dev-up.cmd`; it downloads/caches both tools, installs the pinned Python
packages, rebuilds a missing or stale installer, and then starts Docker Compose.
```

Missing either file = build fails immediately. See `tools/README.md`.

### Brand assets (checked in)

```
connector/installer/assets/onetix.ico
connector/installer/assets/onevo.ico          # same mark; kept for compatibility
connector/installer/assets/wizard-side.bmp    # 164×314 sidebar
connector/installer/assets/wizard-small.bmp   # 55×55
connector/installer/assets/fonts/             # IBM Plex Sans/Mono (OFL) + OFL.txt
```

Regenerate BMP/ICO (optional): `python connector/installer/assets/_gen_brand_assets.py`

## 2. Build

```powershell
cd connector
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-build.txt

.\installer\build.ps1 -BackendUrl https://api.your-domain.example
.\installer\build.ps1 -BackendUrl http://localhost:8081
.\installer\build.ps1 -BackendUrl http://20.193.69.220:8081 -AllowHttp
```

**Rule:** `-BackendUrl` must be `https://`, or `http://localhost:*` /
`http://127.0.0.1:*`. For MVP pilots without TLS, pass `-AllowHttp` with your
HTTP API URL. This URL gets compiled into the `.exe`; the shop owner never
sees or enters it.

### What happens during build

1. PyInstaller (`onevo-connector.spec`) → `onevo-connector.exe`
2. Inno Setup (`onevo-connector.iss`) → bundles the `.exe` + ffmpeg + WinSW →
   produces the installer

Output:

```
connector/dist/ONETIX-Connector-Setup-1.1.20.exe
```

## 3. What the installer does on a shop PC

1. Installs under `Program Files\ONEVO\Connector` (internal path; UI says onetix)
2. Registers a Windows service via WinSW (`ONEVOConnector` / display name from WinSW XML)
3. Collects a dashboard-generated setup code in the native installer
4. Collects one or more RTSP URLs, ONVIF cameras, or a local MP4 test video
5. Writes pending configuration under `%ProgramData%\ONEVO\Connector`
6. Starts the service; it claims the selected store and provisions its cameras
7. Service continuously monitors → motion clips → signed MinIO upload → backend
8. Opens the local status page at `http://localhost:8099/` after first install

If activation fails, the service **still** keeps the admin UI running at `http://localhost:8099/`. Open **Sources** (`/#sources`) to retry camera setup and **Zones** (`/#zones`) to draw detection areas. Generate a new setup code in the dashboard before retrying.

## 4. Publish it

| Environment | Action |
|---|---|
| Docker/dev | Nothing extra — `docker-compose.yml` already mounts `connector/dist` into the backend |
| Production | Copy the `.exe` to wherever `ConnectorInstaller__Path` points on the backend host. No restart needed — backend re-checks the file automatically |

## 5. Version — 3 places must match

| File | Field |
|---|---|
| `connector/installer/onevo-connector.iss` | `#define AppVersion "1.1.20"` |
| `connector/app/config.py` | `version="1.1.20"` |
| Backend env (`docker-compose.yml` / `.env`) | `ConnectorInstaller__Version` / `CONNECTOR_INSTALLER_VERSION` |

Mismatch = backend looks for a filename that doesn't exist =
`GET /api/connectors/installer` 404s.

## 6. Verify

1. `GET /api/connectors/installer` (Admin/Manager/Installer login) → check version/size/sha256
2. Download from dashboard **Setup & Zones** → **Install**, run as Administrator on a test PC
3. Generate a setup code on the same page (select a store first), complete the wizard (RTSP or MP4)
4. Confirm dashboard shows **Installed · Online** after ~2 min

## Common build errors

| Error | Cause |
|---|---|
| `Missing ...ffmpeg.exe` | Tool not placed in `installer/tools/` |
| `Missing ...WinSW-x64.exe` | Same, other tool |
| `Production requires HTTPS...` | `-BackendUrl` isn't https/localhost |
| `Inno Setup 6 (ISCC.exe) was not found` | Inno Setup not installed / not on PATH |
| `PyInstaller build failed` | Check `pip install -r requirements-build.txt` ran in the active venv |
| `localhost:8099` refused after install | Check `ONEVO Local Connector` service in `services.msc`; read `onevo-connector-service.out.log` in the install folder; verify setup code is fresh; open `http://localhost:8099/#sources` to retry |
| Setup code already used | Generate a new code in the dashboard, then open `http://localhost:8099/#sources` or reinstall |
| Upload timeout to `:9000` | ONEVO admin must open Azure NSG port **9000** and set `S3_PUBLIC_ENDPOINT=http://<VM_IP>:9000`; from shop PC run `Test-NetConnection <VM_IP> -Port 9000` |
| `disk_critical` / `disk_warning` | Free space on C: (connector checks the whole drive); pause monitoring at http://localhost:8099 and use **Clear local clips** |
| Clips queue but Uploads OK stays 0 | Check logs for `:9000` timeout; fix MinIO reachability first, then restart ONEVO Connector service |
| Theft MP4 did not alert | Motion cuts may miss the theft moment — use **Upload full source file** on http://localhost:8099; check dashboard **Clips** for risk score (needs ≥ 40) |

## 7. Connector admin controls (http://localhost:8099)

| Action | When to use |
|---|---|
| **Pause monitoring** | Stop new motion clips without stopping the Windows service |
| **Clear local clips** | Free disk after test uploads (`data\clips\` cache) |
| **Upload full source file** | Test a known theft MP4 end-to-end (no motion cutting) |
| **Clip window (pre/post)** | Widen motion cuts (try 30s + 30s for pilot demos) |
| **Cut clip now** | Manual trigger for live RTSP when you see suspicious activity |

To fully stop the connector, use Windows Services (`net stop ONEVO-Connector` or Services.msc).
