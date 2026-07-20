"""ONEVO Local Connector entrypoint.

Flow: (optional ONVIF query) -> register (once) ->
start admin UI + uploader + heartbeat threads ->
capture loop cuts event clips -> clips enqueued to durable SQLite queue ->
uploaded to the cloud via short-lived signed URLs.

ONVIF mode: if --onvif-host (or CONNECTOR_ONVIF_HOST env) is set the connector
auto-discovers the RTSP URL and device info from the camera before starting
capture — no manual rtsp:// URL needed.
"""
import sys
import threading

from .admin import start_admin
from .backend_client import BackendClient
from .capture import CapturePipeline
from .config import load_config
from .runtime import RuntimeState
from .store import LocalStore
from .workers import run_heartbeat, run_uploader


# ---------------------------------------------------------------------------
# ONVIF startup helper
# ---------------------------------------------------------------------------

def _resolve_via_onvif(cfg, state: RuntimeState) -> None:
    """If onvif_host is configured, fetch RTSP URL + device info via ONVIF.

    Updates cfg.source in-place and populates state ONVIF fields.
    Non-fatal: on any error the connector falls back to cfg.source as-is.
    """
    if not cfg.onvif_host:
        return  # ONVIF not configured — use --source as-is

    try:
        from .onvif_client import OnvifCamera
    except ImportError:
        state.log("WARNING: onvif_client not available — using --source as-is")
        return

    state.log(
        f"ONVIF: connecting to {cfg.onvif_host}:{cfg.onvif_port} "
        f"as '{cfg.onvif_user}' …"
    )
    try:
        cam = OnvifCamera()
        cam.connect(
            host=cfg.onvif_host,
            port=cfg.onvif_port,
            username=cfg.onvif_user,
            password=cfg.onvif_pass,
        )

        # ---- Device info ----
        info = cam.get_device_info()
        state.camera_manufacturer = info.manufacturer
        state.camera_model = info.model
        state.camera_serial = info.serial
        state.camera_firmware = info.firmware
        state.log(
            f"ONVIF device: {info.manufacturer} {info.model} "
            f"[S/N {info.serial}] fw={info.firmware}"
        )

        # ---- Stream profiles ----
        profiles = cam.get_profiles()
        state.onvif_profiles = [
            {"token": p.token, "name": p.name,
             "encoding": p.encoding, "width": p.width, "height": p.height}
            for p in profiles
        ]

        # ---- RTSP URL ----
        profile_token = None if cfg.onvif_profile == "auto" else cfg.onvif_profile
        rtsp_url = cam.get_rtsp_url(profile_token)
        state.log(f"ONVIF RTSP URL → {rtsp_url}")
        cfg.source = rtsp_url          # override --source with the auto-fetched URL

    except Exception as exc:  # noqa: BLE001
        state.log(f"ONVIF error (falling back to --source): {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config()
    state = RuntimeState()
    state.source = cfg.source
    state.camera_id = cfg.camera_id

    # ONVIF: auto-resolve RTSP URL + device info if camera_id is set.
    if cfg.camera_id:
        _resolve_via_onvif(cfg, state)
        state.source = cfg.source   # update after possible ONVIF override

    store = LocalStore(cfg.state_dir)
    client = BackendClient(cfg.backend_url)

    # Reuse stored credentials if we already registered; otherwise register now.
    cid = store.get_cred("connector_id")
    key = store.get_cred("api_key")
    if cid and key:
        client.set_credentials(cid, key)
        state.log(f"Loaded existing connector credentials ({cid})")
    else:
        if not cfg.store_id:
            state.log("ERROR: first run needs --store-id to register.")
            return 2
        try:
            cid, key = client.register(cfg.store_id, cfg.connector_name, cfg.version, cfg.bootstrap_key)
        except Exception as e:  # noqa: BLE001
            state.log(f"ERROR: registration failed: {e}")
            return 1
        store.set_cred("connector_id", cid)
        store.set_cred("api_key", key)
        state.log(f"Registered connector {cid}")
    state.connector_id = client.connector_id

    # Push ONVIF device info to backend (best-effort).
    if state.camera_model and cfg.camera_id:
        try:
            client.update_device_info(cfg.camera_id, {
                "manufacturer": state.camera_manufacturer,
                "model": state.camera_model,
                "serial": state.camera_serial,
                "firmware": state.camera_firmware,
                "onvifHost": cfg.onvif_host,
                "onvifPort": cfg.onvif_port,
                "rtspUrl": cfg.source,
            })
            state.log("Device info pushed to backend")
        except Exception as exc:  # noqa: BLE001
            state.log(f"WARNING: could not push device info: {exc}")

    stop = threading.Event()
    start_admin(state, cfg, cfg.admin_port)
    state.log(f"Admin UI on http://localhost:{cfg.admin_port}")

    up = threading.Thread(target=run_uploader, args=(cfg, client, store, state, stop), daemon=True)
    hb = threading.Thread(target=run_heartbeat, args=(cfg, client, store, state, stop), daemon=True)
    up.start()
    hb.start()

    if cfg.camera_id:
        # Backward compatibility / single camera mode
        pipeline = CapturePipeline(cfg, state)

        def on_clip(path: str, duration: float, trigger: str) -> None:
            store.enqueue(path, cfg.camera_id, duration, trigger)
            state.queue_depth = store.pending_count()

        try:
            pipeline.run(on_clip)
        except KeyboardInterrupt:
            state.log("Shutting down (Ctrl-C)")
        finally:
            stop.set()
            pipeline.stop()
    else:
        # Multi-camera orchestrator mode
        from .orchestrator import StoreOrchestrator
        orch = StoreOrchestrator(cfg, state, client, store)
        try:
            orch.run()
        except KeyboardInterrupt:
            state.log("Shutting down (Ctrl-C)")
        finally:
            stop.set()
            orch.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
