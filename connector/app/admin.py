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
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from typing import TYPE_CHECKING, Callable

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .paths import (
    CameraSource,
    WizardConfig,
    load_wizard_config,
    media_dir,
    pause_marker_path,
    save_wizard_config,
)
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


class SourceUpdateBody(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    onvif_host: str | None = None
    onvif_port: int | None = Field(default=None, ge=1, le=65535)
    onvif_user: str | None = None
    onvif_pass: str | None = None


class BulkDeleteBody(BaseModel):
    source_keys: list[str] = Field(default_factory=list)


def _masked_source_value(source: CameraSource) -> str:
    if source.source_file:
        return Path(source.source_file).name
    if source.onvif_host:
        return source.onvif_host
    parsed = urlsplit(source.rtsp_url)
    if not parsed.password:
        return source.rtsp_url
    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:••••@{hostname}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def build_app(
    state: RuntimeState,
    cfg: "Config",
    client: "BackendClient | None" = None,
    store: "LocalStore | None" = None,
    enable_setup_wizard: bool = False,
    on_wizard_configured: Callable | None = None,
) -> FastAPI:
    app = FastAPI(title="ONEVO Connector Admin")

    admin_token = (cfg.admin_token or "").strip()

    @app.middleware("http")
    async def admin_auth_middleware(request, call_next):
        path = request.url.path
        paired = bool(
            store is not None
            and store.get_cred("connector_id")
            and store.get_cred("api_key")
        )
        setup_path = path == "/setup" or path.startswith("/setup/")
        client_host = request.client.host if request.client else ""
        loopback_setup = setup_path and client_host in ("127.0.0.1", "::1")
        first_run_setup = setup_path and not paired
        if path == "/health" or first_run_setup or loopback_setup:
            response = await call_next(request)
        elif admin_token:
            provided = request.headers.get("X-Admin-Token") or request.query_params.get("admin_token")
            if provided != admin_token:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            response = await call_next(request)
        else:
            response = await call_next(request)
        if path == "/" or path == "/setup":
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/status")
    def status():
        return state.snapshot()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/sources")
    def sources():
        wizard = load_wizard_config() or WizardConfig()
        management_ready = bool(
            client is not None
            and store is not None
            and store.get_cred("connector_id")
            and store.get_cred("api_key")
        )
        for source in wizard.sources:
            source.source_key = source.source_key or source_key_for(source)
        return {
            "managementReady": management_ready,
            "sources": [
                {
                    "name": source.name,
                    "type": (
                        "onvif" if source.onvif_host else
                        "video" if source.source_file else "rtsp"
                    ),
                    "value": _masked_source_value(source),
                    "cameraId": source.camera_id,
                    "sourceKey": source.source_key,
                }
                for source in wizard.sources
            ]
        }

    def _sync_sources(wizard: WizardConfig) -> bool:
        connector_id = store.get_cred("connector_id") if store else None
        api_key = store.get_cred("api_key") if store else None
        if client is None or not (connector_id and api_key):
            wizard.setup_complete = False
            save_wizard_config(wizard)
            return False
        client.set_credentials(connector_id, api_key)
        client.finalize_setup([
            source.source_key or source_key_for(source) for source in wizard.sources
        ])
        wizard.use_backend_cameras = True
        wizard.setup_complete = True
        save_wizard_config(wizard)
        return True

    @app.put("/sources/{source_key}")
    def update_source(source_key: str, body: SourceUpdateBody):
        wizard = load_wizard_config() or WizardConfig()
        source_index = next(
            (
                index for index, item in enumerate(wizard.sources)
                if (item.source_key or source_key_for(item)) == source_key
            ),
            -1,
        )
        source = wizard.sources[source_index] if source_index >= 0 else None
        if source is None:
            raise HTTPException(404, "Source not found")
        if body.name is not None:
            source.name = body.name.strip() or source.name
        if body.rtsp_url is not None:
            source.rtsp_url = body.rtsp_url.strip()
            source.source_file = ""
            source.onvif_host = ""
            source.resolved_rtsp_url = ""
        if body.onvif_host is not None:
            source.onvif_host = body.onvif_host.strip()
            source.rtsp_url = ""
            source.source_file = ""
        if body.onvif_port is not None:
            source.onvif_port = body.onvif_port
        if body.onvif_user is not None:
            source.onvif_user = body.onvif_user.strip()
        if body.onvif_pass:
            source.onvif_pass = body.onvif_pass
        source.source_key = source_key_for(source)
        source.camera_id = ""
        validate_sources([source])
        wizard.setup_complete = False
        save_wizard_config(wizard)
        pending = True
        if client is not None and store is not None:
            try:
                created = provision_sources(client, [source], state)
                source = created[0]
                wizard.sources[source_index] = source
                pending = not _sync_sources(wizard)
            except Exception as exc:  # noqa: BLE001
                state.log(f"Local admin: source update pending: {exc}")
        return {"ok": True, "pending": pending, "sourceKey": source.source_key}

    @app.post("/sources/bulk-delete")
    def bulk_delete_sources(body: BulkDeleteBody):
        requested = {key.strip() for key in body.source_keys if key.strip()}
        if not requested:
            raise HTTPException(400, "Select at least one source")
        wizard = load_wizard_config() or WizardConfig()
        before = len(wizard.sources)
        wizard.sources = [
            source for source in wizard.sources
            if (source.source_key or source_key_for(source)) not in requested
        ]
        removed = before - len(wizard.sources)
        if removed == 0:
            raise HTTPException(404, "No matching sources found")
        pending = True
        try:
            pending = not _sync_sources(wizard)
        except Exception as exc:  # noqa: BLE001
            wizard.setup_complete = False
            save_wizard_config(wizard)
            state.log(f"Local admin: bulk removal sync pending: {exc}")
        return {"ok": True, "removed": removed, "pending": pending}

    @app.delete("/sources/by-key/{source_key}")
    def delete_source_by_key(source_key: str):
        return bulk_delete_sources(BulkDeleteBody(source_keys=[source_key]))

    @app.post("/sources")
    async def add_sources(
        source_type: str = Form(...),
        rtsp_text: str = Form(default=""),
        onvif_json: str = Form(default="[]"),
        files: list[UploadFile] = File(default=[]),
    ):
        if client is None or store is None:
            raise HTTPException(503, "Source management is unavailable")
        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if not (connector_id and api_key):
            raise HTTPException(
                409,
                "Complete connector setup with a setup code before adding camera sources",
            )

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
        existing_keys = {source.source_key for source in existing}
        duplicate_names: list[str] = []
        for source in new_sources:
            source.source_key = source_key_for(source)
            if source.source_key in existing_keys:
                duplicate_names.append(source.name)
            existing_keys.add(source.source_key)
        if duplicate_names:
            # Uploads are copied to ProgramData before their stable content key is
            # calculated. Remove those temporary copies when the same physical
            # video/camera was already configured.
            for source in new_sources:
                if source.source_file:
                    Path(source.source_file).unlink(missing_ok=True)
            raise HTTPException(
                409,
                "Already added: " + ", ".join(duplicate_names) +
                ". Remove the existing source first if you need to replace it.",
            )

        wizard.sources = existing + new_sources
        wizard.setup_complete = False
        save_wizard_config(wizard)

        client.set_credentials(connector_id, api_key)

        def checkpoint(created):
            wizard.sources = existing + created
            save_wizard_config(wizard)

        try:
            created = provision_sources(client, new_sources, state, checkpoint=checkpoint)
            wizard.sources = existing + created
            wizard.use_backend_cameras = True
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
        if store is not None:
            store.set_bool_setting("monitoring_paused", True)
        state.set_paused(True)
        marker = pause_marker_path()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        return {
            "ok": True,
            "paused": True,
            "serviceStopping": False,
            "message": (
                "Monitoring is stopped. Camera reads, motion detection, uploads, "
                "and cloud heartbeat are paused; the local control page stays available."
            ),
        }

    @app.post("/capture/resume")
    def capture_resume():
        if store is not None:
            store.set_bool_setting("monitoring_paused", False)
        state.set_paused(False)
        pause_marker_path().unlink(missing_ok=True)
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(
                ["sc.exe", "config", "ONEVOConnector", "start=", "auto"],
                creationflags=flags,
                capture_output=True,
                check=False,
            )
        return {"ok": True, "paused": False}

    @app.post("/capture/trigger-now")
    def capture_trigger_now():
        if state.capture_paused:
            raise HTTPException(
                status_code=409,
                detail="Monitoring is stopped. Start monitoring before creating a clip.",
            )
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
        if state.capture_paused:
            raise HTTPException(
                status_code=409,
                detail="Monitoring is stopped. Start monitoring before uploading a source.",
            )
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
    @app.get("/setup/snapshot")
    def snapshot(camera_id: str):
        """Return a live snapshot from the CapturePipeline's recent frames."""
        frame = state.last_frames.get(camera_id)
        if not frame and len(state.last_frames) == 1:
            # Keep the legacy single-camera compatibility fallback, but never
            # use one camera's preview as another camera's zone-edit frame.
            wizard = load_wizard_config()
            if wizard and len(wizard.sources) == 1:
                frame = next(iter(state.last_frames.values()))
        if not frame:
            # First-run setup deliberately waits to start capture until every
            # camera has a saved zone. The wizard still needs a real frame to
            # draw that zone, so obtain one directly from its configured source.
            wizard = load_wizard_config()
            source = next(
                (
                    item for item in (wizard.sources if wizard else [])
                    if item.camera_id == camera_id
                ),
                None,
            )
            if source is not None:
                try:
                    import cv2

                    source_url = source.source_file or source.rtsp_url or ""
                    if source.onvif_host:
                        from .onvif_client import OnvifCamera

                        camera = OnvifCamera().connect(
                            source.onvif_host,
                            source.onvif_port,
                            source.onvif_user or "admin",
                            source.onvif_pass,
                        )
                        frame = camera.fetch_snapshot_bytes()
                    elif source_url:
                        capture = cv2.VideoCapture(
                            source_url,
                            cv2.CAP_FFMPEG,
                            [
                                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
                            ],
                        )
                        try:
                            ok, image = capture.read()
                            if ok and image is not None:
                                encoded, buffer = cv2.imencode(".jpg", image)
                                if encoded:
                                    frame = buffer.tobytes()
                        finally:
                            capture.release()
                except Exception as exc:  # noqa: BLE001
                    state.log(f"Setup snapshot unavailable for {camera_id}: {exc}")
        if not frame:
            raise HTTPException(status_code=404, detail="No snapshot available yet")
        return Response(content=frame, media_type="image/jpeg")

    @app.get("/live/cameras")
    def live_cameras():
        return {"cameras": state.camera_statuses()}

    @app.get("/live/cameras/{camera_id}/status")
    def live_camera_status(camera_id: str):
        camera = next(
            (item for item in state.camera_statuses() if item["cameraId"] == camera_id),
            None,
        )
        if camera is None:
            raise HTTPException(404, "Camera runtime not found")
        return camera

    @app.get("/live/cameras/{camera_id}/zones")
    def live_camera_zones(camera_id: str):
        """Return the saved polygons used to overlay this local live preview."""
        if client is None or store is None:
            raise HTTPException(503, "Connector backend client is unavailable")
        # The service can replace its operational client after installer
        # provisioning. Reload durable credentials so overlays never use a
        # stale/unauthenticated client instance.
        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if not (connector_id and api_key):
            raise HTTPException(401, "Connector is not paired")
        try:
            client.set_credentials(connector_id, api_key)
            return client.get_zones(camera_id)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Could not load camera zones: {exc}") from exc

    @app.get("/live/cameras/{camera_id}/stream.mjpg")
    def live_camera_stream(camera_id: str):
        def frames():
            last_frame = None
            while True:
                frame = state.get_frame(camera_id)
                if frame and frame is not last_frame:
                    last_frame = frame
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                        + frame
                        + b"\r\n"
                    )
                time.sleep(0.125)

        return StreamingResponse(
            frames(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

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
    body{{font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0b0e13;color:#eef2f8;
      padding:1.5rem 1.5rem 1.5rem 13rem;max-width:1500px;margin:auto}}
    h1{{font-size:1.1rem;font-weight:600;color:#8ab4f8;margin-bottom:1rem}}
    h2{{font-size:.85rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
        color:#888;margin-bottom:.5rem}}
    .section{{background:#151a22;border:1px solid #222b38;border-radius:12px;
      padding:1.15rem;margin-bottom:1rem;box-shadow:0 8px 28px rgba(0,0,0,.12)}}
    .grid{{display:grid;grid-template-columns:180px 1fr;gap:.2rem .75rem;font-size:.85rem}}
    .k{{color:#8ab4f8;font-size:.8rem}}
    .v{{color:#e6e6e6;word-break:break-all}}
    pre{{background:#0f1216;padding:.75rem;border-radius:6px;max-height:300px;overflow:auto;
         font-size:.75rem;line-height:1.4;margin-top:.5rem}}
    .badge{{display:inline-block;padding:.1rem .5rem;border-radius:10px;font-size:.7rem;font-weight:600}}
    .ok{{background:#1a3a2a;color:#5cdb7f}}.warn{{background:#3a2a1a;color:#f0a030}}
    .err{{background:#3a1a1a;color:#f07070}}
    .btn{{display:inline-flex;align-items:center;justify-content:center;padding:.48rem .8rem;
          border-radius:8px;font-size:.8rem;background:#1b2431;color:#9fc2ff;
          text-decoration:none;border:1px solid #30415a;min-height:36px}}
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
    .source-notice{{padding:.8rem 1rem;border:1px solid #60452c;background:#2b2117;
      border-radius:9px;color:#ffc27a;font-size:.82rem;line-height:1.45;margin:.75rem 0}}
    .source-toolbar{{display:flex;justify-content:space-between;align-items:center;gap:.75rem;
      flex-wrap:wrap;margin:.75rem 0}}
    .check-all{{display:flex;align-items:center;gap:.5rem;padding:.48rem .7rem;
      border:1px solid #30415a;border-radius:8px;background:#10151c;color:#c9d3e2;font-size:.8rem}}
    .check-all input,.source-card input{{accent-color:#79a7ff;width:16px;height:16px}}
    .source-card{{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;
      gap:.75rem;padding:.75rem;margin:.55rem 0;border:1px solid #283444;border-radius:10px;
      background:#10151c}}
    .source-card .source-title{{font-weight:650;font-size:.85rem;color:#eef2f8}}
    .source-card .source-detail{{font-size:.74rem;color:#8d99aa;margin-top:.18rem;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
    .btn.danger{{border-color:#6a3030;color:#f07070}}
    .btn.primary{{border-color:#3a5080;color:#8ab4f8}}
    .hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem}}
    .local-nav{{position:fixed;z-index:20;inset:0 auto 0 0;width:11.5rem;padding:1.25rem .65rem;
      display:flex;gap:.3rem;flex-direction:column;background:#10131c;border-right:1px solid #242b3a}}
    .local-nav:before{{content:'◆ ONEVO\\A CONNECTOR';white-space:pre;line-height:1.5;color:#a98cff;
      font-size:.75rem;font-weight:700;letter-spacing:.06em;padding:.35rem .6rem .9rem}}
    .local-nav a{{color:#aeb8c9;text-decoration:none;font-size:.8rem;padding:.6rem .7rem;border-radius:6px}}
    .local-nav a:hover,.local-nav a.active{{background:#35235e;color:#d5c4ff}}
    .view-hidden{{display:none!important}}
    @media(max-width:720px){{body{{padding:5rem 1rem 1rem}}.local-nav{{width:100%;height:4rem;flex-direction:row;
      overflow:auto;align-items:center;padding:.5rem;white-space:nowrap}}.local-nav:before{{display:none}}}}
    .hidden{{display:none!important}}
    #tick{{font-size:.7rem;color:#555}}
    .row{{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin-top:.5rem}}
    input[type=number]{{width:4.5rem;padding:.25rem .4rem;border-radius:4px;border:1px solid #2a3a50;
      background:#0f1216;color:#e6e6e6;font-size:.82rem}}
    .hint{{font-size:.75rem;color:#888;margin-top:.35rem}}
    .camera-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.75rem}}
    .camera-tile{{background:#0f1216;border:1px solid #2a3a50;border-radius:8px;overflow:hidden;
      cursor:pointer;transition:border-color .15s,transform .15s}}
    .camera-tile:hover{{border-color:#8ab4f8;transform:translateY(-1px)}}
    .camera-visual{{position:relative;aspect-ratio:16/9;background:#090b0e}}
    .camera-tile img{{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;background:#090b0e}}
    .zone-overlay{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}}
    .camera-tile .meta{{display:flex;justify-content:space-between;gap:.5rem;padding:.55rem .65rem;
      font-size:.78rem}}
    .camera-focus{{position:fixed;inset:0;background:rgba(4,6,9,.96);z-index:50;padding:2rem;
      display:flex;flex-direction:column;gap:.75rem}}
    .camera-focus .camera-visual{{flex:1;aspect-ratio:auto}}
    .camera-focus img{{width:100%;height:calc(100vh - 7rem);object-fit:contain;background:#000}}
    .camera-focus .focus-head{{display:flex;justify-content:space-between;align-items:center}}
    #action-msg{{font-size:.78rem;color:#5cdb7f;margin-top:.35rem}}
    #action-err{{font-size:.78rem;color:#f07070;margin-top:.35rem}}
    .zone-workbench{{display:grid;grid-template-columns:minmax(0,1fr) 17rem;gap:1rem;margin-top:.75rem}}
    .zone-canvas-wrap{{position:relative;border:1px solid #2a3a4d;border-radius:10px;overflow:hidden;
      background:#090b0e;min-height:360px}}
    #zoneCanvas{{display:block;width:100%;height:auto;max-height:640px;touch-action:none;cursor:crosshair}}
    .zone-tools{{border:1px solid #2a3a4d;border-radius:10px;background:#10151c;padding:.85rem}}
    .zone-tools input,.zone-tools select{{width:100%;box-sizing:border-box;margin:.3rem 0 .65rem;
      background:#0f1216;color:#e6e6e6;border:1px solid #2a3a50;border-radius:5px;padding:.45rem}}
    .zone-list{{display:flex;flex-direction:column;gap:.35rem;max-height:180px;overflow:auto;margin:.6rem 0}}
    .zone-list button{{text-align:left}}
    @media(max-width:820px){{.zone-workbench{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <div class="hdr">
    <h1>🎥 ONEVO Local Connector</h1>
    <span id="tick">—</span>
  </div>
  <nav class="local-nav" aria-label="Connector navigation">
    <a href="#dashboard" data-view="dashboard">Dashboard</a>
    <a href="#sources" data-view="sources">Sources</a>
    <a href="#live" data-view="live">Live view</a>
    <a href="#zones" data-view="zones">Zones</a>
    <a href="#logs" data-view="logs">Logs</a>
    <a href="#settings" data-view="settings">Settings</a>
    <a href="#about" data-view="about">About</a>
  </nav>

  <div class="section hidden" id="alert-banner">
    <h2 id="alert-title" style="color:#f07070"></h2>
    <p id="alert-text" style="font-size:.85rem;line-height:1.45;margin-bottom:.75rem"></p>
  </div>

  <div class="section" id="dashboard" data-view="dashboard">
    <h2>Runtime</h2>
    <div class="grid" id="runtime-grid"></div>
  </div>

  <div class="section" data-view="dashboard">
    <h2>Actions</h2>
    <p class="hint">Stop monitoring pauses camera processing but keeps this local page available. Start monitoring resumes the same configured cameras.</p>
    <div class="row">
      <button class="btn" id="btn-pause" onclick="pauseCapture()">Stop monitoring</button>
      <button class="btn" id="btn-resume" onclick="resumeCapture()">Start monitoring</button>
      <button class="btn" id="btn-trigger" onclick="triggerNow()">Cut clip now</button>
      <button class="btn primary" id="btn-upload-source" onclick="uploadFullSource()">Upload full source file</button>
      <button class="btn" type="button" onclick="openZoneEditor()">Edit camera zones</button>
    </div>
    <div id="action-msg"></div>
    <div id="action-err"></div>
  </div>

  <div class="section hidden" id="zone-editor-section" data-view="zones">
    <div class="hdr">
      <div>
        <h2>Camera Zones</h2>
        <p class="hint">Drag to draw a rectangular monitoring area. Drag a yellow corner to resize it, or drag inside the zone to move it. Live previews remain available while you edit.</p>
      </div>
      <div class="row" style="margin:0">
        <button class="btn" type="button" onclick="refreshZoneEditor()">Refresh frame</button>
        <button class="btn" type="button" onclick="closeZoneEditor()">Close editor</button>
      </div>
    </div>
    <div class="zone-workbench">
      <div class="zone-canvas-wrap"><canvas id="zoneCanvas" width="960" height="540"></canvas></div>
      <div class="zone-tools">
        <label class="hint">Camera</label><select id="zoneCamera"></select>
        <label class="hint">Zone name</label><input id="zoneName" placeholder="e.g. Checkout area" />
        <label class="hint">Zone type</label>
        <select id="zoneType"><option value="Shelf">Shelf</option><option value="HighValue">High-value shelf</option><option value="Checkout">Checkout</option><option value="Exit">Exit</option><option value="BlindSpot">Blind spot</option><option value="Staff">Staff area</option></select>
        <div class="row"><button class="btn" id="zoneNew" type="button">New</button><button class="btn" id="zoneUndo" type="button">Undo</button></div>
        <div class="row"><button class="btn primary" id="zoneSave" type="button">Save zone</button><button class="btn danger" id="zoneDelete" type="button">Delete</button></div>
        <div class="zone-list" id="zoneList"></div>
        <button class="btn primary" id="zoneFinish" type="button">Finish setup</button>
        <div class="source-msg" id="zoneMsg"></div>
      </div>
    </div>
  </div>

  <div class="section" id="settings" data-view="settings">
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

  <div class="section" data-view="settings">
    <h2>Local clips</h2>
    <p class="hint" id="local-clips-summary">—</p>
    <div class="row">
      <button class="btn danger" onclick="clearLocalClips()">Clear local clips</button>
    </div>
  </div>

  {onvif_section}

  <div class="section" id="live-cameras-section" data-view="live">
    <div class="hdr">
      <h2>Live Cameras</h2>
      <span class="hint">Click a camera to open the single view</span>
    </div>
    <div id="camera-grid" class="camera-grid"></div>
  </div>

  <div class="camera-focus hidden" id="camera-focus">
    <div class="focus-head">
      <h2 id="focus-title">Camera</h2>
      <button class="btn" type="button" onclick="closeCameraFocus()">Back to all cameras</button>
    </div>
    <div class="camera-visual">
      <img id="focus-stream" alt="Selected live camera">
      <canvas id="focus-zone-overlay" class="zone-overlay"></canvas>
    </div>
  </div>

  <div class="section" id="sources" data-view="sources">
    <div class="hdr">
      <div>
        <h2>Camera / Video Sources</h2>
        <p class="hint">Add RTSP, ONVIF, or MP4 sources. Active sources appear in Live Cameras above.</p>
      </div>
    </div>
    <div id="source-setup-notice" class="source-notice hidden">
      Connector installation is incomplete. Uninstall and run the installer again;
      setup codes are accepted only once during the native installation.
    </div>
    <div class="source-toolbar hidden" id="source-toolbar">
      <label class="check-all"><input id="select-all-sources" type="checkbox"> Select all sources</label>
      <button class="btn danger" type="button" id="remove-selected">Remove selected</button>
    </div>
    <div id="saved-sources" class="v">Loading configured sources...</div>
    <div class="source-types" id="source-types">
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

  <div class="section" id="logs" data-view="logs">
    <h2>Logs</h2>
    <pre id="logs"></pre>
  </div>
  <div class="section" id="about" data-view="about">
    <h2>About ONEVO Connector</h2>
    <div class="grid" id="about-grid"></div>
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
    const localPageId = `${{Date.now()}}-${{Math.random()}}`;
    const localPageChannel = typeof BroadcastChannel === 'undefined'
      ? null : new BroadcastChannel('onevo-local-page');
    let ownsLivePreview = document.hasFocus();
    function showView(view) {{
      const selected = view || 'dashboard';
      document.querySelectorAll('.section[data-view]').forEach(section =>
        section.classList.toggle('view-hidden', section.dataset.view !== selected)
      );
      document.querySelectorAll('.local-nav a[data-view]').forEach(link =>
        link.classList.toggle('active', link.dataset.view === selected)
      );
      if (selected === 'zones') openZoneEditor();
      if (selected === 'live') loadSources();
      if (selected === 'about') loadAbout();
    }}
    function loadAbout() {{
      fetch('/setup/wizard/status').then(response => response.json()).then(data => {{
        const entries = [
          ['Version', data.version || '—'], ['Connector ID', data.connectorId || '—'],
          ['Backend', data.backendUrl || '—'], ['Paired', data.claimed ? 'Yes' : 'No'],
        ];
        document.getElementById('about-grid').innerHTML = entries.map(([key, value]) =>
          `<div class="k">${{key}}</div><div class="v">${{value}}</div>`
        ).join('');
      }}).catch(() => {{}});
    }}
    document.querySelectorAll('.local-nav a[data-view]').forEach(link => {{
      link.addEventListener('click', event => {{
        event.preventDefault();
        const view = link.dataset.view;
        history.replaceState(null, '', `#${{view}}`);
        showView(view);
      }});
    }});

    function stopLivePreviews() {{
      document.querySelectorAll('#camera-grid img').forEach(image => image.removeAttribute('src'));
      document.getElementById('camera-focus').classList.add('hidden');
      document.getElementById('focus-stream').removeAttribute('src');
    }}
    function setLivePreviewOwner(active) {{
      if (ownsLivePreview === active) return;
      ownsLivePreview = active;
      if (!active) {{
        stopLivePreviews();
        const grid = document.getElementById('camera-grid');
        if (grid) grid.textContent = 'Live preview is active in another ONEVO Connector tab.';
        return;
      }}
      loadSources().catch(() => {{}});
    }}
    if (localPageChannel) {{
      localPageChannel.onmessage = event => {{
        if (event.data && event.data.type === 'active' && event.data.id !== localPageId)
          setLivePreviewOwner(false);
      }};
    }}
    function activateLocalPage() {{
      setLivePreviewOwner(true);
      if (localPageChannel) localPageChannel.postMessage({{type:'active', id:localPageId}});
    }}
    window.addEventListener('focus', activateLocalPage);
    window.addEventListener('blur', () => setLivePreviewOwner(false));
    document.addEventListener('visibilitychange', () => {{
      if (document.visibilityState === 'visible') activateLocalPage();
      else setLivePreviewOwner(false);
    }});
    window.addEventListener('message', event => {{
      if (event.origin !== window.location.origin || !event.data) return;
      if (event.data.type === 'onevo-zones-changed' && event.data.cameraId) {{
        zoneOverlayCache.delete(event.data.cameraId);
        document.querySelectorAll(`.zone-overlay[data-camera-id="${{event.data.cameraId}}"]`)
          .forEach(overlay => loadZoneOverlay(event.data.cameraId, overlay));
        return;
      }}
      if (event.data.type === 'onevo-zones-complete') closeZoneEditor();
    }});

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
      const el = document.getElementById('saved-sources');
      const toolbar = document.getElementById('source-toolbar');
      const sourceTypes = document.getElementById('source-types');
      const notice = document.getElementById('source-setup-notice');
      try {{
        const response = await fetch('/sources');
        const data = await response.json().catch(() => ({{}}));
        if (!response.ok) throw new Error(data.detail || data.error || 'Could not load configured sources');
        sourceTypes.classList.toggle('hidden', !data.managementReady);
        notice.classList.toggle('hidden', data.managementReady);
        document.getElementById('source-form').classList.toggle(
          'hidden', !data.managementReady);
        renderCameraGrid(data.sources);
        if (!data.sources.length) {{
          toolbar.classList.add('hidden');
          el.innerHTML = data.managementReady
            ? '<div class="hint">No sources yet. Choose RTSP, ONVIF, or MP4 below.</div>'
            : '<div class="hint">Sources can be added after connector setup is complete.</div>';
          return;
        }}
        toolbar.classList.remove('hidden');
        el.innerHTML = '';
        data.sources.forEach((source, index) => {{
          const row = document.createElement('div');
          row.className = 'source-card';
          const select = document.createElement('input');
          select.type = 'checkbox';
          select.className = 'saved-source-select';
          select.value = source.sourceKey;
          const text = document.createElement('div');
          const title = document.createElement('div');
          title.className = 'source-title';
          title.textContent = source.name;
          const detail = document.createElement('div');
          detail.className = 'source-detail';
          detail.textContent = `${{source.type.toUpperCase()}} · ${{source.value}}`;
          text.append(title, detail);
          const remove = document.createElement('button');
          remove.type = 'button';
          remove.className = 'btn';
          remove.textContent = 'Remove';
          remove.onclick = () => removeSavedSource(source.sourceKey);
          const edit = document.createElement('button');
          edit.type = 'button';
          edit.className = 'btn';
          edit.textContent = 'Edit name';
          edit.onclick = () => editSavedSource(source);
          const actions = document.createElement('div');
          actions.className = 'row';
          actions.style.margin = '0';
          actions.append(edit, remove);
          row.append(select, text, actions);
          el.appendChild(row);
        }});
        document.getElementById('select-all-sources').checked = false;
      }} catch (error) {{
        toolbar.classList.add('hidden');
        el.textContent = 'Could not load sources: ' + error.message;
        document.getElementById('camera-grid').textContent =
          'Local dashboard is reconnecting. Use the tray icon to start monitoring if this persists.';
      }}
    }}
    async function editSavedSource(source) {{
      const name = prompt('Source name', source.name || '');
      if (name === null || !name.trim() || name.trim() === source.name) return;
      try {{
        const response = await fetch(`/sources/${{encodeURIComponent(source.sourceKey)}}`, {{
          method:'PUT', headers:{{'Content-Type':'application/json'}},
          body:JSON.stringify({{name:name.trim()}})
        }});
        const data = await response.json().catch(() => ({{}}));
        if (!response.ok) throw new Error(data.detail || 'Could not update source');
        showActionMsg('Source updated. Reconnecting the camera…');
        loadSources();
      }} catch (error) {{ showActionMsg(error.message, true); }}
    }}
    function renderCameraGrid(sources) {{
      const grid = document.getElementById('camera-grid');
      grid.innerHTML = '';
      if (!ownsLivePreview) {{
        grid.textContent = 'Live preview is active in another ONEVO Connector tab.';
        return;
      }}
      if (!document.getElementById('camera-focus').classList.contains('hidden')) {{
        grid.textContent = 'Single camera view is open.';
        return;
      }}
      const seenCameraIds = new Set();
      const active = sources.filter(source => source.cameraId && !seenCameraIds.has(source.cameraId) &&
        (seenCameraIds.add(source.cameraId) || true));
      if (!active.length) {{
        grid.textContent = 'No active camera feeds yet.';
        return;
      }}
      active.forEach(source => {{
        const tile = document.createElement('div');
        tile.className = 'camera-tile';
        tile.onclick = () => openCameraFocus(source);
        const visual = document.createElement('div');
        visual.className = 'camera-visual';
        const img = document.createElement('img');
        img.src = `/live/cameras/${{encodeURIComponent(source.cameraId)}}/stream.mjpg`;
        img.alt = source.name;
        const overlay = document.createElement('canvas');
        overlay.className = 'zone-overlay';
        overlay.dataset.cameraId = source.cameraId;
        img.addEventListener('load', () => redrawZoneOverlay(source.cameraId, overlay));
        new ResizeObserver(() => redrawZoneOverlay(source.cameraId, overlay)).observe(visual);
        visual.append(img, overlay);
        loadZoneOverlay(source.cameraId, overlay);
        const meta = document.createElement('div');
        meta.className = 'meta';
        const name = document.createElement('strong');
        name.textContent = source.name;
        const kind = document.createElement('span');
        kind.textContent = source.type.toUpperCase();
        meta.append(name, kind);
        tile.append(visual, meta);
        grid.appendChild(tile);
      }});
    }}
    const zoneOverlayCache = new Map();
    function zoneColor(zone) {{
      const type = zone.zoneType || zone.ZoneType || '';
      if (type === 'HighValue') return ['rgba(255,120,120,.30)', '#ff7878'];
      if (type === 'Exit') return ['rgba(255,190,80,.28)', '#ffbe50'];
      if (type === 'BlindSpot') return ['rgba(180,120,255,.28)', '#b478ff'];
      if (type === 'Checkout') return ['rgba(92,219,127,.27)', '#5cdb7f'];
      return ['rgba(120,160,255,.28)', '#78a0ff'];
    }}
    function zonePoints(zone) {{
      try {{
        const raw = zone.polygonJson || zone.PolygonJson || zone.polygon || [];
        const points = typeof raw === 'string' ? JSON.parse(raw) : raw;
        if (!Array.isArray(points)) return [];
        return points.map(point => Array.isArray(point)
          ? [Number(point[0]), Number(point[1])]
          : [Number(point.x ?? point.X), Number(point.y ?? point.Y)]
        ).filter(point => Number.isFinite(point[0]) && Number.isFinite(point[1]));
      }} catch (_) {{ return []; }}
    }}
    function drawZoneOverlay(canvas, zones) {{
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(1, Math.round(rect.width));
      const height = Math.max(1, Math.round(rect.height));
      if (canvas.width !== width || canvas.height !== height) {{
        canvas.width = width; canvas.height = height;
      }}
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, width, height);
      zones.forEach(zone => {{
        const points = zonePoints(zone);
        if (!Array.isArray(points) || points.length < 3) return;
        const [fill, stroke] = zoneColor(zone);
        ctx.beginPath();
        ctx.moveTo(points[0][0] * width, points[0][1] * height);
        points.slice(1).forEach(point => ctx.lineTo(point[0] * width, point[1] * height));
        ctx.closePath();
        ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2;
        ctx.fill(); ctx.stroke();
      }});
    }}
    function redrawZoneOverlay(cameraId, canvas) {{
      drawZoneOverlay(canvas, zoneOverlayCache.get(cameraId) || []);
    }}
    async function loadZoneOverlay(cameraId, canvas) {{
      try {{
        const response = await fetch(`/live/cameras/${{encodeURIComponent(cameraId)}}/zones`);
        if (!response.ok) return;
        const zones = await response.json();
        zoneOverlayCache.set(cameraId, Array.isArray(zones) ? zones : []);
        redrawZoneOverlay(cameraId, canvas);
      }} catch (_) {{}}
    }}
    function openCameraFocus(source) {{
      if (!ownsLivePreview) return;
      stopLivePreviews();
      document.getElementById('camera-grid').textContent = 'Single camera view is open.';
      document.getElementById('focus-title').textContent = source.name;
      const stream = document.getElementById('focus-stream');
      stream.src =
        `/live/cameras/${{encodeURIComponent(source.cameraId)}}/stream.mjpg?t=${{Date.now()}}`;
      const overlay = document.getElementById('focus-zone-overlay');
      overlay.dataset.cameraId = source.cameraId;
      stream.onload = () => redrawZoneOverlay(source.cameraId, overlay);
      loadZoneOverlay(source.cameraId, overlay);
      document.getElementById('camera-focus').classList.remove('hidden');
      new ResizeObserver(() => redrawZoneOverlay(source.cameraId, overlay))
        .observe(document.getElementById('camera-focus').querySelector('.camera-visual'));
    }}
    function closeCameraFocus() {{
      document.getElementById('camera-focus').classList.add('hidden');
      document.getElementById('focus-stream').removeAttribute('src');
      const overlay = document.getElementById('focus-zone-overlay');
      overlay.getContext('2d').clearRect(0, 0, overlay.width, overlay.height);
      loadSources();
    }}
    async function removeSavedSource(sourceKey) {{
      if (!confirm('Remove this camera/video source?')) return;
      const response = await fetch(`/sources/by-key/${{encodeURIComponent(sourceKey)}}`, {{method:'DELETE'}});
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
    document.getElementById('select-all-sources').onchange = event => {{
      document.querySelectorAll('.saved-source-select').forEach(box => {{
        box.checked = event.target.checked;
      }});
    }};
    document.getElementById('remove-selected').onclick = async () => {{
      const keys = [...document.querySelectorAll('.saved-source-select:checked')]
        .map(box => box.value).filter(Boolean);
      if (!keys.length) {{
        document.getElementById('source-msg').textContent = 'Select at least one source.';
        return;
      }}
      if (!confirm(`Remove ${{keys.length}} selected source(s)?`)) return;
      const response = await fetch('/sources/bulk-delete', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{source_keys: keys}})
      }});
      const data = await response.json();
      document.getElementById('source-msg').textContent = response.ok
        ? `Removed ${{data.removed}} source(s).`
        : (data.detail || 'Could not remove selected sources');
      if (response.ok) await loadSources();
    }};
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
        openZoneEditor();
        event.target.reset();
        document.getElementById('source-rows').innerHTML = '';
        document.getElementById('source-form').classList.remove('on');
        selectedSourceType = '';
      }} catch (error) {{
        msg.textContent = error.message;
      }}
    }};
    function openZoneEditor() {{
      const section = document.getElementById('zone-editor-section');
      section.classList.remove('hidden');
      // Zone editing uses a single snapshot for the selected camera. Keep all
      // normal live tiles running so operators can monitor other cameras.
      loadNativeZoneEditor();
      if (window.location.hash !== '#zones') history.replaceState(null, '', '#zones');
      section.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}
    function refreshZoneEditor() {{
      loadNativeZoneFrame();
    }}
    function closeZoneEditor() {{
      const section = document.getElementById('zone-editor-section');
      section.classList.add('hidden');
      loadSources();
      document.getElementById('live-cameras-section').scrollIntoView({{behavior:'smooth', block:'start'}});
    }}
    let nativeZoneCameras=[], nativeZones=[], nativePoints=[], nativeSelected=null, nativeFrame=null;
    let nativeDrawing=false, nativeDragPoint=null, nativeDrawStart=null, nativeResizeAnchor=null, nativeMoveStart=null, nativeMovePoints=[];
    const nativeCanvas=document.getElementById('zoneCanvas'), nativeCtx=nativeCanvas.getContext('2d');
    function nativeZonePoints(zone) {{
      try {{ return JSON.parse(zone.polygonJson || zone.PolygonJson || '[]'); }} catch {{ return []; }}
    }}
    function drawNativeZones() {{
      nativeCtx.clearRect(0,0,nativeCanvas.width,nativeCanvas.height);
      if (nativeFrame) nativeCtx.drawImage(nativeFrame,0,0,nativeCanvas.width,nativeCanvas.height);
      const draw=(points,color,editable=false)=>{{
        if(!points.length)return;
        nativeCtx.beginPath(); nativeCtx.moveTo(points[0][0]*nativeCanvas.width,points[0][1]*nativeCanvas.height);
        points.slice(1).forEach(p=>nativeCtx.lineTo(p[0]*nativeCanvas.width,p[1]*nativeCanvas.height));
        if(points.length>2) nativeCtx.closePath();
        nativeCtx.fillStyle=color+'44'; nativeCtx.strokeStyle=color; nativeCtx.lineWidth=2; nativeCtx.fill(); nativeCtx.stroke();
        if(editable) points.forEach(p=>{{nativeCtx.beginPath();nativeCtx.arc(p[0]*nativeCanvas.width,p[1]*nativeCanvas.height,5,0,Math.PI*2);nativeCtx.fillStyle=color;nativeCtx.fill();nativeCtx.strokeStyle='#fff';nativeCtx.stroke();}});
      }};
      nativeZones.forEach(zone=>draw(nativeZonePoints(zone),zone===nativeSelected?'#ffd36a':'#6ea8ff'));
      draw(nativePoints,'#ffd36a',true);
    }}
    function nativePoint(event) {{
      const rect=nativeCanvas.getBoundingClientRect();
      return [Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))];
    }}
    function nativePointInPolygon(point, polygon) {{
      let inside=false;
      for(let i=0,j=polygon.length-1;i<polygon.length;j=i++) {{
        const [xi,yi]=polygon[i], [xj,yj]=polygon[j];
        if(((yi>point[1]) !== (yj>point[1])) &&
           (point[0] < (xj-xi)*(point[1]-yi)/(yj-yi)+xi)) inside=!inside;
      }}
      return inside;
    }}
    function setNativeRectangle(start, end) {{
      const left=Math.min(start[0],end[0]), right=Math.max(start[0],end[0]);
      const top=Math.min(start[1],end[1]), bottom=Math.max(start[1],end[1]);
      nativePoints=[[left,top],[right,top],[right,bottom],[left,bottom]];
    }}
    function simplifyNativeFreehand(raw, tolerance=.012) {{
      if(raw.length<=4) return raw;
      const simplify=(points)=>{{
        if(points.length<=2) return points;
        const first=points[0], last=points[points.length-1];
        const dx=last[0]-first[0], dy=last[1]-first[1], denominator=dx*dx+dy*dy || 1;
        let maxDistance=0, pivot=0;
        for(let i=1;i<points.length-1;i++) {{
          const t=Math.max(0,Math.min(1,((points[i][0]-first[0])*dx+(points[i][1]-first[1])*dy)/denominator));
          const px=first[0]+t*dx, py=first[1]+t*dy;
          const distance=Math.hypot(points[i][0]-px,points[i][1]-py);
          if(distance>maxDistance) {{ maxDistance=distance;pivot=i; }}
        }}
        return maxDistance>tolerance
          ? simplify(points.slice(0,pivot+1)).slice(0,-1).concat(simplify(points.slice(pivot)))
          : [first,last];
      }};
      const result=simplify(raw);
      return result.length>=3 ? result : raw.slice(0,3);
    }}
    function nativeResetZone() {{
      nativeSelected=null;nativePoints=[];nativeDragPoint=null;nativeDrawStart=null;nativeResizeAnchor=null;nativeDrawing=false;nativeMoveStart=null;nativeMovePoints=[];
      document.getElementById('zoneName').value='';document.getElementById('zoneDelete').disabled=true;drawNativeZones();
    }}
    function renderNativeZoneList() {{
      document.getElementById('zoneList').innerHTML=nativeZones.map(z=>`<button class="btn" data-id="${{z.id||z.Id}}">${{z.name||z.Name}}</button>`).join('')||'<span class="hint">No saved zones for this camera.</span>';
      document.querySelectorAll('#zoneList button').forEach(button=>button.onclick=()=>{{
        nativeSelected=nativeZones.find(z=>(z.id||z.Id)===button.dataset.id);nativePoints=nativeZonePoints(nativeSelected);
        document.getElementById('zoneName').value=nativeSelected.name||nativeSelected.Name||'';
        document.getElementById('zoneType').value=nativeSelected.zoneType||nativeSelected.ZoneType||'Entrance';
        document.getElementById('zoneDelete').disabled=false;drawNativeZones();
      }});
    }}
    async function loadNativeZoneCamera() {{
      const id=document.getElementById('zoneCamera').value;if(!id)return;
      nativeResetZone();
      try {{ nativeZones=await (await fetch(`/setup/wizard/cameras/${{encodeURIComponent(id)}}/zones`)).json();renderNativeZoneList();loadNativeZoneFrame(); }}
      catch(error) {{ document.getElementById('zoneMsg').textContent=error.message; }}
    }}
    function loadNativeZoneFrame() {{
      const id=document.getElementById('zoneCamera').value;if(!id)return;
      const image=new Image();
      image.onload=()=>{{nativeFrame=image;drawNativeZones();document.getElementById('zoneMsg').textContent='Frame ready. Drag on the frame to draw; drag a point to refine.';}};
      image.onerror=()=>document.getElementById('zoneMsg').textContent='Could not load a camera frame.';
      image.src=`/setup/snapshot?camera_id=${{encodeURIComponent(id)}}&t=${{Date.now()}}`;
    }}
    async function loadNativeZoneEditor() {{
      const sourceData=await (await fetch('/sources')).json();
      nativeZoneCameras=(sourceData.sources||[]).filter(source=>source.cameraId);
      const select=document.getElementById('zoneCamera');
      const prior=select.value;select.innerHTML=nativeZoneCameras.map((source,index)=>`<option value="${{source.cameraId}}">${{source.name||`Camera ${{index+1}}`}}</option>`).join('');
      if(prior && nativeZoneCameras.some(source=>source.cameraId===prior))select.value=prior;
      await loadNativeZoneCamera();
    }}
    nativeCanvas.onpointerdown=event=>{{
      if(event.button!==0)return;const point=nativePoint(event);
      const index=nativePoints.findIndex(p=>Math.hypot(p[0]-point[0],p[1]-point[1])<.025);
      nativeCanvas.setPointerCapture(event.pointerId);
      if(index>=0 && nativePoints.length===4){{nativeDragPoint=index;nativeResizeAnchor=nativePoints[(index+2)%nativePoints.length];nativeCanvas.style.cursor='nwse-resize';return;}}
      if(nativePoints.length>=3 && nativePointInPolygon(point,nativePoints)) {{
        nativeMoveStart=point;nativeMovePoints=nativePoints.map(p=>[...p]);nativeCanvas.style.cursor='move';return;
      }}
      nativeSelected=null;nativeDrawStart=point;setNativeRectangle(point,point);nativeDrawing=true;document.getElementById('zoneDelete').disabled=true;drawNativeZones();
    }};
    nativeCanvas.onpointermove=event=>{{
      const point=nativePoint(event);
      if(nativeDragPoint!==null){{setNativeRectangle(nativeResizeAnchor,point);drawNativeZones();}}
      else if(nativeMoveStart){{const dx=point[0]-nativeMoveStart[0],dy=point[1]-nativeMoveStart[1];nativePoints=nativeMovePoints.map(p=>[Math.max(0,Math.min(1,p[0]+dx)),Math.max(0,Math.min(1,p[1]+dy))]);drawNativeZones();}}
      else if(nativeDrawing){{setNativeRectangle(nativeDrawStart,point);drawNativeZones();}}
    }};
    nativeCanvas.onpointerup=event=>{{if(nativeCanvas.hasPointerCapture(event.pointerId))nativeCanvas.releasePointerCapture(event.pointerId);nativeDragPoint=null;nativeDrawStart=null;nativeResizeAnchor=null;nativeDrawing=false;nativeMoveStart=null;nativeMovePoints=[];nativeCanvas.style.cursor='crosshair';drawNativeZones();}};
    nativeCanvas.onpointercancel=()=>{{nativeDragPoint=null;nativeDrawStart=null;nativeResizeAnchor=null;nativeDrawing=false;nativeMoveStart=null;nativeMovePoints=[];nativeCanvas.style.cursor='crosshair';drawNativeZones();}};
    document.getElementById('zoneCamera').onchange=loadNativeZoneCamera;
    document.getElementById('zoneNew').onclick=nativeResetZone;
    document.getElementById('zoneUndo').onclick=()=>{{nativePoints.pop();drawNativeZones();}};
    document.getElementById('zoneSave').onclick=async()=>{{
      const id=document.getElementById('zoneCamera').value,name=document.getElementById('zoneName').value.trim();
      if(!id||!name||nativePoints.length<3){{document.getElementById('zoneMsg').textContent='Enter a name and draw an area with at least three points.';return;}}
      const response=await fetch(`/setup/wizard/cameras/${{encodeURIComponent(id)}}/zones`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{zoneId:nativeSelected&&(nativeSelected.id||nativeSelected.Id),name,zoneType:document.getElementById('zoneType').value,polygon:nativePoints}})}});
      if(!response.ok){{document.getElementById('zoneMsg').textContent=await response.text();return;}}
      zoneOverlayCache.delete(id);nativeResetZone();await loadNativeZoneCamera();document.getElementById('zoneMsg').textContent='Zone saved and applied to live detection.';
    }};
    document.getElementById('zoneDelete').onclick=async()=>{{
      if(!nativeSelected)return;const id=document.getElementById('zoneCamera').value;
      await fetch(`/setup/wizard/zones/${{nativeSelected.id||nativeSelected.Id}}`,{{method:'DELETE'}});
      zoneOverlayCache.delete(id);nativeResetZone();await loadNativeZoneCamera();
    }};
    document.getElementById('zoneFinish').onclick=async()=>{{
      const response=await fetch('/setup/wizard/zones/finish',{{method:'POST'}}),data=await response.json().catch(()=>({{}}));
      if(!response.ok){{document.getElementById('zoneMsg').textContent=data.detail||'Save a zone for every camera first.';return;}}
      document.getElementById('zoneMsg').textContent='Setup complete. Monitoring is ready.';closeZoneEditor();
    }};
    window.addEventListener('hashchange', () => {{
      showView(window.location.hash.slice(1) || 'dashboard');
    }});
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
      if (!s.paired && reason && (/setup code|activation|configured yet|pairing/i.test(reason))) {{
        return {{
          title: 'Installation incomplete',
          text: 'This connector was not paired during installation. Uninstall it and run the installer again.',
          setup: false,
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
      try {{
        const result = await postJson('/capture/pause');
        showActionMsg(result.message || 'Monitoring stopped');
        setCaptureButtons(true);
      }}
      catch(e) {{ showActionMsg(e.message, true); }}
    }}
    async function resumeCapture() {{
      try {{
        await postJson('/capture/resume');
        showActionMsg('Monitoring started');
        setCaptureButtons(false);
        tick();
      }}
      catch(e) {{ showActionMsg(e.message, true); }}
    }}
    function setCaptureButtons(paused) {{
      document.getElementById('btn-pause').disabled = paused;
      document.getElementById('btn-resume').disabled = !paused;
      document.getElementById('btn-trigger').disabled = paused;
      document.getElementById('btn-upload-source').disabled = paused;
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
        const s = await (await fetch('/setup/wizard/status')).json();
        setCaptureButtons(Boolean(s.capturePaused));
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
        if (banner && alertText) {{
          const alert = classifyAlert(s);
          if (alert) {{
            banner.classList.remove('hidden');
            banner.style.cssText = alert.style;
            if (alertTitle) alertTitle.textContent = alert.title;
            alertText.textContent = alert.text;
          }} else {{
            banner.classList.add('hidden');
          }}
        }}
        if (
          /^Camera setup is ready\\./.test(s.degradedReason || '') &&
          window.location.hash !== '#zones' &&
          !window.onevoAutoOpenedZones
        ) {{
          window.onevoAutoOpenedZones = true;
          history.replaceState(null, '', '#zones');
          showView('zones');
        }}
        document.getElementById('tick').textContent = 'updated ' + new Date().toLocaleTimeString();
        refreshLocalClips();
      }} catch(e) {{ document.getElementById('tick').textContent = 'fetch error'; }}
    }}
    loadClipSettings();
    window.addEventListener('resize', () => {{
      document.querySelectorAll('.zone-overlay').forEach(overlay => {{
        if (overlay.dataset.cameraId) redrawZoneOverlay(overlay.dataset.cameraId, overlay);
      }});
    }});
    setInterval(tick, 1500);
    setInterval(loadSources, 5000);
    setInterval(() => {{
      document.querySelectorAll('.zone-overlay[data-camera-id]').forEach(overlay =>
        loadZoneOverlay(overlay.dataset.cameraId, overlay)
      );
    }}, 5000);
    tick();
    loadSources();
    showView(window.location.hash.slice(1) || 'dashboard');
  </script>
</body>
</html>"""

    return app


def start_admin(
    state: RuntimeState,
    cfg: "Config",
    port: int,
    client: "BackendClient | None" = None,
    store: "LocalStore | None" = None,
    enable_setup_wizard: bool = False,
    on_wizard_configured: Callable | None = None,
) -> threading.Thread:
    from .backend_client import BackendClient

    client: BackendClient | None = None
    if store is not None:
        client = BackendClient(cfg.backend_url)
        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if connector_id and api_key:
            client.set_credentials(connector_id, api_key)

    app = build_app(
        state,
        cfg,
        client=client,
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
    # Management and live-preview endpoints stay local by default. LAN exposure
    # must be an explicit deployment choice.
    admin_host = os.getenv("CONNECTOR_ADMIN_HOST", "127.0.0.1").strip() or "127.0.0.1"
    config = uvicorn.Config(app, host=admin_host, port=port, log_level="warning")
    config = uvicorn.Config(app, host=cfg.admin_bind_host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return t

