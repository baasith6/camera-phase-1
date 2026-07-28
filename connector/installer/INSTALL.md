# ONEVO Connector — Installer Build Guide

Connector runtime already works. This packages it into
`ONEVO-Connector-Setup-1.1.0.exe`.

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
```

Missing either file = build fails immediately. See `tools/README.md`.

## 2. Build

```powershell
cd connector
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-build.txt

.\installer\build.ps1 -BackendUrl https://api.your-domain.example
.\installer\build.ps1 -BackendUrl http://localhost:8081
```

**Rule:** `-BackendUrl` must be `https://`, or `http://localhost:*` /
`http://127.0.0.1:*`. Any other plain-HTTP URL throws an error — no
exceptions. This URL gets compiled into the `.exe`; the shop owner never
sees or enters it.

### What happens during build

1. PyInstaller (`onevo-connector.spec`) → `onevo-connector.exe`
2. Inno Setup (`onevo-connector.iss`) → bundles the `.exe` + ffmpeg + WinSW →
   produces the installer

Output:

```
connector/dist/ONEVO-Connector-Setup-1.1.0.exe
```

## 3. What the installer does on a shop PC

1. Installs under `Program Files\ONEVO\Connector`
2. Registers a Windows service via WinSW (`ONEVO Local Connector`)
3. Collects a dashboard-generated setup code in the native installer
4. Collects one or more RTSP URLs, ONVIF cameras, or a local MP4 test video
5. Writes pending configuration under `%ProgramData%\ONEVO\Connector`
6. Starts the service; it claims the selected store and provisions its cameras
7. Service continuously monitors → motion clips → signed MinIO upload → backend

## 4. Publish it

| Environment | Action |
|---|---|
| Docker/dev | Nothing extra — `docker-compose.yml` already mounts `connector/dist` into the backend |
| Production | Copy the `.exe` to wherever `ConnectorInstaller__Path` points on the backend host. No restart needed — backend re-checks the file automatically |

## 5. Version — 3 places must match

| File | Field |
|---|---|
| `connector/installer/onevo-connector.iss` | `#define AppVersion "1.1.0"` |
| `connector/app/config.py` | `version="1.1.0"` |
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
