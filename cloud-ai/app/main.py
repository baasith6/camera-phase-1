"""Cloud AI worker: consumes clip jobs from Redis, runs detection + tracking + event
extraction, and posts AI events back to the backend (which scores + alerts)."""
import json
import os
import tempfile
import time

import redis

from .backend_client import BackendClient
from .config import Config
from .detector import DetectorBackend, build_detector
from .events import extract_events
from .s3 import ClipStore
from .zones import parse_zones

QUEUE_KEY = "onevo:clip-jobs"


def process_job(job: dict, cfg: Config, store: ClipStore, detector: DetectorBackend, backend: BackendClient) -> None:
    clip_id = job["clipId"]
    object_key = job["objectKey"]
    camera_id = job["cameraId"]
    print(f"[cloud-ai] processing clip {clip_id} ({object_key})", flush=True)

    tmp = os.path.join(tempfile.gettempdir(), f"{clip_id}.mp4")
    store.download(object_key, tmp)
    try:
        raw_zones = backend.get_zones(camera_id)
        zones = parse_zones(raw_zones)
        fps, frames = detector.track_clip(tmp)
        events = extract_events(fps, frames, zones)
        result = backend.post_ai_events(clip_id, detector.version, events)
        print(f"[cloud-ai] clip {clip_id}: {len(events)} events -> {result}", flush=True)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def main() -> None:
    cfg = Config.load()
    host, _, port = cfg.redis_connection.partition(":")
    r = redis.Redis(host=host, port=int(port or 6379), decode_responses=True)
    store = ClipStore(cfg)
    backend = BackendClient(cfg.backend_url, cfg.service_key)

    print(f"[cloud-ai] loading backend={cfg.model_backend} model={cfg.model} device={cfg.device} ...", flush=True)
    detector = build_detector(cfg.model_backend, cfg.model, cfg.device, cfg.yoloe_prompts)
    print("[cloud-ai] ready, waiting for clip jobs", flush=True)

    while True:
        try:
            item = r.brpop(QUEUE_KEY, timeout=5)
            if item is None:
                continue
            _key, payload = item
            job = json.loads(payload)
            process_job(job, cfg, store, detector, backend)
        except Exception as e:  # noqa: BLE001
            print(f"[cloud-ai] error: {e}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
