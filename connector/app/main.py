"""ONEVO Local Connector entrypoint.

Flow: register (once) -> start admin UI + uploader + heartbeat threads ->
capture loop cuts event clips -> clips enqueued to durable SQLite queue -> uploaded
to the cloud via short-lived signed URLs.
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


def main() -> int:
    cfg = load_config()
    state = RuntimeState()
    state.source = cfg.source
    state.camera_id = cfg.camera_id

    if not cfg.camera_id:
        state.log("ERROR: --camera-id (or CONNECTOR_CAMERA_ID) is required.")
        return 2

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

    stop = threading.Event()
    start_admin(state, cfg.admin_port)
    state.log(f"Admin UI on http://localhost:{cfg.admin_port}")

    up = threading.Thread(target=run_uploader, args=(cfg, client, store, state, stop), daemon=True)
    hb = threading.Thread(target=run_heartbeat, args=(cfg, client, store, state, stop), daemon=True)
    up.start()
    hb.start()

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
