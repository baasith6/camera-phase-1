"""Background workers: durable upload queue processor + heartbeat reporter."""
import os
import shutil
import threading
import time

from .backend_client import BackendClient
from .config import Config
from .runtime import RuntimeState
from .store import LocalStore


def disk_free_pct(path: str) -> float:
    try:
        usage = shutil.disk_usage(path)
        return 100.0 * usage.free / usage.total
    except Exception:
        return 100.0


def run_uploader(cfg: Config, client: BackendClient, store: LocalStore,
                 state: RuntimeState, stop: threading.Event) -> None:
    while not stop.is_set():
        # A managed stop must leave queued clips durable but prevent every
        # cloud-side upload until the operator explicitly starts monitoring.
        if not state.wait_until_running(stop):
            break
        job = store.next_pending()
        if job is None:
            state.queue_depth = store.pending_count()
            stop.wait(1.0)
            continue

        if state.capture_paused:
            continue
        state.queue_depth = store.pending_count()
        try:
            store.mark(job.id, "uploading")
            info = client.request_upload_url(job.camera_id, job.duration_sec, job.trigger)
            client.upload_file(info["uploadUrl"], job.clip_path)
            client.complete_clip(info["clipId"])
            store.mark(job.id, "done")
            state.uploads_ok += 1
            state.log(f"Uploaded clip {info['clipId']}")
            # Delete local clip after successful upload (retention: keep only queued/failed).
            try:
                os.remove(job.clip_path)
            except OSError:
                pass
        except Exception as e:  # noqa: BLE001
            retries = job.retries + 1
            if retries >= cfg.max_upload_retries:
                store.mark(job.id, "failed", str(e), inc_retry=True)
                state.uploads_failed += 1
                state.log(f"Upload FAILED permanently (job {job.id}): {e}")
            else:
                store.mark(job.id, "pending", str(e), inc_retry=True)
                backoff = min(60, 2 ** retries)
                state.log(f"Upload error (job {job.id}), retry in {backoff}s: {e}")
                stop.wait(backoff)
        state.queue_depth = store.pending_count()


def run_heartbeat(cfg: Config, client: BackendClient, store: LocalStore,
                  state: RuntimeState, stop: threading.Event) -> None:
    from .network_util import admin_public_host

    admin_host = admin_public_host()
    while not stop.is_set():
        # Do not report a stopped connector as online. The local UI remains
        # reachable, but cloud traffic is intentionally paused.
        if not state.wait_until_running(stop):
            break
        free = disk_free_pct(cfg.state_dir)
        state.disk_free_pct = free
        operational = None
        if free < cfg.disk_critical_pct:
            operational = f"disk_critical:{free:.1f}%"
        elif free < cfg.disk_warn_pct:
            operational = f"disk_warning:{free:.1f}%"
        if store.pending_count() > 50:
            operational = (operational + ";" if operational else "") + "queue_backlog"

        with state._lock:
            existing = state.degraded_reason
            if existing and (
                existing.startswith("Setup")
                or "activation" in existing.lower()
                or "pending" in existing.lower()
            ):
                degraded = f"{existing};{operational}" if operational else existing
            else:
                degraded = operational
                state.degraded_reason = operational

        try:
            client.heartbeat(
                free, store.pending_count(), degraded, cfg.version,
                admin_host=admin_host, admin_port=cfg.admin_port,
            )
            state.last_heartbeat = time.time()
        except Exception as e:  # noqa: BLE001
            state.log(f"Heartbeat error: {e}")
        stop.wait(10.0)
