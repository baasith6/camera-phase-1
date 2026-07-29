"""Local admin UI/API for the connector (installer view).

Endpoints:
  GET  /           — HTML status dashboard
  GET  /status     — JSON runtime snapshot
  GET  /health     — {"ok": true}
  POST /capture/pause|resume|trigger-now
  GET|POST /capture/settings
  GET  /clips/local
  POST /clips/clear-local
  POST /clips/upload-full-source
  GET  /onvif/discover   — WS-Discovery scan; returns list of cameras on LAN
  ...
"""
import json
import shutil
import threading
import uuid
from typing import TYPE_CHECKING, Callable

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .paths import CameraSource, WizardConfig, load_wizard_config, media_dir, save_wizard_config
from .provisioning import provision_sources, source_key_for, validate_sources
from .clip_ops import clear_local_clip_files, list_local_clip_files, prepare_clip_file, resolve_file_source
from .clip_settings import ClipSettings, load_clip_settings, save_clip_settings
from .runtime import RuntimeState

if TYPE_CHECKING:
    from .backend_client import BackendClient
    from .config import Config
    from .store import LocalStore


class CaptureSettingsBody(BaseModel):
    pre_seconds: float = Field(ge=1, le=120)
    post_seconds: float = Field(ge=1, le=120)
    cooldown_seconds: float = Field(ge=5, le=600)


def build_app(
    state: RuntimeState,
    cfg: "Config",
    client: "BackendClient | None" = None,
    store: "LocalStore | None" = None,
    enable_setup_wizard: bool = False,
    on_wizard_configured: Callable | None = None,
) -> FastAPI:
    app = FastAPI(title="ONEVO Connector Admin")

    @app.get("/status")
    def status():
        return state.snapshot()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/sources")
    def sources():
        wizard = load_wizard_config() or WizardConfig()
        return {
            "sources": [
                {
                    "name": source.name,
                    "type": (
                        "onvif" if source.onvif_host else
                        "video" if source.source_file else "rtsp"
                    ),
                    "value": (
                        source.onvif_host or source.source_file or source.rtsp_url
                    ),
                    "cameraId": source.camera_id,
                }
                for source in wizard.sources
            ]
        }

    @app.post("/sources")
    async def add_sources(
        source_type: str = Form(...),
        rtsp_text: str = Form(default=""),
        onvif_json: str = Form(default="[]"),
        files: list[UploadFile] = File(default=[]),
    ):
        if client is None or store is None:
            raise HTTPException(503, "Source management is unavailable")

        new_sources: list[CameraSource] = []
        kind = source_type.strip().lower()
        if kind == "rtsp":
            urls = [
                value.strip()
                for value in rtsp_text.replace("\r", "\n").replace(";", "\n").splitlines()
                if value.strip()
            ]
            new_sources = [
                CameraSource(name=f"Camera {index}", rtsp_url=url)
                for index, url in enumerate(urls, start=1)
            ]
        elif kind == "onvif":
            try:
                entries = json.loads(onvif_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, "Invalid ONVIF camera data") from exc
            if not isinstance(entries, list):
                raise HTTPException(400, "Invalid ONVIF camera data")
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    continue
                try:
                    port = int(entry.get("port") or 80)
                except (TypeError, ValueError) as exc:
                    raise HTTPException(
                        400, f"ONVIF camera {index}: enter a valid port"
                    ) from exc
                new_sources.append(CameraSource(
                    name=(entry.get("name") or f"ONVIF Camera {index}").strip(),
                    onvif_host=(entry.get("host") or "").strip(),
                    onvif_port=port,
                    onvif_user=(entry.get("username") or "admin").strip(),
                    onvif_pass=str(entry.get("password") or ""),
                ))
        elif kind == "video":
            for index, upload in enumerate(files, start=1):
                if not upload.filename:
                    continue
                if not upload.filename.lower().endswith(".mp4"):
                    raise HTTPException(400, f"{upload.filename}: select an MP4 video")
                destination = media_dir() / f"local-video-{uuid.uuid4().hex}.mp4"
                with destination.open("wb") as output:
                    shutil.copyfileobj(upload.file, output)
                new_sources.append(CameraSource(
                    name=f"Local Video {index}",
                    source_file=str(destination),
                    loop=True,
                ))
        else:
            raise HTTPException(400, "Choose RTSP, ONVIF, or local MP4 video")

        if not new_sources:
            raise HTTPException(400, "Add at least one source")
        try:
            validate_sources(new_sources)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        wizard = load_wizard_config() or WizardConfig(
            connector_name=cfg.connector_name,
            setup_complete=False,
        )
        existing = list(wizard.sources)
        for source in existing:
            source.source_key = source.source_key or source_key_for(source)

        wizard.sources = existing + new_sources
        wizard.setup_complete = False
        save_wizard_config(wizard)

        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if not (connector_id and api_key):
            state.log(
                f"Local admin: saved {len(new_sources)} {kind} source(s); pairing pending"
            )
            return {
                "ok": True,
                "pending": True,
                "added": len(new_sources),
                "total": len(wizard.sources),
            }
        client.set_credentials(connector_id, api_key)

        def checkpoint(created):
            wizard.sources = existing + created
            save_wizard_config(wizard)

        try:
            created = provision_sources(client, new_sources, state, checkpoint=checkpoint)
            wizard.sources = existing + created
            wizard.setup_complete = True
            save_wizard_config(wizard)
            client.finalize_setup([
                source.source_key for source in wizard.sources if source.source_key
            ])
        except Exception as exc:  # noqa: BLE001
            wizard.sources = existing + new_sources
            wizard.setup_complete = False
            save_wizard_config(wizard)
            state.log(f"Local admin: sources saved; backend activation pending: {exc}")
            return {
                "ok": True,
                "pending": True,
                "added": len(new_sources),
                "total": len(wizard.sources),
            }

        state.log(f"Local admin: added {len(created)} {kind} source(s)")
        return {"ok": True, "added": len(created), "total": len(wizard.sources)}

    @app.delete("/sources/{source_index}")
    def remove_source(source_index: int):
        if client is None or store is None:
            raise HTTPException(503, "Source management is unavailable")
        wizard = load_wizard_config() or WizardConfig()
        if source_index < 0 or source_index >= len(wizard.sources):
            raise HTTPException(404, "Source not found")
        removed = wizard.sources.pop(source_index)
        wizard.setup_complete = False
        save_wizard_config(wizard)

        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if connector_id and api_key:
            client.set_credentials(connector_id, api_key)
            try:
                for source in wizard.sources:
                    source.source_key = source.source_key or source_key_for(source)
                client.finalize_setup([
                    source.source_key for source in wizard.sources
                    if source.source_key
                ])
                wizard.setup_complete = True
                save_wizard_config(wizard)
            except Exception as exc:  # noqa: BLE001
                state.log(f"Local admin: removal saved; backend sync pending: {exc}")
        state.log(f"Local admin: removed source {removed.name}")
        return {
            "ok": True,
            "pending": not wizard.setup_complete,
            "total": len(wizard.sources),
        }
    @app.post("/capture/pause")
    def capture_pause():
        state.set_paused(True)
        return {"ok": True, "paused": True}

    @app.post("/capture/resume")
    def capture_resume():
        state.set_paused(False)
        return {"ok": True, "paused": False}

    @app.post("/capture/trigger-now")
    def capture_trigger_now():
        if not state.request_trigger():
            raise HTTPException(status_code=503, detail="Capture pipeline not running")
        state.log("Manual clip trigger requested")
        return {"ok": True}

    @app.get("/capture/settings")
    def get_capture_settings():
        return {
            "pre_seconds": cfg.pre_seconds,
            "post_seconds": cfg.post_seconds,
            "cooldown_seconds": cfg.cooldown_seconds,
            "paused": state.capture_paused,
            "approxClipSeconds": cfg.pre_seconds + cfg.post_seconds,
        }

    @app.post("/capture/settings")
    def update_capture_settings(body: CaptureSettingsBody):
        settings = ClipSettings(
            pre_seconds=body.pre_seconds,
            post_seconds=body.post_seconds,
            cooldown_seconds=body.cooldown_seconds,
        )
        settings.apply_to_config(cfg)
        save_clip_settings(settings)
        state.log(
            f"Clip settings updated: pre={cfg.pre_seconds}s post={cfg.post_seconds}s "
            f"cooldown={cfg.cooldown_seconds}s"
        )
        return get_capture_settings()

    @app.get("/clips/local")
    def clips_local():
        if store is None:
            raise HTTPException(status_code=503, detail="Store not available")
        files = list_local_clip_files(cfg.state_dir)
        jobs = store.list_queue_jobs()
        pending = sum(1 for j in jobs if j.state in ("pending", "uploading"))
        return {
            "fileCount": len(files),
            "files": files,
            "queuePending": pending,
            "queueJobs": [
                {
                    "id": j.id,
                    "clipPath": j.clip_path,
                    "state": j.state,
                    "trigger": j.trigger,
                    "retries": j.retries,
                }
                for j in jobs[:50]
            ],
        }

    @app.post("/clips/clear-local")
    def clips_clear_local():
        if store is None:
            raise HTTPException(status_code=503, detail="Store not available")
        cancelled = store.cancel_all_pending()
        purged = store.purge_done_failed()
        deleted = clear_local_clip_files(cfg.state_dir)
        state.queue_depth = store.pending_count()
        state.log(f"Cleared local clips: {deleted} files, {cancelled} queue jobs cancelled")
        return {"deletedFiles": deleted, "cancelledJobs": cancelled, "purgedRows": purged}

    @app.post("/clips/upload-full-source")
    def clips_upload_full_source():
        if store is None:
            raise HTTPException(status_code=503, detail="Store not available")
        source = resolve_file_source(cfg)
        if source is None:
            raise HTTPException(
                status_code=400,
                detail="No local file source configured (RTSP-only). Use wizard MP4 or file:// source.",
            )
        camera_id = cfg.camera_id
        if not camera_id:
            wizard = load_wizard_config()
            if wizard and wizard.sources:
                camera_id = wizard.sources[0].camera_id
        if not camera_id:
            raise HTTPException(status_code=400, detail="No camera ID configured")

        try:
            path, duration = prepare_clip_file(source, cfg.state_dir)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to prepare clip: {exc}") from exc

        store.enqueue(path, camera_id, duration, "manual-full-file")
        state.queue_depth = store.pending_count()
        state.clips_created += 1
        state.log(f"Enqueued full source file ({duration:.1f}s): {source.name}")
        return {"ok": True, "clipPath": path, "durationSec": duration, "cameraId": camera_id}

    # ------------------------------------------------------------------
    # ONVIF endpoints
    # ------------------------------------------------------------------
    @app.get("/onvif/discover")
    def onvif_discover(timeout: float = Query(default=5.0, ge=1.0, le=30.0)):
        """Run WS-Discovery and return all ONVIF cameras found on the LAN."""
        try:
            from .onvif_client import discover
            cameras = discover(timeout=timeout)
            return {
                "count": len(cameras),
                "cameras": [
                    {"ip": c.ip, "xaddr": c.xaddr, "name": c.name, "scopes": c.scopes}
                    for c in cameras
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/onvif/info")
    def onvif_info():
        """Return device info for the camera configured via --onvif-host."""
        if not cfg.onvif_host:
            raise HTTPException(status_code=400, detail="ONVIF not configured (no --onvif-host)")
        try:
            from .onvif_client import OnvifCamera
            cam = OnvifCamera()
            cam.connect(cfg.onvif_host, cfg.onvif_port, cfg.onvif_user, cfg.onvif_pass)
            info = cam.get_device_info()
            return {
                "manufacturer": info.manufacturer,
                "model": info.model,
                "serial": info.serial,
                "firmware": info.firmware,
                "hardware": info.hardware,
                "host": cfg.onvif_host,
                "port": cfg.onvif_port,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/onvif/profiles")
    def onvif_profiles():
        """Return stream profiles for the configured camera."""
        if not cfg.onvif_host:
            raise HTTPException(status_code=400, detail="ONVIF not configured (no --onvif-host)")
        try:
            from .onvif_client import OnvifCamera
            cam = OnvifCamera()
            cam.connect(cfg.onvif_host, cfg.onvif_port, cfg.onvif_user, cfg.onvif_pass)
            profiles = cam.get_profiles()
            return {
                "count": len(profiles),
                "profiles": [
                    {"token": p.token, "name": p.name,
                     "encoding": p.encoding, "width": p.width, "height": p.height}
                    for p in profiles
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/onvif/snapshot")
    def onvif_snapshot(profile: str = Query(default="")):
        """Fetch and return a live JPEG snapshot from the configured camera."""
        if not cfg.onvif_host:
            raise HTTPException(status_code=400, detail="ONVIF not configured (no --onvif-host)")
        try:
            from .onvif_client import OnvifCamera
            cam = OnvifCamera()
            cam.connect(cfg.onvif_host, cfg.onvif_port, cfg.onvif_user, cfg.onvif_pass)
            token = profile or None
            jpeg = cam.fetch_snapshot_bytes(token)
            return Response(content=jpeg, media_type="image/jpeg")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/snapshot")
    def snapshot(camera_id: str):
        """Return a live snapshot from the CapturePipeline's recent frames."""
        frame = state.last_frames.get(camera_id)
        if not frame and len(state.last_frames) == 1:
            # Single-source connector: tolerate a camera-id mismatch between the
            # dashboard GUID and the locally configured source.
            frame = next(iter(state.last_frames.values()))
        if not frame:
            raise HTTPException(status_code=404, detail="No snapshot available yet")
        return Response(content=frame, media_type="image/jpeg")

    # ------------------------------------------------------------------
    # Dashboard HTML
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index():
        onvif_section = ""
        if cfg.onvif_host:
            onvif_section = f"""
            <div class="section">
              <h2>ONVIF Camera</h2>
              <div class="grid" id="onvif-grid"></div>
              <div style="margin-top:.75rem;display:flex;gap:.5rem;flex-wrap:wrap">
                <a class="btn" href="/onvif/snapshot" target="_blank">📷 Live Snapshot</a>
                <a class="btn" href="/onvif/profiles" target="_blank">📋 Profiles</a>
                <a class="btn" href="/onvif/discover" target="_blank">🔍 Discover LAN</a>
              </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ONEVO Connector Admin</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:system-ui,sans-serif;background:#0f1216;color:#e6e6e6;padding:1.5rem}}
    h1{{font-size:1.1rem;font-weight:600;color:#8ab4f8;margin-bottom:1rem}}
    h2{{font-size:.85rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
        color:#888;margin-bottom:.5rem}}
    .section{{background:#171b21;border-radius:8px;padding:1rem;margin-bottom:1rem}}
    .grid{{display:grid;grid-template-columns:180px 1fr;gap:.2rem .75rem;font-size:.85rem}}
    .k{{color:#8ab4f8;font-size:.8rem}}
    .v{{color:#e6e6e6;word-break:break-all}}
    pre{{background:#0f1216;padding:.75rem;border-radius:6px;max-height:300px;overflow:auto;
         font-size:.75rem;line-height:1.4;margin-top:.5rem}}
    .badge{{display:inline-block;padding:.1rem .5rem;border-radius:10px;font-size:.7rem;font-weight:600}}
    .ok{{background:#1a3a2a;color:#5cdb7f}}.warn{{background:#3a2a1a;color:#f0a030}}
    .err{{background:#3a1a1a;color:#f07070}}
    .btn{{display:inline-block;padding:.35rem .75rem;border-radius:6px;font-size:.78rem;
          background:#1e2530;color:#8ab4f8;text-decoration:none;border:1px solid #2a3a50}}
    .btn:hover{{background:#2a3a50}}
    button{{cursor:pointer}}
    .source-types{{display:flex;gap:.5rem;flex-wrap:wrap;margin:.75rem 0}}
    .source-form{{display:none;border-top:1px solid #2a3a50;padding-top:.75rem}}
    .source-form.on{{display:block}}
    .source-row{{display:flex;gap:.5rem;align-items:end;margin:.5rem 0;flex-wrap:wrap}}
    .source-row label{{color:#888;font-size:.72rem;flex:1;min-width:120px}}
    .source-row input{{display:block;width:100%;margin-top:.2rem;background:#0f1216;
      color:#e6e6e6;border:1px solid #2a3a50;border-radius:5px;padding:.45rem}}
    .source-msg{{font-size:.78rem;margin-top:.6rem;color:#8ab4f8}}
    .btn.danger{{border-color:#6a3030;color:#f07070}}
    .btn.primary{{border-color:#3a5080;color:#8ab4f8}}
    .hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem}}
    .hidden{{display:none!important}}
    #tick{{font-size:.7rem;color:#555}}
    .row{{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin-top:.5rem}}
    input[type=number]{{width:4.5rem;padding:.25rem .4rem;border-radius:4px;border:1px solid #2a3a50;
      background:#0f1216;color:#e6e6e6;font-size:.82rem}}
    .hint{{font-size:.75rem;color:#888;margin-top:.35rem}}
    #action-msg{{font-size:.78rem;color:#5cdb7f;margin-top:.35rem}}
    #action-err{{font-size:.78rem;color:#f07070;margin-top:.35rem}}
  </style>
</head>
<body>
  <div class="hdr">
    <h1>🎥 ONEVO Local Connector</h1>
    <span id="tick">—</span>
  </div>

  <div class="section hidden" id="alert-banner">
    <h2 id="alert-title" style="color:#f07070"></h2>
    <p id="alert-text" style="font-size:.85rem;line-height:1.45;margin-bottom:.75rem"></p>
    <a class="btn hidden" id="alert-setup-link" href="/setup">Retry setup</a>
  </div>

  <div class="section">
    <h2>Runtime</h2>
    <div class="grid" id="runtime-grid"></div>
  </div>

  <div class="section">
    <h2>Actions</h2>
    <p class="hint">Pause stops new motion clips. To fully stop the Windows service use Services.msc or <code>net stop ONEVO-Connector</code>.</p>
    <div class="row">
      <button class="btn" id="btn-pause" onclick="pauseCapture()">Pause monitoring</button>
      <button class="btn" id="btn-resume" onclick="resumeCapture()">Resume monitoring</button>
      <button class="btn" onclick="triggerNow()">Cut clip now</button>
      <button class="btn primary" onclick="uploadFullSource()">Upload full source file</button>
    </div>
    <div id="action-msg"></div>
    <div id="action-err"></div>
  </div>

  <div class="section">
    <h2>Clip window (motion cuts)</h2>
    <p class="hint">Each motion clip ≈ pre + post seconds. Use 30/30 for theft MP4 demos.</p>
    <div class="row">
      <label class="k">Pre-roll (s)</label>
      <input type="number" id="preSec" min="1" max="120" step="1" />
      <label class="k">Post-roll (s)</label>
      <input type="number" id="postSec" min="1" max="120" step="1" />
      <label class="k">Cooldown (s)</label>
      <input type="number" id="coolSec" min="5" max="600" step="1" />
      <button class="btn" onclick="saveClipSettings()">Save</button>
    </div>
    <p class="hint" id="clip-window-hint"></p>
  </div>

  <div class="section">
    <h2>Local clips</h2>
    <p class="hint" id="local-clips-summary">—</p>
    <div class="row">
      <button class="btn danger" onclick="clearLocalClips()">Clear local clips</button>
    </div>
  </div>

  {onvif_section}

  <div class="section">
    <h2>Camera / Video Sources</h2>
    <div id="saved-sources" class="v">Loading configured sources...</div>
    <div class="source-types">
      <button class="btn" type="button" onclick="chooseSource('rtsp')">+ Add RTSP Camera</button>
      <button class="btn" type="button" onclick="chooseSource('onvif')">+ Add ONVIF Camera</button>
      <button class="btn" type="button" onclick="chooseSource('video')">+ Add Local MP4 Video</button>
    </div>
    <form id="source-form" class="source-form">
      <input type="hidden" id="source-type" name="source_type">
      <div id="source-rows"></div>
      <button class="btn" type="button" id="add-row">+ Add another</button>
      <button class="btn" type="submit">Save and start monitoring</button>
      <div class="source-msg" id="source-msg"></div>
    </form>
  </div>

  <div class="section">
    <h2>Logs</h2>
    <pre id="logs"></pre>
  </div>

  <script>
    const RUNTIME_FIELDS = [
      ['connectorId','Connector ID'],['cameraId','Camera ID'],['source','Source'],
      ['capturing','Capturing'],['capturePaused','Paused'],['clipsCreated','Clips created'],
      ['uploadsOk','Uploads OK'],['uploadsFailed','Uploads failed'],
      ['queueDepth','Queue depth'],['diskFreePct','Disk free %'],
      ['rtspReconnects','RTSP reconnects'],['degradedReason','Degraded'],
      ['uptimeSec','Uptime (s)'],
    ];
    const ONVIF_FIELDS = [
      ['cameraManufacturer','Manufacturer'],['cameraModel','Model'],
      ['cameraSerial','Serial'],['cameraFirmware','Firmware'],
    ];

    function badge(v) {{
      if (v === true || v === 'true') return '<span class="badge ok">YES</span>';
      if (v === false || v === 'false') return '<span class="badge warn">NO</span>';
      if (v === null || v === undefined || v === '') return '<span style="color:#555">—</span>';
      return String(v);
    }}

    let selectedSourceType = '';
    function sourceRow(type, index) {{
      const removeButton = index > 1
        ? '<button class="btn remove-source" type="button">Remove</button>'
        : '';
      if (type === 'rtsp') return `<div class="source-row">
        <label>RTSP URL ${{index}}<input class="rtsp-url" placeholder="rtsp://..."></label>
        ${{removeButton}}</div>`;
      if (type === 'onvif') return `<div class="source-row onvif-row">
        <label>Name<input class="onvif-name" value="ONVIF Camera ${{index}}"></label>
        <label>Host / IP<input class="onvif-host" placeholder="192.168.1.20"></label>
        <label>Port<input class="onvif-port" value="80" type="number" min="1" max="65535"></label>
        <label>Username<input class="onvif-user" value="admin"></label>
        <label>Password<input class="onvif-pass" type="password"></label>
        ${{removeButton}}</div>`;
      return `<div class="source-row">
        <label>MP4 video ${{index}}<input class="video-file" type="file" accept=".mp4,video/mp4"></label>
        ${{removeButton}}</div>`;
    }}
    function addSourceRow() {{
      const rows = document.getElementById('source-rows');
      rows.insertAdjacentHTML('beforeend', sourceRow(selectedSourceType, rows.children.length + 1));
    }}
    function chooseSource(type) {{
      selectedSourceType = type;
      document.getElementById('source-type').value = type;
      document.getElementById('source-rows').innerHTML = '';
      document.getElementById('source-form').classList.add('on');
      document.getElementById('source-msg').textContent = '';
      addSourceRow();
    }}
    document.getElementById('add-row').onclick = addSourceRow;
    document.getElementById('source-rows').onclick = event => {{
      if (event.target.classList.contains('remove-source')) {{
        const rows = document.getElementById('source-rows');
        if (rows.children.length > 1) event.target.closest('.source-row').remove();
      }}
    }};
    async function loadSources() {{
      const data = await (await fetch('/sources')).json();
      const el = document.getElementById('saved-sources');
      if (!data.sources.length) {{
        el.textContent = 'No sources configured. Add them here when ready.';
        return;
      }}
      el.innerHTML = '';
      data.sources.forEach((source, index) => {{
        const row = document.createElement('div');
        row.className = 'source-row';
        const text = document.createElement('span');
        text.textContent = `${{source.name}} (${{source.type}}): ${{source.value}}`;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn';
        remove.textContent = 'Remove';
        remove.onclick = () => removeSavedSource(index);
        row.append(text, remove);
        el.appendChild(row);
      }});
    }}
    async function removeSavedSource(index) {{
      if (!confirm('Remove this camera/video source?')) return;
      const response = await fetch(`/sources/${{index}}`, {{method:'DELETE'}});
      const data = await response.json();
      const msg = document.getElementById('source-msg');
      if (!response.ok) {{
        msg.textContent = data.detail || 'Could not remove source';
        return;
      }}
      msg.textContent = data.pending
        ? 'Source removed locally. Backend sync is pending.'
        : 'Source removed.';
      await loadSources();
    }}
    document.getElementById('source-form').onsubmit = async event => {{
      event.preventDefault();
      const fd = new FormData();
      fd.append('source_type', selectedSourceType);
      if (selectedSourceType === 'rtsp') {{
        fd.append('rtsp_text', [...document.querySelectorAll('.rtsp-url')]
          .map(input => input.value.trim()).filter(Boolean).join('\\n'));
      }} else if (selectedSourceType === 'onvif') {{
        fd.append('onvif_json', JSON.stringify([...document.querySelectorAll('.onvif-row')].map(row => ({{
          name: row.querySelector('.onvif-name').value,
          host: row.querySelector('.onvif-host').value,
          port: row.querySelector('.onvif-port').value,
          username: row.querySelector('.onvif-user').value,
          password: row.querySelector('.onvif-pass').value
        }}))));
      }} else {{
        document.querySelectorAll('.video-file').forEach(input => {{
          if (input.files[0]) fd.append('files', input.files[0]);
        }});
      }}
      const msg = document.getElementById('source-msg');
      msg.textContent = 'Saving sources...';
      try {{
        const response = await fetch('/sources', {{method:'POST', body:fd}});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not add sources');
        msg.textContent = data.pending
          ? `Saved ${{data.added}} source(s). Backend activation is pending.`
          : `Added ${{data.added}} source(s). Monitoring will start shortly.`;
        await loadSources();
      }} catch (error) {{
        msg.textContent = error.message;
      }}
    }};
    function classifyAlert(s) {{
      const reason = s.degradedReason || '';
      const logs = (s.logs || []).join('\\n');
      const uploadStuck = (s.queueDepth > 0 || s.uploadsFailed > 0) &&
        /ConnectTimeoutError|:9000|Upload FAILED|Upload error/i.test(logs);
      if (reason.startsWith('disk_critical') || reason.startsWith('disk_warning')) {{
        return {{
          title: 'Low disk space',
          text: reason + '. Free space on the Windows drive (target >20% free). '
            + 'Stop the service and clear C:\\\\ProgramData\\\\ONEVO\\\\Connector\\\\data\\\\clips if test clips piled up.',
          setup: false,
          style: 'border-color:#5a4030;background:#2a2218',
        }};
      }}
      if (uploadStuck) {{
        return {{
          title: 'Clip upload blocked',
          text: 'Motion clips are queued but cannot reach cloud storage (often port 9000 / MinIO). '
            + 'Ask your ONEVO admin to open storage access from shop PCs, then restart this service.',
          setup: false,
          style: 'border-color:#5a3030;background:#2a1818',
        }};
      }}
      if (reason && (/setup code|activation|configured yet/i.test(reason))) {{
        return {{
          title: 'Setup required',
          text: reason,
          setup: true,
          style: 'border-color:#5a3030;background:#2a1818',
        }};
      }}
      if (reason) {{
        return {{ title: 'Connector degraded', text: reason, setup: false,
          style: 'border-color:#5a4030;background:#2a2218' }};
      }}
      return null;
    }}

    function showActionMsg(msg, isErr) {{
      document.getElementById('action-msg').textContent = isErr ? '' : msg;
      document.getElementById('action-err').textContent = isErr ? msg : '';
    }}

    async function postJson(url) {{
      const r = await fetch(url, {{ method: 'POST' }});
      const data = await r.json().catch(() => ({{}}));
      if (!r.ok) throw new Error(data.detail || data.error || r.statusText);
      return data;
    }}

    async function pauseCapture() {{
      try {{ await postJson('/capture/pause'); showActionMsg('Monitoring paused'); tick(); }}
      catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function resumeCapture() {{
      try {{ await postJson('/capture/resume'); showActionMsg('Monitoring resumed'); tick(); }}
      catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function triggerNow() {{
      try {{ await postJson('/capture/trigger-now'); showActionMsg('Manual clip trigger sent'); }}
      catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function uploadFullSource() {{
      if (!confirm('Upload the entire configured MP4 as one clip (no motion cutting)?')) return;
      try {{
        const d = await postJson('/clips/upload-full-source');
        showActionMsg('Full file queued (' + d.durationSec.toFixed(1) + 's)');
        tick();
      }} catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function clearLocalClips() {{
      if (!confirm('Delete all local clip files and cancel pending uploads?')) return;
      try {{
        const d = await postJson('/clips/clear-local');
        showActionMsg('Deleted ' + d.deletedFiles + ' files, cancelled ' + d.cancelledJobs + ' jobs');
        tick();
      }} catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function loadClipSettings() {{
      try {{
        const s = await (await fetch('/capture/settings')).json();
        document.getElementById('preSec').value = s.pre_seconds;
        document.getElementById('postSec').value = s.post_seconds;
        document.getElementById('coolSec').value = s.cooldown_seconds;
        document.getElementById('clip-window-hint').textContent =
          'Each motion clip ≈ ' + s.approxClipSeconds + 's total';
      }} catch(e) {{}}
    }}
    async function saveClipSettings() {{
      try {{
        const body = {{
          pre_seconds: parseFloat(document.getElementById('preSec').value),
          post_seconds: parseFloat(document.getElementById('postSec').value),
          cooldown_seconds: parseFloat(document.getElementById('coolSec').value),
        }};
        const r = await fetch('/capture/settings', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(body),
        }});
        const s = await r.json();
        if (!r.ok) throw new Error(s.detail || 'Save failed');
        showActionMsg('Clip settings saved');
        document.getElementById('clip-window-hint').textContent =
          'Each motion clip ≈ ' + s.approxClipSeconds + 's total';
      }} catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function refreshLocalClips() {{
      try {{
        const d = await (await fetch('/clips/local')).json();
        const el = document.getElementById('local-clips-summary');
        if (el) el.textContent = d.fileCount + ' local file(s), ' + d.queuePending + ' queued for upload';
      }} catch(e) {{}}
    }}

    async function tick() {{
      try {{
        const s = await (await fetch('/status')).json();
        const rg = document.getElementById('runtime-grid');
        if (rg) rg.innerHTML = RUNTIME_FIELDS.map(([k,l]) =>
          `<div class="k">${{l}}</div><div class="v">${{badge(s[k])}}</div>`).join('');

        const og = document.getElementById('onvif-grid');
        if (og) og.innerHTML = ONVIF_FIELDS.map(([k,l]) =>
          `<div class="k">${{l}}</div><div class="v">${{badge(s[k])}}</div>`).join('');

        const logs = document.getElementById('logs');
        if (logs) {{ logs.textContent = (s.logs||[]).join('\\n'); logs.scrollTop = logs.scrollHeight; }}
        const banner = document.getElementById('alert-banner');
        const alertTitle = document.getElementById('alert-title');
        const alertText = document.getElementById('alert-text');
        const setupLink = document.getElementById('alert-setup-link');
        if (banner && alertText) {{
          const alert = classifyAlert(s);
          if (alert) {{
            banner.classList.remove('hidden');
            banner.style.cssText = alert.style;
            if (alertTitle) alertTitle.textContent = alert.title;
            alertText.textContent = alert.text;
            if (setupLink) setupLink.classList.toggle('hidden', !alert.setup);
          }} else {{
            banner.classList.add('hidden');
          }}
        }}
        document.getElementById('tick').textContent = 'updated ' + new Date().toLocaleTimeString();
        refreshLocalClips();
      }} catch(e) {{ document.getElementById('tick').textContent = 'fetch error'; }}
    }}
    loadClipSettings();
    setInterval(tick, 1500); tick();loadSources();
  </script>
</body>
</html>"""

    return app


def start_admin(
    state: RuntimeState,
    cfg: "Config",
    port: int,
    store: "LocalStore | None" = None,
    enable_setup_wizard: bool = False,
    on_wizard_configured: Callable | None = None,
) -> threading.Thread:
    app = build_app(
        state,
        cfg,
        store=store,
        enable_setup_wizard=enable_setup_wizard,
        on_wizard_configured=on_wizard_configured,
    )
    if enable_setup_wizard and store is not None:
        from .wizard import WIZARD_ROUTE_PREFIX, attach_wizard_routes

        attach_wizard_routes(
            app,
            state,
            cfg,
            store,
            route_prefix=WIZARD_ROUTE_PREFIX,
            on_configured=on_wizard_configured,
        )
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return t

