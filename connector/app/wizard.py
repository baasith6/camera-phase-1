"""First-run setup wizard (local FastAPI UI).

Shop owners enter a dashboard-generated setup code, then connect one or more
RTSP cameras and/or upload a local test MP4. Config is persisted under
ProgramData and the connector service continues monitoring afterwards.
"""
from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .backend_client import BackendClient
from .paths import CameraSource, WizardConfig, load_wizard_config, media_dir, save_wizard_config
from .provisioning import claim_setup, complete_setup, provision_sources

if TYPE_CHECKING:
    from .config import Config
    from .runtime import RuntimeState
    from .store import LocalStore


WIZARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ONEVO Connector Setup</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root {
      --bg: #0e141b;
      --panel: #161e28;
      --line: #2a3644;
      --text: #e8eef5;
      --muted: #8b9aab;
      --accent: #3d9cf0;
      --accent-dim: #1a3a5c;
      --ok: #3ecf8e;
      --err: #f07178;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Segoe UI", "Candara", sans-serif;
      background:
        radial-gradient(1200px 600px at 10% -10%, #1a2d44 0%, transparent 55%),
        radial-gradient(900px 500px at 100% 0%, #1a2430 0%, transparent 50%),
        var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 2rem 1rem 3rem;
    }
    .wrap { max-width: 640px; margin: 0 auto; }
    .brand {
      font-size: 1.65rem; font-weight: 700; letter-spacing: .04em;
      color: var(--accent); margin-bottom: .35rem;
    }
    .sub { color: var(--muted); font-size: .95rem; margin-bottom: 1.5rem; line-height: 1.45; }
    .steps { display: flex; gap: .5rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
    .step-pill {
      font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
      padding: .35rem .65rem; border: 1px solid var(--line); border-radius: 4px; color: var(--muted);
    }
    .step-pill.on { border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }
    .panel {
      background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 1.25rem 1.35rem; margin-bottom: 1rem;
    }
    h2 { font-size: 1.05rem; margin-bottom: .75rem; font-weight: 600; }
    label { display: block; font-size: .78rem; color: var(--muted); margin: .65rem 0 .25rem; }
    input, textarea {
      width: 100%; background: #0e141b; border: 1px solid var(--line); color: var(--text);
      border-radius: 6px; padding: .55rem .7rem; font-size: .9rem;
    }
    input:focus, textarea:focus { outline: none; border-color: var(--accent); }
    textarea { min-height: 110px; resize: vertical; font-family: ui-monospace, Consolas, monospace; font-size: .82rem; }
    .hint { font-size: .78rem; color: var(--muted); margin-top: .4rem; line-height: 1.4; }
    .row { display: flex; gap: .6rem; flex-wrap: wrap; margin-top: 1rem; }
    button, .btn {
      appearance: none; border: 1px solid var(--accent); background: var(--accent);
      color: #061018; font-weight: 600; border-radius: 6px; padding: .55rem 1rem;
      cursor: pointer; font-size: .88rem;
    }
    button.ghost { background: transparent; color: var(--accent); }
    button:disabled { opacity: .45; cursor: not-allowed; }
    .msg { margin-top: .85rem; font-size: .85rem; padding: .55rem .7rem; border-radius: 6px; display: none; }
    .msg.ok { display: block; background: rgba(62,207,142,.12); color: var(--ok); border: 1px solid rgba(62,207,142,.35); }
    .msg.err { display: block; background: rgba(240,113,120,.12); color: var(--err); border: 1px solid rgba(240,113,120,.35); }
    .hidden { display: none !important; }
    .status-line { font-size: .85rem; color: var(--muted); }
    .status-line strong { color: var(--ok); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">ONEVO</div>
    <p class="sub">Local Connector setup — link this PC to your store, then add camera streams or a test video.</p>
    <div class="steps">
      <span class="step-pill" id="p1">1 · Setup code</span>
      <span class="step-pill" id="p2">2 · Sources</span>
      <span class="step-pill" id="p3">3 · Done</span>
    </div>

    <div class="panel" id="panel-claim">
      <h2>Enter setup code</h2>
      <p class="hint">Generate a code on the dashboard <em>Setup &amp; Zones</em> page, then paste it here.</p>
      <label>Setup code</label>
      <input id="setupCode" placeholder="XXXX-XXXX" autocomplete="off" />
      <label>Connector name</label>
      <input id="connName" value="edge-connector-1" />
      <div class="row">
        <button id="btnClaim" type="button">Connect store</button>
      </div>
      <div class="msg" id="claimMsg"></div>
    </div>

    <div class="panel hidden" id="panel-sources">
      <h2>Camera sources</h2>
      <p class="hint">Add one RTSP URL per line (single or multiple cameras), and/or upload a local MP4 for continuous test monitoring.</p>
      <label>RTSP links</label>
      <textarea id="rtspList" placeholder="rtsp://user:pass@192.168.1.64:554/Streaming/Channels/101&#10;rtsp://user:pass@192.168.1.65:554/stream1"></textarea>
      <label>Test video (MP4)</label>
      <input id="mp4File" type="file" accept="video/mp4,.mp4" />
      <label style="display:flex;align-items:center;gap:.5rem">
        <input id="loopFile" type="checkbox" checked style="width:auto" />
        Loop uploaded test video continuously
      </label>
      <div class="row">
        <button class="ghost" type="button" id="btnBack">Back</button>
        <button type="button" id="btnSave">Save &amp; start monitoring</button>
      </div>
      <div class="msg" id="srcMsg"></div>
    </div>

    <div class="panel hidden" id="panel-done">
      <h2>Setup complete</h2>
      <p class="status-line" id="doneText">Connector is configured. Motion events will upload to ONEVO automatically.</p>
      <div class="row">
        <a class="btn" href="/">Open status dashboard</a>
      </div>
    </div>
  </div>
  <script>
    const pills = [document.getElementById('p1'), document.getElementById('p2'), document.getElementById('p3')];
    function setStep(n) {
      pills.forEach((p, i) => p.classList.toggle('on', i === n));
      document.getElementById('panel-claim').classList.toggle('hidden', n !== 0);
      document.getElementById('panel-sources').classList.toggle('hidden', n !== 1);
      document.getElementById('panel-done').classList.toggle('hidden', n !== 2);
    }
    function show(el, ok, text) {
      el.className = 'msg ' + (ok ? 'ok' : 'err');
      el.textContent = text;
    }
    async function boot() {
      const s = await (await fetch('/wizard/status')).json();
      if (s.setupComplete) { setStep(2); return; }
      if (s.claimed) { setStep(1); return; }
      setStep(0);
    }
    document.getElementById('btnClaim').onclick = async () => {
      const msg = document.getElementById('claimMsg');
      const code = document.getElementById('setupCode').value.trim();
      const name = document.getElementById('connName').value.trim() || 'edge-connector-1';
      if (!code) { show(msg, false, 'Enter a setup code'); return; }
      try {
        const r = await fetch('/wizard/claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ setupCode: code, name })
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || data.error || 'Claim failed');
        show(msg, true, 'Linked to store. Next: add cameras.');
        setTimeout(() => setStep(1), 500);
      } catch (e) { show(msg, false, e.message || String(e)); }
    };
    document.getElementById('btnBack').onclick = () => setStep(0);
    document.getElementById('btnSave').onclick = async () => {
      const msg = document.getElementById('srcMsg');
      const rtsp = document.getElementById('rtspList').value;
      const fileInput = document.getElementById('mp4File');
      const fd = new FormData();
      fd.append('rtsp_text', rtsp);
      if (fileInput.files && fileInput.files[0]) fd.append('file', fileInput.files[0]);
      fd.append('loop_file', document.getElementById('loopFile').checked ? 'true' : 'false');
      try {
        const r = await fetch('/wizard/sources', { method: 'POST', body: fd });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || data.error || 'Save failed');
        document.getElementById('doneText').textContent =
          `Monitoring ${data.cameraCount} source(s). Clips upload on motion.`;
        setStep(2);
      } catch (e) { show(msg, false, e.message || String(e)); }
    };
    boot();
  </script>
</body>
</html>
"""


def build_wizard_app(
    state: "RuntimeState",
    cfg: "Config",
    store: "LocalStore",
    on_configured=None,
) -> FastAPI:
    app = FastAPI(title="ONEVO Connector Setup Wizard")
    client = BackendClient(cfg.backend_url)

    def _reload_creds() -> bool:
        cid = store.get_cred("connector_id")
        key = store.get_cred("api_key")
        if cid and key:
            client.set_credentials(cid, key)
            return True
        return False

    @app.get("/", response_class=HTMLResponse)
    def index():
        return WIZARD_HTML

    @app.get("/wizard/status")
    def wizard_status():
        w = load_wizard_config()
        claimed = bool(store.get_cred("connector_id") and store.get_cred("api_key"))
        return {
            "setupComplete": bool(w and w.setup_complete),
            "claimed": claimed,
            "backendUrl": cfg.backend_url,
            "version": cfg.version,
        }

    @app.post("/wizard/claim")
    def wizard_claim(body: dict):
        code = (body.get("setupCode") or body.get("setup_code") or "").strip()
        name = (body.get("name") or cfg.connector_name or "edge-connector-1").strip()
        if not code:
            raise HTTPException(400, "setupCode is required")
        try:
            w = load_wizard_config() or WizardConfig()
            w.setup_code = code
            w.connector_name = name
            cid, store_id = claim_setup(client, store, w, cfg.version)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc
        state.connector_id = cid
        state.log(f"Wizard: claimed setup code → connector {cid} store {store_id}")
        return {"ok": True, "connectorId": cid, "storeId": store_id}

    @app.post("/wizard/sources")
    async def wizard_sources(
        rtsp_text: str = Form(default=""),
        file: UploadFile | None = File(default=None),
        loop_file: bool = Form(default=True),
    ):
        if not _reload_creds():
            raise HTTPException(400, "Claim a setup code first")

        sources: list[CameraSource] = []
        lines = [ln.strip() for ln in (rtsp_text or "").splitlines() if ln.strip()]
        for i, url in enumerate(lines, start=1):
            if not url.lower().startswith("rtsp://"):
                raise HTTPException(400, f"Invalid RTSP URL (line {i}): must start with rtsp://")
            sources.append(CameraSource(name=f"Camera {i}", rtsp_url=url, loop=False))

        if file is not None and file.filename:
            dest = media_dir() / "test-upload.mp4"
            with dest.open("wb") as out:
                shutil.copyfileobj(file.file, out)
            sources.append(
                CameraSource(
                    name="Test Video",
                    source_file=str(dest),
                    loop=loop_file,
                )
            )

        if not sources:
            raise HTTPException(400, "Add at least one RTSP URL or upload an MP4")

        try:
            created = provision_sources(client, sources, state)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Failed to configure cameras: {exc}") from exc

        w = load_wizard_config() or WizardConfig()
        complete_setup(w, created)
        state.log(f"Wizard: configured {len(created)} source(s)")

        if on_configured:
            try:
                on_configured(w)
            except Exception as exc:  # noqa: BLE001
                state.log(f"WARNING: on_configured hook failed: {exc}")

        return {"ok": True, "cameraCount": len(created)}

    return app


def start_wizard(
    state: "RuntimeState",
    cfg: "Config",
    store: "LocalStore",
    port: int,
    on_configured=None,
) -> threading.Thread:
    app = build_wizard_app(state, cfg, store, on_configured=on_configured)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return t


def open_wizard_browser(port: int) -> None:
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{port}/")



