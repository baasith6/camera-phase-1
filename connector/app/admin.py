"""Local admin UI/API for the connector (installer view)."""
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .runtime import RuntimeState


def build_app(state: RuntimeState) -> FastAPI:
    app = FastAPI(title="ONEVO Connector Admin")

    @app.get("/status")
    def status():
        return state.snapshot()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return """
        <html><head><title>ONEVO Connector</title>
        <style>
          body{font-family:system-ui,sans-serif;margin:2rem;background:#0f1216;color:#e6e6e6}
          h1{font-size:1.2rem} .k{color:#8ab4f8}
          pre{background:#171b21;padding:1rem;border-radius:8px;max-height:340px;overflow:auto}
          .grid{display:grid;grid-template-columns:180px 1fr;gap:.25rem .75rem;max-width:560px}
        </style></head>
        <body>
          <h1>ONEVO Local Connector</h1>
          <div class="grid" id="g"></div>
          <h3>Logs</h3><pre id="logs"></pre>
          <script>
            async function tick(){
              const s = await (await fetch('/status')).json();
              const g = document.getElementById('g');
              const fields = ['connectorId','cameraId','source','capturing','clipsCreated',
                'uploadsOk','uploadsFailed','queueDepth','diskFreePct','degradedReason','uptimeSec'];
              g.innerHTML = fields.map(f=>`<div class="k">${f}</div><div>${s[f]}</div>`).join('');
              document.getElementById('logs').textContent = (s.logs||[]).join('\\n');
            }
            setInterval(tick, 1500); tick();
          </script>
        </body></html>
        """

    return app


def start_admin(state: RuntimeState, port: int) -> threading.Thread:
    app = build_app(state)
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return t
