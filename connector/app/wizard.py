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
from .provisioning import claim_setup, complete_setup, provision_sources, source_key_for
from .wizard_html import WIZARD_HTML

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

    def _persist_reference_frame(camera_id: str) -> bool:
        """Persist the selected camera's last frame for offline zone editing."""
        frame = state.get_frame(camera_id)
        if not frame:
            return False
        try:
            client.upload_reference_frame(camera_id, frame)
            state.log(f"Wizard: saved reference frame for camera {camera_id}")
            return True
        except Exception as exc:  # noqa: BLE001
            state.log(f"WARNING: reference frame save failed for {camera_id}: {exc}")
            return False

    @app.get(page_path, response_class=HTMLResponse)
    def wizard_index(request: Request):
        # First-run / incomplete setup always gets the dark wizard.
        # Completed installs redirect into the admin dashboard (or embedded iframe).
        if prefix and request.query_params.get("embedded") != "1":
            wizard = load_wizard_config()
            if wizard and wizard.setup_complete:
                has_cameras = any(source.camera_id for source in wizard.sources)
                return RedirectResponse(
                    "/#zones" if has_cameras else "/#dashboard",
                    status_code=307,
                )
        return wizard_page_html(prefix)

    @app.get(f"{api_prefix}/status")
    def wizard_status():
        w = load_wizard_config()
        cid = store.get_cred("connector_id")
        key = store.get_cred("api_key")
        claimed = bool(cid and key)
        cameras = [
            {"cameraId": source.camera_id, "name": source.name}
            for source in (w.sources if w else [])
            if source.camera_id
        ]
        return {
            "setupComplete": bool(w and w.setup_complete),
            "claimed": claimed,
            "connectorId": cid or "",
            "backendUrl": cfg.backend_url,
            "version": cfg.version,
            "activationError": (w.activation_error if w else "") or "",
            "cameras": cameras,
            "hasConfiguredSources": bool(w and w.sources),
            "readyForZones": bool(claimed and cameras),
        }

    class WizardClaimBody(BaseModel):
        setupCode: str
        connectorName: str = "ONETIX Store Connector"

    @app.post(f"{api_prefix}/claim")
    def wizard_claim(body: WizardClaimBody):
        code = (body.setupCode or "").strip()
        name = (body.connectorName or "").strip() or "ONETIX Store Connector"
        if not code:
            raise HTTPException(400, "Setup code is required")
        w = load_wizard_config() or WizardConfig()
        w.setup_code = code
        w.connector_name = name
        w.activation_error = ""
        save_wizard_config(w)
        try:
            cid, store_id = claim_setup(client, store, w, cfg.version)
            state.log(f"Wizard: claimed setup code → connector {cid}")
            return {
                "ok": True,
                "connectorId": cid,
                "storeId": store_id,
                "claimed": True,
            }
        except Exception as exc:  # noqa: BLE001
            w = load_wizard_config() or WizardConfig()
            w.activation_error = str(exc)
            save_wizard_config(w)
            raise HTTPException(502, f"Could not claim setup code: {exc}") from exc

    @app.post(f"{api_prefix}/skip-sources")
    def wizard_skip_sources():
        if not _reload_creds():
            raise HTTPException(400, "Claim a setup code first")
        w = load_wizard_config() or WizardConfig()
        w.sources = []
        w.activation_error = ""
        complete_setup(w, [])
        if on_configured:
            try:
                on_configured(w)
            except Exception as exc:  # noqa: BLE001
                state.log(f"WARNING: on_configured hook failed: {exc}")
        state.log("Wizard: skipped camera sources")
        return {"ok": True, "cameraCount": 0, "cameras": []}

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
            _persist_reference_frame(camera_id)
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
        marker = default_state_dir() / "zone_setup.complete"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("complete\n", encoding="utf-8")
        complete_setup(wizard, list(wizard.sources))
        if on_configured:
            try:
                on_configured(wizard)
            except Exception as exc:  # noqa: BLE001
                state.log(f"WARNING: on_configured hook failed: {exc}")
        state.log(f"Wizard: zone setup completed for {len(cameras)} camera(s)")
        return {"ok": True, "cameraCount": len(cameras)}

    @app.post(f"{api_prefix}/zones/skip")
    def wizard_skip_zones():
        """Finish setup without requiring zones (operator chose Skip)."""
        if not _reload_creds():
            raise HTTPException(401, "Connector is not paired")
        wizard = load_wizard_config() or WizardConfig()
        marker = default_state_dir() / "zone_setup.complete"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("skipped\n", encoding="utf-8")
        complete_setup(wizard, list(wizard.sources))
        if on_configured:
            try:
                on_configured(wizard)
            except Exception as exc:  # noqa: BLE001
                state.log(f"WARNING: on_configured hook failed: {exc}")
        state.log("Wizard: zone setup skipped")
        return {"ok": True, "cameraCount": len(wizard.sources)}


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



