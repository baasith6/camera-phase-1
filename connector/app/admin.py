"""Local admin UI/API for the connector (installer view).

Endpoints:
  GET  /           — HTML status dashboard
  GET  /status     — JSON runtime snapshot
  GET  /health     — {"ok": true}
  GET  /onvif/discover   — WS-Discovery scan; returns list of cameras on LAN
  GET  /onvif/info       — device info for the currently connected camera
  GET  /onvif/profiles   — stream profiles for the currently connected camera
  GET  /onvif/snapshot   — live JPEG snapshot (returns image/jpeg)
"""
import threading
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .runtime import RuntimeState

if TYPE_CHECKING:
    from .config import Config


def build_app(state: RuntimeState, cfg: "Config") -> FastAPI:
    app = FastAPI(title="ONEVO Connector Admin")

    @app.get("/status")
    def status():
        return state.snapshot()

    @app.get("/health")
    def health():
        return {"ok": True}

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
    .hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem}}
    #tick{{font-size:.7rem;color:#555}}
  </style>
</head>
<body>
  <div class="hdr">
    <h1>🎥 ONEVO Local Connector</h1>
    <span id="tick">—</span>
  </div>

  <div class="section">
    <h2>Runtime</h2>
    <div class="grid" id="runtime-grid"></div>
  </div>

  {onvif_section}

  <div class="section">
    <h2>Logs</h2>
    <pre id="logs"></pre>
  </div>

  <script>
    const RUNTIME_FIELDS = [
      ['connectorId','Connector ID'],['cameraId','Camera ID'],['source','Source'],
      ['capturing','Capturing'],['clipsCreated','Clips created'],
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
        document.getElementById('tick').textContent = 'updated ' + new Date().toLocaleTimeString();
      }} catch(e) {{ document.getElementById('tick').textContent = 'fetch error'; }}
    }}
    setInterval(tick, 1500); tick();
  </script>
</body>
</html>"""

    return app


def start_admin(state: RuntimeState, cfg: "Config", port: int) -> threading.Thread:
    app = build_app(state, cfg)
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return t

