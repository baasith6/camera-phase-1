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
import webbrowser

from .admin import start_admin
from .backend_client import BackendClient
from .capture import CapturePipeline, validate_rtsp_stream
from .clip_settings import ClipSettings, load_clip_settings, save_clip_settings
from .config import load_config
from .paths import apply_pending_source_update, load_wizard_config,save_wizard_config
from .instance_lock import InstanceLock
from .runtime import RuntimeState
from .store import LocalStore
from .update_check import check_for_update
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
        state.paired = True
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
    state.paired = True
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

        pipeline = CapturePipeline(
            cfg,
            state,
            zone_provider=lambda: client.get_zones(cfg.camera_id),
            zone_revision=lambda: state.zone_revision(cfg.camera_id),
        )
        state.pipeline = pipeline

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
    state.log(f"Local dashboard on http://127.0.0.1:{cfg.admin_port}/")
    start_admin(
        state,
        cfg,
        cfg.admin_port,
        store=store,
        enable_setup_wizard=True,
    )
    webbrowser.open(f"http://127.0.0.1:{cfg.admin_port}/#sources")
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


def _preflight_rtsp(rtsp_url: str, source_name: str, state: RuntimeState) -> None:
    """Validate that an RTSP URL is reachable before registering the camera."""
    state.log(f"Preflight: validating RTSP for {source_name} …")
    ok, msg = validate_rtsp_stream(rtsp_url)
    if not ok:
        raise ValueError(f"{source_name}: {msg}")
    state.log(f"Preflight: {source_name} — {msg}")


def _persist_provision_failure(
    wizard,
    claim_succeeded: bool,
    error: Exception,
    state: RuntimeState,
) -> None:
    """Persist activation failure without reopening browser-based first-time setup."""
    message = str(error) or "Installer activation failed"
    wizard.activation_error = message
    err_lower = message.lower()
    if claim_succeeded or any(token in err_lower for token in ("invalid", "expired", "used")):
        wizard.setup_code = ""
    save_wizard_config(wizard)
    state.degraded_reason = f"Installer activation failed: {message}"


def _has_connector_credentials(store: LocalStore) -> bool:
    return bool(store.get_cred("connector_id") and store.get_cred("api_key"))


def _reconcile_paired_wizard(wizard, store: LocalStore):
    """A paired connector never reuses or asks for a setup code.

    Installer updates can leave an older pending config behind. The durable
    connector credentials remain authoritative until a real uninstall removes
    the local state database.
    """
    if not wizard or not _has_connector_credentials(store):
        return wizard
    changed = bool(wizard.setup_code or wizard.activation_error)
    wizard.setup_code = ""
    wizard.activation_error = ""
    if changed:
        save_wizard_config(wizard)
    return wizard


def _provision_native_installer(cfg, wizard, client: BackendClient, store: LocalStore, state: RuntimeState) -> bool:
    """Claim native-installer setup and create its configured camera sources once."""
    if not wizard or wizard.setup_complete:
        return False

    claim_succeeded = False
    try:
        from .provisioning import claim_setup, complete_setup, provision_sources

        existing_cid = store.get_cred("connector_id")
        existing_key = store.get_cred("api_key")
        if existing_cid and existing_key:
            cid = existing_cid
            wizard.setup_code = ""
            wizard.activation_error = ""
            client.set_credentials(existing_cid, existing_key)
            save_wizard_config(wizard)
        elif wizard.setup_code:
            cid, _ = claim_setup(client, store, wizard, cfg.version)
            claim_succeeded = True
            # The one-time code has now been consumed and durable credentials
            # are authoritative, even while camera provisioning is still pending.
            state.connector_id = cid
            state.paired = True
        else:
            cid = store.get_cred("connector_id")
            api_key = store.get_cred("api_key")
            if not (cid and api_key):
                raise RuntimeError("pending setup has no connector credentials")
            client.set_credentials(cid, api_key)

        def checkpoint(sources):
            wizard.sources = sources
            wizard.setup_complete = False
            save_wizard_config(wizard)

        if wizard.sources:
            # Native Inno Setup collected these zones before service startup.
            # Preserve that fact before the sync loop removes pending entries.
            native_zones_configured = bool(wizard.pending_zones)
            created = provision_sources(
                client,
                wizard.sources,
                state,
                checkpoint=checkpoint,
                preflight_rtsp=bool(getattr(cfg, "service_mode", False)),
            )
            while wizard.pending_zones:
                pending_zone = wizard.pending_zones[0]
                if pending_zone.source_index < 0 or pending_zone.source_index >= len(created):
                    state.log(
                        f"WARNING: ignored installer zone with invalid source index "
                        f"{pending_zone.source_index}"
                    )
                    wizard.pending_zones.pop(0)
                    save_wizard_config(wizard)
                    continue
                camera_id = created[pending_zone.source_index].camera_id
                if camera_id:
                    client.create_zone(
                        camera_id,
                        pending_zone.name,
                        pending_zone.zone_type,
                        pending_zone.polygon,
                    )
                wizard.pending_zones.pop(0)
                save_wizard_config(wizard)
            client.finalize_setup([source.source_key for source in created])
            wizard.sources = created
            if native_zones_configured:
                # The installer page requires at least one zone per selected
                # camera. Zones have now been persisted in the backend, so a
                # browser wizard is not required to start monitoring.
                complete_setup(wizard, created)
            else:
                # Browser/local source additions still use the dashboard zone
                # page and must not start monitoring before it finishes.
                wizard.setup_complete = False
                save_wizard_config(wizard)
        else:
            # Installer may skip camera setup; pair connector and add sources later.
            created = []
            complete_setup(wizard, created)
        state.connector_id = cid
        state.paired = True
        if created:
            state.log(
                f"Native installer provisioned {len(created)} camera source(s); "
                "waiting for zone setup"
            )
        else:
            state.log("Native installer completed without camera sources")
        return True
    except Exception as exc:  # noqa: BLE001
        state.log(f"ERROR: native installer activation failed: {exc}")
        _persist_provision_failure(wizard, claim_succeeded, exc, state)
        if claim_succeeded and hasattr(store, "get_cred"):
            cid = store.get_cred("connector_id")
            key = store.get_cred("api_key")
            if cid and key:
                client.set_credentials(cid, key)
                state.connector_id = cid
                state.paired = True
        if _has_connector_credentials(store):
            had_stale_code = bool(wizard.setup_code)
            wizard.setup_code = ""
            if had_stale_code:
                save_wizard_config(wizard)
            state.degraded_reason = f"Camera configuration failed: {exc}"
        return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config()
    clip_tuning = load_clip_settings(
        ClipSettings(
            pre_seconds=cfg.pre_seconds,
            post_seconds=cfg.post_seconds,
            cooldown_seconds=cfg.cooldown_seconds,
        )
    )
    clip_tuning.apply_to_config(cfg)

    state = RuntimeState()
    state.source = cfg.source
    state.camera_id = cfg.camera_id

    store = LocalStore(cfg.state_dir)
    state.paired = _has_connector_credentials(store)
    # Pause is an operator decision, not a temporary process flag. Preserve it
    # across Windows service restarts and PC reboots.
    state.set_paused(store.get_bool_setting("monitoring_paused", False))

    if cfg.wizard_mode:
        return _run_wizard_only(cfg, state, store)

    instance_lock = InstanceLock(cfg.state_dir)
    if not instance_lock.acquire():
        state.log("ERROR: connector state is locked or unavailable")
        return 3

    client = BackendClient(cfg.backend_url)

    # Native installer writes a pending setup config before starting the service.
    # It must take precedence over credentials left by an older installation.
    wizard = load_wizard_config()
    if wizard and apply_pending_source_update(wizard):
        wizard = load_wizard_config()
        state.log("Installer source update applied; activation is pending")
    wizard = _reconcile_paired_wizard(wizard, store)

    stop = threading.Event()
    wizard_ready = threading.Event()
    pending_setup = bool(wizard and not wizard.setup_complete)

    def _on_wizard_configured(_wizard_cfg) -> None:
        wizard_ready.set()

    # Keep localhost:8099 reachable while backend activation is pending.
    start_admin(
        state,
        cfg,
        cfg.admin_port,
        client=client,
        store=store,
        # Keep /setup available after activation as the tray/local zone editor.
        enable_setup_wizard=True,
        on_wizard_configured=_on_wizard_configured if pending_setup else None,
    )
    state.log(f"Admin UI on http://localhost:{cfg.admin_port}")

    if cfg.service_mode and wizard and not wizard.setup_complete:
        if not wizard.setup_code and not _has_connector_credentials(store):
            state.degraded_reason = (
                "First-time pairing was not completed by the installer."
            )
            state.log("Setup is waiting for a setup code")
            while not wizard_ready.wait(timeout=1):
                current = load_wizard_config()
                if current and (
                    current.setup_code or current.setup_complete
                ):
                    wizard = current
                    break
        while wizard and not wizard.setup_complete:
            if _provision_native_installer(cfg, wizard, client, store, state):
                wizard = load_wizard_config()
                # Sources are ready but monitoring must wait for the browser
                # wizard's zone-finish action.  A source-less install is an
                # explicit operator choice and can complete immediately.
                if wizard and wizard.sources and not wizard.setup_complete:
                    state.degraded_reason = (
                        "Camera setup is ready. Open the Zones page in the "
                        "local dashboard to draw and save zones before monitoring starts."
                    )
                    state.log("Waiting for zone setup to complete")
                    wizard_ready.clear()
                    while not wizard_ready.wait(timeout=1):
                        current = load_wizard_config()
                        if current is None:
                            wizard = None
                            break
                        if current.setup_complete:
                            wizard = current
                            break
                    if wizard and wizard.setup_complete:
                        break
                    continue
                break

            wizard = load_wizard_config()
            if wizard is None:
                break

            has_credentials = _has_connector_credentials(store)
            if not wizard.setup_code and not has_credentials:
                state.degraded_reason = (
                    wizard.activation_error
                    or "First-time pairing was not completed by the installer."
                )
                state.log(
                    "Setup is waiting for a valid setup code; automatic retries paused"
                )
                wizard_ready.clear()
                while not wizard_ready.wait(timeout=1):
                    current = load_wizard_config()
                    if current is None:
                        wizard = None
                        break
                    if current.setup_complete or current.setup_code:
                        wizard = current
                        break
                continue

            state.degraded_reason = (
                "Setup pending: backend connection failed; retrying automatically."
            )
            state.log("Installer activation pending; retrying in 15 seconds")
            if wizard_ready.wait(timeout=15):
                wizard_ready.clear()
            wizard = load_wizard_config()
        cfg = load_config()
        state.source = cfg.source
        state.camera_id = cfg.camera_id
        client = BackendClient(cfg.backend_url)
        state.degraded_reason = None
    # Service / normal: register if needed (wizard may already have claimed).
    if not _has_connector_credentials(store):
        if not _ensure_registered(cfg, client, store, state):
            # Not registered yet Ã¢â‚¬â€ if installed, open wizard instead of failing hard.
            if cfg.service_mode or (wizard is None or not wizard.setup_complete):
                state.degraded_reason = "Connector pairing is incomplete."
                state.log("Not configured yet; local admin remains available")
                while True:
                    time.sleep(15)
            return 2
    else:
        client.set_credentials(store.get_cred("connector_id"), store.get_cred("api_key"))
        state.connector_id = client.connector_id
        state.paired = True
        state.log(f"Loaded existing connector credentials ({client.connector_id})")

        state.log("Setup completed via /setup — starting monitoring")

    up = threading.Thread(target=run_uploader, args=(cfg, client, store, state, stop), daemon=True)
    hb = threading.Thread(target=run_heartbeat, args=(cfg, client, store, state, stop), daemon=True)
    up.start()
    hb.start()
    check_for_update(cfg.backend_url, cfg.version, state.log)

    return _run_capture(cfg, client, store, state, stop)


if __name__ == "__main__":
    sys.exit(main())
