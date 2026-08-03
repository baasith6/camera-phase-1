"""First-run setup wizard (local FastAPI UI).

Shop owners enter a dashboard-generated setup code, then connect one or more
RTSP cameras and/or upload a local test MP4. Config is persisted under
ProgramData and the connector service continues monitoring afterwards.
"""
from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from .backend_client import BackendClient
from .capture import validate_rtsp_stream
from .paths import (
    CameraSource,
    WizardConfig,
    default_state_dir,
    load_wizard_config,
    media_dir,
    save_wizard_config,
)
from .provisioning import complete_setup, provision_sources, source_key_for

if TYPE_CHECKING:
    from .config import Config
    from .runtime import RuntimeState
    from .store import LocalStore


def parse_rtsp_urls(rtsp_text: str) -> list[str]:
    """Parse RTSP URLs from newline- or semicolon-separated text."""
    return [
        value.strip()
        for value in rtsp_text.replace("\r", "\n").replace(";", "\n").splitlines()
        if value.strip()
    ]


WIZARD_ROUTE_PREFIX = "/setup"


class WizardZoneBody(BaseModel):
    zoneId: str | None = None
    name: str
    zoneType: str
    polygon: list[list[float]]


def wizard_page_html(route_prefix: str = "") -> str:
    """HTML for the setup wizard; route_prefix is '' for standalone or '/setup' when mounted."""
    prefix = route_prefix.rstrip("/")
    base_href = f"{prefix}/" if prefix else "/"
    html = WIZARD_HTML.replace("__WIZARD_BASE__", base_href)
    if prefix:
        html = html.replace("/wizard/", f"{prefix}/wizard/")
    return html


WIZARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ONEVO Connector Setup</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <base href="__WIZARD_BASE__">
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
    .wrap { max-width: 1040px; margin: 0 auto; }
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
    .zone-layout { display:grid; grid-template-columns:220px 1fr; gap:1rem; }
    .zone-list button { width:100%; margin:.25rem 0; text-align:left; }
    canvas { width:100%; max-width:800px; background:#080b12; border:1px solid var(--line); border-radius:8px; cursor:crosshair; touch-action:none; }
    @media(max-width:700px) { .zone-layout { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">ONEVO</div>
    <p class="sub">Local Connector camera setup — add sources, draw zones, and keep them synchronized with ONEVO.</p>
    <div class="steps">
      <span class="step-pill" id="p1">1 · Sources</span>
      <span class="step-pill" id="p2">2 · Zones</span>
      <span class="step-pill" id="p3">3 · Done</span>
    </div>

    <div class="panel hidden" id="panel-zones">
      <h2>Set camera zones</h2>
      <p class="hint">Choose a camera, draw around the monitoring area, then release. Drag a yellow handle to reshape it, or drag inside the zone to move it. Every saved zone is immediately shared with the ONEVO dashboard.</p>
      <label>Camera</label><select id="zoneCamera"></select>
      <div class="zone-layout">
        <div>
          <label>Saved zones</label><div id="zoneList" class="zone-list"></div>
          <button class="ghost" id="newZone" type="button">+ New zone</button>
        </div>
        <div>
          <canvas id="zoneCanvas" width="800" height="450"></canvas>
          <label>Zone name</label><input id="zoneName" placeholder="High-value shelf" />
          <label>Zone type</label>
          <select id="zoneType">
            <option>Shelf</option><option>HighValue</option><option>Checkout</option>
            <option>Exit</option><option>BlindSpot</option>
          </select>
          <div class="row">
            <button class="ghost" id="refreshFrame" type="button">Refresh frame</button>
            <button class="ghost" id="undoPoint" type="button">Undo point</button>
            <button class="ghost" id="clearZone" type="button">Clear</button>
            <button id="saveZone" type="button">Save zone</button>
            <button class="ghost hidden" id="deleteZone" type="button">Delete</button>
          </div>
          <div class="msg" id="zoneMsg"></div>
        </div>
      </div>
      <div class="row" id="finish-zones-row"><button id="finishZones" type="button">Finish setup</button></div>
    </div>

    <div class="panel" id="panel-sources">
      <h2>Camera sources</h2>
      <p class="hint">Add one RTSP URL per line (single or multiple cameras), and/or upload one or more local MP4s for continuous test monitoring.</p>
      <label>RTSP links</label>
      <textarea id="rtspList" placeholder="rtsp://user:pass@192.168.1.64:554/Streaming/Channels/101&#10;rtsp://user:pass@192.168.1.65:554/stream1"></textarea>
      <label>ONVIF camera (optional)</label>
      <div style="display:grid;grid-template-columns:2fr .7fr 1fr 1fr;gap:.5rem">
        <input id="onvifHost" placeholder="Camera IP / host" />
        <input id="onvifPort" type="number" value="80" min="1" max="65535" placeholder="Port" />
        <input id="onvifUser" placeholder="Username" value="admin" />
        <input id="onvifPass" type="password" placeholder="Password" />
      </div>
      <p class="hint">ONEVO will retrieve the RTSP stream from this ONVIF camera automatically.</p>
      <label>Test videos (MP4)</label>
      <input id="mp4File" type="file" accept="video/mp4,.mp4" multiple />
      <label style="display:flex;align-items:center;gap:.5rem">
        <input id="loopFile" type="checkbox" checked style="width:auto" />
        Loop uploaded test video continuously
      </label>
      <div class="row">
        <button type="button" id="btnSave">Save &amp; continue to zones</button>
      </div>
      <div class="msg" id="srcMsg"></div>
    </div>

    <div class="panel hidden" id="panel-done">
      <h2>Setup complete</h2>
      <p class="status-line" id="doneText">Connector is configured. Motion events will upload to ONEVO automatically.</p>
    </div>
  </div>
  <script>
    const params = new URLSearchParams(window.location.search);
    const embedded = params.get('embedded') === '1';
    const requestedZones = params.get('step') === 'zones';
    const pills = [document.getElementById('p1'), document.getElementById('p2'), document.getElementById('p3')];
    function setStep(n) {
      pills.forEach((p, i) => p.classList.toggle('on', i === n));
      document.getElementById('panel-sources').classList.toggle('hidden', n !== 0);
      document.getElementById('panel-zones').classList.toggle('hidden', n !== 1);
      document.getElementById('panel-done').classList.toggle('hidden', n !== 2);
    }
    function show(el, ok, text) {
      el.className = 'msg ' + (ok ? 'ok' : 'err');
      el.textContent = text;
    }
    async function boot() {
      const s = await (await fetch('wizard/status')).json();
      if (s.readyForZones && s.cameras && s.cameras.length) {
        initZones(s.cameras); setStep(1); return;
      }
      setStep(0);
      const save = document.getElementById('btnSave');
      const msg = document.getElementById('srcMsg');
      if (s.claimed && s.hasConfiguredSources) {
        save.disabled = true;
        show(msg, !s.activationError,
          s.activationError || (
            requestedZones
              ? 'Preparing the camera selected in the installer. The zone editor will open automatically…'
              : 'Preparing the camera selected in the installer. Zone setup will open automatically…'
          ));
        if (!s.activationError) setTimeout(boot, 1500);
        return;
      }
      if (s.claimed) {
        save.disabled = false;
        return;
      }
      save.disabled = true;
      show(msg, !s.activationError,
        s.activationError ||
        'ONEVO is completing the one-time installer pairing. This page will continue automatically…');
      if (!s.activationError) setTimeout(boot, 1500);
    }
    document.getElementById('btnSave').onclick = async () => {
      const msg = document.getElementById('srcMsg');
      const rtsp = document.getElementById('rtspList').value;
      const fileInput = document.getElementById('mp4File');
      const fd = new FormData();
      fd.append('rtsp_text', rtsp);
      fd.append('onvif_host', document.getElementById('onvifHost').value);
      fd.append('onvif_port', document.getElementById('onvifPort').value || '80');
      fd.append('onvif_user', document.getElementById('onvifUser').value || 'admin');
      fd.append('onvif_pass', document.getElementById('onvifPass').value);
      if (fileInput.files) [...fileInput.files].forEach(file => fd.append('files', file));
      fd.append('loop_file', document.getElementById('loopFile').checked ? 'true' : 'false');
      try {
        const r = await fetch('wizard/sources', { method: 'POST', body: fd });
        const text = await r.text();
        let data = {};
        try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text || r.statusText }; }
        if (!r.ok) {
          const err = data.detail || data.error || text || 'Save failed';
          throw new Error(typeof err === 'string' ? err : JSON.stringify(err));
        }
         initZones(data.cameras || []);
         setStep(1);
      } catch (e) { show(msg, false, e.message || String(e)); }
    };
    let zoneCameras = [], zones = [], points = [], selectedZone = null, frame = null;
    let dragPoint = null, drawing = false, moveStart = null, movePoints = [];
    const canvas = document.getElementById('zoneCanvas'), ctx = canvas.getContext('2d');
    function notifyZonesChanged(cameraId) {
      if (embedded) {
        window.parent.postMessage({type:'onevo-zones-changed', cameraId}, window.location.origin);
      }
    }
    function cameraId(c) { return c.cameraId || c.id || c.Id || ''; }
    function initZones(cameras) {
      zoneCameras = cameras;
      const sel = document.getElementById('zoneCamera');
      sel.innerHTML = cameras.map((c,i) => `<option value="${cameraId(c)}">${c.name || c.Name || `Camera ${i+1}`}</option>`).join('');
      if (cameras.length) loadZoneCamera();
    }
    function draw() {
      ctx.clearRect(0,0,canvas.width,canvas.height);
      if (frame) ctx.drawImage(frame,0,0,canvas.width,canvas.height);
      for (const z of zones) drawPoly(JSON.parse(z.polygonJson || z.PolygonJson || '[]'), z === selectedZone ? '#ffd36a' : '#6ea8ff');
      drawPoly(points,'#ffd36a',true);
    }
    function drawPoly(p, color, editable=false) {
      if (!p.length) return; ctx.beginPath(); ctx.moveTo(p[0][0]*canvas.width,p[0][1]*canvas.height);
      p.slice(1).forEach(x => ctx.lineTo(x[0]*canvas.width,x[1]*canvas.height));
      if (p.length>2) ctx.closePath(); ctx.fillStyle=color+'44'; ctx.strokeStyle=color; ctx.lineWidth=2; ctx.fill(); ctx.stroke();
      if(editable) p.forEach(point=>{const x=point[0]*canvas.width,y=point[1]*canvas.height;ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fillStyle='#ffd36a';ctx.fill();ctx.strokeStyle='#fff';ctx.stroke()});
    }
    async function loadZoneCamera() {
      const id=document.getElementById('zoneCamera').value; points=[]; selectedZone=null; frame=null; draw();
      try {
        zones=await (await fetch(`wizard/cameras/${id}/zones`)).json();
        loadZoneFrame(id);
        renderZoneList(); draw();
      } catch(e) { show(document.getElementById('zoneMsg'),false,e.message||String(e)); }
    }
    function loadZoneFrame(id) {
      const img=new Image();
      img.onload=()=>{
        if(document.getElementById('zoneCamera').value!==id)return;
        frame=img; draw();
        show(document.getElementById('zoneMsg'),true,'Live frame ready. Draw the zone on the image.');
      };
      img.onerror=()=>{
        if(document.getElementById('zoneCamera').value!==id)return;
        show(document.getElementById('zoneMsg'),false,'Could not capture a frame. Check the source, then click Refresh frame.');
      };
      img.src=`/snapshot?camera_id=${id}&t=${Date.now()}`;
    }
    function renderZoneList() {
      document.getElementById('zoneList').innerHTML=zones.map(z =>
        `<button class="ghost" type="button" data-id="${z.id||z.Id}">${z.name||z.Name}</button>`).join('') || '<span class="hint">No zones yet</span>';
      document.querySelectorAll('#zoneList button').forEach(b=>b.onclick=()=>editZone(b.dataset.id));
    }
    function editZone(id) {
      selectedZone=zones.find(z=>(z.id||z.Id)===id); points=JSON.parse(selectedZone.polygonJson||selectedZone.PolygonJson||'[]');
      document.getElementById('zoneName').value=selectedZone.name||selectedZone.Name;
      document.getElementById('zoneType').value=selectedZone.zoneType||selectedZone.ZoneType;
      document.getElementById('deleteZone').classList.remove('hidden'); draw();
    }
    function resetZone(){selectedZone=null;points=[];dragPoint=null;drawing=false;moveStart=null;movePoints=[];document.getElementById('zoneName').value='';document.getElementById('deleteZone').classList.add('hidden');draw()}
    function canvasPoint(e){
      const r=canvas.getBoundingClientRect();
      return [
        Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),
        Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))
      ];
    }
    function pointInPolygon(point, polygon) {
      let inside=false;
      for(let i=0,j=polygon.length-1;i<polygon.length;j=i++) {
        const [xi,yi]=polygon[i], [xj,yj]=polygon[j];
        if(((yi>point[1]) !== (yj>point[1])) &&
           (point[0] < (xj-xi)*(point[1]-yi)/(yj-yi)+xi)) inside=!inside;
      }
      return inside;
    }
    function simplifyFreehand(raw, tolerance=.012) {
      if(raw.length<=4) return raw;
      const simplify=(items)=>{
        if(items.length<=2) return items;
        const first=items[0], last=items[items.length-1];
        const dx=last[0]-first[0], dy=last[1]-first[1], denominator=dx*dx+dy*dy || 1;
        let maxDistance=0, pivot=0;
        for(let i=1;i<items.length-1;i++) {
          const t=Math.max(0,Math.min(1,((items[i][0]-first[0])*dx+(items[i][1]-first[1])*dy)/denominator));
          const px=first[0]+t*dx, py=first[1]+t*dy;
          const distance=Math.hypot(items[i][0]-px,items[i][1]-py);
          if(distance>maxDistance) { maxDistance=distance;pivot=i; }
        }
        return maxDistance>tolerance
          ? simplify(items.slice(0,pivot+1)).slice(0,-1).concat(simplify(items.slice(pivot)))
          : [first,last];
      };
      const result=simplify(raw);
      return result.length>=3 ? result : raw.slice(0,3);
    }
    canvas.onpointerdown=e=>{
      if(e.button!==0)return;
      const point=canvasPoint(e), index=points.findIndex(p=>Math.hypot(p[0]-point[0],p[1]-point[1])<.025);
      canvas.setPointerCapture(e.pointerId);
      if(index>=0){dragPoint=index;canvas.style.cursor='grabbing';return}
      if(points.length>=3 && pointInPolygon(point,points)){
        moveStart=point;movePoints=points.map(p=>[...p]);canvas.style.cursor='move';return;
      }
      selectedZone=null;
      points=[point];
      drawing=true;
      canvas.style.cursor='crosshair';
      draw();
    };
    canvas.onpointermove=e=>{
      const point=canvasPoint(e);
      if(dragPoint!==null){points[dragPoint]=point;draw();return}
      if(moveStart!==null){
        const dx=point[0]-moveStart[0],dy=point[1]-moveStart[1];
        points=movePoints.map(p=>[Math.max(0,Math.min(1,p[0]+dx)),Math.max(0,Math.min(1,p[1]+dy))]);
        draw();return;
      }
      if(drawing){
        const previous=points[points.length-1];
        if(Math.hypot(previous[0]-point[0],previous[1]-point[1])>=.008) points.push(point);
        draw();
        return;
      }
      canvas.style.cursor=points.some(p=>Math.hypot(p[0]-point[0],p[1]-point[1])<.025)?'grab':'crosshair';
    };
    canvas.onpointerup=e=>{
      if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);
      if(dragPoint!==null){dragPoint=null;canvas.style.cursor='grab';draw()}
      else if(moveStart!==null){moveStart=null;movePoints=[];canvas.style.cursor='crosshair';draw()}
      else if(drawing) {
        drawing=false;
        points=simplifyFreehand(points);
        if (points.length < 3) {
          points=[];
          show(document.getElementById('zoneMsg'),false,'Draw a larger area to create a zone.');
        }
        canvas.style.cursor='crosshair';
        draw();
      }
    };
    canvas.onpointercancel=()=>{dragPoint=null;drawing=false;moveStart=null;movePoints=[];canvas.style.cursor='crosshair';draw()};
    document.getElementById('zoneCamera').onchange=loadZoneCamera;
    document.getElementById('refreshFrame').onclick=()=>{
      const id=document.getElementById('zoneCamera').value;
      if(id) loadZoneFrame(id);
    };
    document.getElementById('newZone').onclick=resetZone;
    document.getElementById('clearZone').onclick=resetZone;
    document.getElementById('undoPoint').onclick=()=>{points.pop();draw()};
    document.getElementById('saveZone').onclick=async()=>{
      const body={zoneId:selectedZone&&(selectedZone.id||selectedZone.Id),name:document.getElementById('zoneName').value.trim(),zoneType:document.getElementById('zoneType').value,polygon:points};
      if(!body.name||points.length<3){show(document.getElementById('zoneMsg'),false,'Enter a name and draw at least 3 points');return}
      const id=document.getElementById('zoneCamera').value,r=await fetch(`wizard/cameras/${id}/zones`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!r.ok){show(document.getElementById('zoneMsg'),false,await r.text());return}
      notifyZonesChanged(id); resetZone();await loadZoneCamera();
    };
    document.getElementById('deleteZone').onclick=async()=>{
      if(!selectedZone)return;
      const cameraId=document.getElementById('zoneCamera').value;
      await fetch(`wizard/zones/${selectedZone.id||selectedZone.Id}`,{method:'DELETE'});
      notifyZonesChanged(cameraId);resetZone();await loadZoneCamera()
    };
    document.getElementById('finishZones').onclick=async()=>{
      const msg=document.getElementById('zoneMsg');
      try {
        const r=await fetch('wizard/zones/finish',{method:'POST'});
        const text=await r.text();
        let data={};
        try { data=text?JSON.parse(text):{}; } catch { data={detail:text||r.statusText}; }
        if(!r.ok) throw new Error(data.detail||data.error||text||'Zone setup is incomplete');
        show(msg,true,'All camera zones are saved and synchronized.');
        const finishButton=document.getElementById('finishZones');
        finishButton.disabled=true;
        finishButton.textContent='Setup complete';
        if (embedded) {
          window.parent.postMessage({type:'onevo-zones-complete'}, window.location.origin);
        } else {
          setTimeout(()=>window.location.replace('/'),350);
        }
      } catch(e) { show(msg,false,e.message||String(e)); }
    };
    boot();
  </script>
</body>
</html>
"""


def attach_wizard_routes(
    app: FastAPI,
    state: "RuntimeState",
    cfg: "Config",
    store: "LocalStore",
    *,
    route_prefix: str = "",
    on_configured=None,
) -> None:
    """Register setup wizard routes on an existing FastAPI app."""
    prefix = route_prefix.rstrip("/")
    page_path = prefix or "/"
    api_prefix = f"{prefix}/wizard" if prefix else "/wizard"
    client = BackendClient(cfg.backend_url)

    def _reload_creds() -> bool:
        cid = store.get_cred("connector_id")
        key = store.get_cred("api_key")
        if cid and key:
            client.set_credentials(cid, key)
            return True
        return False

    @app.get(page_path, response_class=HTMLResponse)
    def wizard_index(request: Request):
        # In service mode the sidebar dashboard is the only visual UI. Keep
        # this route for old bookmarks, but route it into the matching view
        # while retaining /setup/wizard/* as the zone/source API namespace.
        if prefix and request.query_params.get("embedded") != "1":
            wizard = load_wizard_config()
            has_cameras = bool(
                wizard and any(source.camera_id for source in wizard.sources)
            )
            return RedirectResponse("/#zones" if has_cameras else "/#sources", status_code=307)
        return wizard_page_html(prefix)

    @app.get(f"{api_prefix}/status")
    def wizard_status():
        w = load_wizard_config()
        claimed = bool(store.get_cred("connector_id") and store.get_cred("api_key"))
        cameras = [
            {"cameraId": source.camera_id, "name": source.name}
            for source in (w.sources if w else [])
            if source.camera_id
        ]
        return {
            "setupComplete": bool(w and w.setup_complete),
            "claimed": claimed,
            "backendUrl": cfg.backend_url,
            "version": cfg.version,
            "activationError": (w.activation_error if w else "") or "",
            "cameras": cameras,
            "hasConfiguredSources": bool(w and w.sources),
            "readyForZones": bool(claimed and cameras),
        }

    @app.post(f"{api_prefix}/sources")
    async def wizard_sources(
        rtsp_text: str = Form(default=""),
        onvif_host: str = Form(default=""),
        onvif_port: int = Form(default=80),
        onvif_user: str = Form(default="admin"),
        onvif_pass: str = Form(default=""),
        files: list[UploadFile] = File(default=[]),
        loop_file: bool = Form(default=True),
    ):
        if not _reload_creds():
            raise HTTPException(400, "Claim a setup code first")

        sources: list[CameraSource] = []
        lines = parse_rtsp_urls(rtsp_text or "")
        for i, url in enumerate(lines, start=1):
            if not url.lower().startswith("rtsp://"):
                raise HTTPException(400, f"Invalid RTSP URL (line {i}): must start with rtsp://")
            ok, msg = validate_rtsp_stream(url)
            if not ok:
                raise HTTPException(400, f"RTSP preflight failed for '{url}': {msg}")
            sources.append(CameraSource(name=f"Camera {i}", rtsp_url=url, loop=False))

        if onvif_host.strip():
            if not 1 <= onvif_port <= 65535:
                raise HTTPException(400, "ONVIF port must be between 1 and 65535")
            sources.append(
                CameraSource(
                    name="ONVIF Camera",
                    onvif_host=onvif_host.strip(),
                    onvif_port=onvif_port,
                    onvif_user=onvif_user.strip() or "admin",
                    onvif_pass=onvif_pass,
                )
            )

        for index, file in enumerate(files, start=1):
            if not file.filename:
                continue
            if not file.filename.lower().endswith(".mp4"):
                raise HTTPException(400, f"{file.filename}: upload an MP4 video")
            dest = media_dir() / f"wizard-video-{uuid.uuid4().hex}.mp4"
            with dest.open("wb") as out:
                shutil.copyfileobj(file.file, out)
            sources.append(
                CameraSource(
                    name=f"Test Video {index}",
                    source_file=str(dest),
                    loop=loop_file,
                )
            )

        if not sources:
            raise HTTPException(400, "Add an RTSP URL, ONVIF camera, or upload an MP4")

        unique_sources: list[CameraSource] = []
        seen_keys: set[str] = set()
        for source in sources:
            source.source_key = source_key_for(source)
            if source.source_key in seen_keys:
                if source.source_file:
                    Path(source.source_file).unlink(missing_ok=True)
                continue
            seen_keys.add(source.source_key)
            unique_sources.append(source)
        sources = unique_sources

        w = load_wizard_config() or WizardConfig()
        w.sources = sources
        w.setup_complete = False

        def checkpoint(current_sources):
            w.sources = current_sources
            save_wizard_config(w)

        try:
            created = provision_sources(
                client, sources, state, checkpoint=checkpoint
            )
            client.finalize_setup([source.source_key for source in created])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Failed to configure cameras: {exc}") from exc

        w = load_wizard_config() or WizardConfig()
        w.activation_error = ""
        w.sources = created
        w.setup_complete = False
        save_wizard_config(w)
        state.log(f"Wizard: prepared {len(created)} source(s) for zone setup")

        return {
            "ok": True,
            "cameraCount": len(created),
            "cameras": [
                {"cameraId": source.camera_id, "name": source.name}
                for source in created
            ],
        }

    @app.get(f"{api_prefix}/cameras/{{camera_id}}/zones")
    def wizard_zones(camera_id: str):
        if not _reload_creds():
            raise HTTPException(401, "Connector is not paired")
        try:
            return client.get_zones(camera_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Could not load zones: {exc}") from exc

    @app.post(f"{api_prefix}/cameras/{{camera_id}}/zones")
    def wizard_save_zone(camera_id: str, body: WizardZoneBody):
        if not _reload_creds():
            raise HTTPException(401, "Connector is not paired")
        if len(body.polygon) < 3:
            raise HTTPException(400, "Draw at least three zone points")
        if any(len(point) != 2 or any(value < 0 or value > 1 for value in point)
               for point in body.polygon):
            raise HTTPException(400, "Zone points must be normalized between 0 and 1")
        try:
            if body.zoneId:
                result = client.update_zone(
                    body.zoneId, body.name, body.zoneType, body.polygon
                )
            else:
                result = client.create_zone(
                    camera_id, body.name, body.zoneType, body.polygon
                )
            state.invalidate_zones(camera_id)
            return result
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Could not save zone: {exc}") from exc

    @app.delete(f"{api_prefix}/zones/{{zone_id}}")
    def wizard_delete_zone(zone_id: str):
        if not _reload_creds():
            raise HTTPException(401, "Connector is not paired")
        try:
            zones = []
            wizard = load_wizard_config()
            if wizard:
                zones = [
                    source.camera_id for source in wizard.sources if source.camera_id
                ]
            client.delete_zone(zone_id)
            # The backend delete route is zone-id based. Invalidate all local
            # cameras; the cache reload is cheap and avoids stale masks.
            for camera_id in zones:
                state.invalidate_zones(camera_id)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Could not delete zone: {exc}") from exc

    @app.post(f"{api_prefix}/zones/finish")
    def wizard_finish_zones():
        """Require at least one backend-saved zone for every configured camera."""
        if not _reload_creds():
            raise HTTPException(401, "Connector is not paired")
        wizard = load_wizard_config()
        cameras = [
            source for source in (wizard.sources if wizard else [])
            if source.camera_id
        ]
        if not cameras:
            raise HTTPException(400, "No configured cameras are available for zone setup")

        missing: list[str] = []
        try:
            for source in cameras:
                if not client.get_zones(source.camera_id):
                    missing.append(source.name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Could not verify camera zones: {exc}") from exc

        if missing:
            raise HTTPException(
                400,
                "Create and save at least one zone for: " + ", ".join(missing),
            )
        # The native installer watches this local marker and only enables its
        # final Finish button after the browser-based zone workflow completes.
        marker = default_state_dir() / "zone_setup.complete"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("complete\n", encoding="utf-8")
        # Keep sources that are still waiting for provisioning. Passing only
        # camera-id-bearing entries silently deleted transiently failed sources.
        complete_setup(wizard, list(wizard.sources))
        if on_configured:
            try:
                on_configured(wizard)
            except Exception as exc:  # noqa: BLE001
                state.log(f"WARNING: on_configured hook failed: {exc}")
        state.log(f"Wizard: zone setup completed for {len(cameras)} camera(s)")
        return {"ok": True, "cameraCount": len(cameras)}


def build_wizard_app(
    state: "RuntimeState",
    cfg: "Config",
    store: "LocalStore",
    on_configured=None,
) -> FastAPI:
    app = FastAPI(title="ONEVO Connector Setup Wizard")
    attach_wizard_routes(
        app,
        state,
        cfg,
        store,
        route_prefix="",
        on_configured=on_configured,
    )
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



