"""ONEVO Local Connector entrypoint.

Flow: (optional ONVIF query) -> register (once) ->
start admin UI + uploader + heartbeat threads ->
capture loop cuts event clips -> clips enqueued to durable SQLite queue ->
uploaded to the cloud via short-lived signed URLs.

ONVIF mode: if --onvif-host (or CONNECTOR_ONVIF_HOST env) is set the connector
auto-discovers the RTSP URL and device info from the camera before starting
capture Ã¢â‚¬â€ no manual rtsp:// URL needed.

Installer modes:
  --wizard   first-run setup UI (setup code + RTSP / MP4)
  --service  Windows service: load ProgramData config and monitor continuously
"""
import sys
import threading
import time
from pathlib import Path

from .admin import start_admin
from .backend_client import BackendClient
from .capture import CapturePipeline
from .config import load_config
from .paths import load_wizard_config
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
        return  # ONVIF not configured Ã¢â‚¬â€ use --source as-is

    try:
        from .onvif_client import OnvifCamera
    except ImportError:
        state.log("WARNING: onvif_client not available Ã¢â‚¬â€ using --source as-is")
        return

    state.log(
        f"ONVIF: connecting to {cfg.onvif_host}:{cfg.onvif_port} "
        f"as '{cfg.onvif_user}' Ã¢â‚¬Â¦"
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
        state.log(f"ONVIF RTSP URL Ã¢â€ â€™ {rtsp_url}")
        cfg.source = rtsp_url          # override --source with the auto-fetched URL

    except Exception as exc:  # noqa: BLE001
        state.log(f"ONVIF error (falling back to --source): {exc}")


def _ensure_registered(cfg, client: BackendClient, store: LocalStore, state: RuntimeState) -> bool:
    """Load or register connector credentials. Returns False on hard failure."""
    cid = store.get_cred("connector_id")
    key = store.get_cred("api_key")
    if cid and key:
        client.set_credentials(cid, key)
        state.log(f"Loaded existing connector credentials ({cid})")
        state.connector_id = client.connector_id
        return True

    if not cfg.store_id:
        state.log("ERROR: first run needs --store-id (or complete the setup wizard).")
        return False
    try:
        cid, key = client.register(cfg.store_id, cfg.connector_name, cfg.version, cfg.bootstrap_key)
    except Exception as e:  # noqa: BLE001
        state.log(f"ERROR: registration failed: {e}")
        return False
    store.set_cred("connector_id", cid)
    store.set_cred("api_key", key)
    state.log(f"Registered connector {cid}")
    state.connector_id = client.connector_id
    return True


def _run_capture(cfg, client: BackendClient, store: LocalStore, state: RuntimeState, stop: threading.Event) -> int:
    if cfg.camera_id:
        _resolve_via_onvif(cfg, state)
        state.source = cfg.source
        state.camera_id = cfg.camera_id

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


def _run_wizard_only(cfg, state: RuntimeState, store: LocalStore) -> int:
    from .wizard import open_wizard_browser, start_wizard

    state.log(f"Setup wizard on http://127.0.0.1:{cfg.admin_port}/")
    start_wizard(state, cfg, store, cfg.admin_port)
    open_wizard_browser(cfg.admin_port)
    try:
        while True:
            time.sleep(1)
            w = load_wizard_config()
            if w and w.setup_complete:
                state.log("Wizard complete Ã¢â‚¬â€ you can close this window; the service will monitor.")
                # Let the browser receive the final response before the installer continues.
                time.sleep(2)
                break
    except KeyboardInterrupt:
        state.log("Wizard closed")
    return 0


def _provision_native_installer(cfg, wizard, client: BackendClient, store: LocalStore, state: RuntimeState) -> bool:
    """Claim native-installer setup and create its configured camera sources once."""
    if not wizard or wizard.setup_complete or not wizard.setup_code:
        return False
    if not wizard.sources:
        state.log("ERROR: installer configuration has no camera source")
        return False

    try:
        for source in wizard.sources:
            modes = sum(bool(value) for value in (
                source.rtsp_url, source.source_file, source.onvif_host
            ))
            if modes != 1:
                raise ValueError(f"{source.name}: configure exactly one source type")
            if source.rtsp_url and not source.rtsp_url.lower().startswith("rtsp://"):
                raise ValueError(f"{source.name}: RTSP URL must start with rtsp://")
            if source.source_file and not Path(source.source_file).is_file():
                raise ValueError(f"{source.name}: video file does not exist")
            if source.onvif_host and not (1 <= int(source.onvif_port) <= 65535):
                raise ValueError(f"{source.name}: invalid ONVIF port")

        cid, key, store_id = client.claim_setup_code(
            wizard.setup_code, wizard.connector_name, cfg.version
        )
        store.set_cred("connector_id", cid)
        store.set_cred("api_key", key)
        store.set_cred("store_id", store_id)
        created = []
        for source in wizard.sources:
            rtsp_url = source.rtsp_url
            device_info = None
            if source.onvif_host:
                from .onvif_client import OnvifCamera
                onvif = OnvifCamera().connect(
                    source.onvif_host,
                    source.onvif_port,
                    source.onvif_user or "admin",
                    source.onvif_pass,
                )
                profile = None if source.onvif_profile == "auto" else source.onvif_profile
                rtsp_url = onvif.get_rtsp_url(profile)
                device_info = onvif.get_device_info()

            camera = client.create_camera({
                "name": source.name,
                "rtspUrl": rtsp_url or f"file://{source.source_file}",
                "onvifHost": source.onvif_host or None,
                "onvifPort": source.onvif_port if source.onvif_host else None,
                "useDemoZones": bool(source.source_file),
            })
            source.camera_id = camera.get("id") or camera.get("Id") or ""
            source.rtsp_url = rtsp_url
            if device_info and source.camera_id:
                try:
                    client.update_device_info(source.camera_id, {
                        "manufacturer": device_info.manufacturer,
                        "model": device_info.model,
                        "serial": device_info.serial,
                        "firmware": device_info.firmware,
                    })
                except Exception as exc:  # noqa: BLE001
                    state.log(f"WARNING: ONVIF device info update failed: {exc}")
            created.append(source)

        wizard.sources = created
        wizard.store_id = store_id
        wizard.setup_code = ""
        for source in wizard.sources:
            source.rtsp_url = ""
            source.onvif_user = ""
            source.onvif_pass = ""
        wizard.setup_complete = True
        from .paths import save_wizard_config
        save_wizard_config(wizard)
        client.set_credentials(cid, key)
        state.connector_id = cid
        state.log(f"Native installer provisioned {len(created)} camera source(s)")
        return True
    except Exception as exc:  # noqa: BLE001
        state.log(f"ERROR: native installer activation failed: {exc}")
        return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config()
    state = RuntimeState()
    state.source = cfg.source
    state.camera_id = cfg.camera_id

    store = LocalStore(cfg.state_dir)
    client = BackendClient(cfg.backend_url)

    if cfg.wizard_mode:
        return _run_wizard_only(cfg, state, store)

    # Native installer writes a pending setup config before starting the service.
    # It must take precedence over credentials left by an older installation.
    wizard = load_wizard_config()
    if cfg.service_mode and wizard and not wizard.setup_complete and wizard.setup_code:
        if not _provision_native_installer(cfg, wizard, client, store, state):
            state.log("ERROR: installer activation failed; capture will not start with a fallback source")
            return 2
        cfg = load_config()
        state.source = cfg.source
        state.camera_id = cfg.camera_id
        client = BackendClient(cfg.backend_url)

    # Service / normal: register if needed (wizard may already have claimed).
    if not (store.get_cred("connector_id") and store.get_cred("api_key")):
        if not _ensure_registered(cfg, client, store, state):
            # Not registered yet Ã¢â‚¬â€ if installed, open wizard instead of failing hard.
            if cfg.service_mode or (wizard is None or not wizard.setup_complete):
                state.log("Not configured yet Ã¢â‚¬â€ starting setup wizard")
                return _run_wizard_only(cfg, state, store)
            return 2
    else:
        client.set_credentials(store.get_cred("connector_id"), store.get_cred("api_key"))
        state.connector_id = client.connector_id
        state.log(f"Loaded existing connector credentials ({client.connector_id})")

    stop = threading.Event()
    start_admin(state, cfg, cfg.admin_port)
    state.log(f"Admin UI on http://localhost:{cfg.admin_port}")

    up = threading.Thread(target=run_uploader, args=(cfg, client, store, state, stop), daemon=True)
    hb = threading.Thread(target=run_heartbeat, args=(cfg, client, store, state, stop), daemon=True)
    up.start()
    hb.start()

    return _run_capture(cfg, client, store, state, stop)


if __name__ == "__main__":
    sys.exit(main())
