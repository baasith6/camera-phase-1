"""Cloud AI worker: consumes clip jobs from Redis, runs detection + tracking + event
extraction, and posts AI events back to the backend (which scores + alerts).

Reliability:
  - Failed jobs are retried up to MAX_RETRIES times.
  - After MAX_RETRIES failures the job payload (with error info) is pushed to
    DEAD_LETTER_KEY for manual inspection.
  - Inspect dead-letter queue: redis-cli LRANGE onevo:clip-jobs:failed 0 -1
"""
import json
import os
import tempfile
import time

import redis

from .backend_client import BackendClient
from .config import Config
from .reid import ReIDExtractor
from .detector import DetectorBackend, build_detector
from .events import extract_events
from .s3 import ClipStore
from .zones import parse_zones

QUEUE_KEY       = "onevo:clip-jobs"
DEAD_LETTER_KEY = "onevo:clip-jobs:failed"
MAX_RETRIES     = 3


def process_job(job: dict, cfg: Config, store: ClipStore, detector: DetectorBackend,
                backend: BackendClient, reid_extractor: ReIDExtractor = None) -> None:
    clip_id    = job["clipId"]
    object_key = job["objectKey"]
    camera_id  = job["cameraId"]
    print(f"[cloud-ai] processing clip {clip_id} ({object_key})", flush=True)

    tmp = os.path.join(tempfile.gettempdir(), f"{clip_id}.mp4")
    store.download(object_key, tmp)
    try:
        raw_zones = backend.get_zones(camera_id)
        zones     = parse_zones(raw_zones)
        fps, frames = detector.track_clip(tmp, reid_extractor=reid_extractor)
        events    = extract_events(fps, frames, zones)
        result    = backend.post_ai_events(clip_id, detector.version, events)
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
    store   = ClipStore(cfg)
    backend = BackendClient(cfg.backend_url, cfg.service_key)

    print(f"[cloud-ai] loading backend={cfg.model_backend} model={cfg.model} device={cfg.device} ...", flush=True)
    detector = build_detector(cfg.model_backend, cfg.model, cfg.device, cfg.yoloe_prompts)
    reid_extractor = ReIDExtractor(device=cfg.device)
    print("[cloud-ai] ready, waiting for clip jobs", flush=True)

    while True:
        try:
            item = r.brpop(QUEUE_KEY, timeout=5)
            if item is None:
                continue
            _key, payload = item
            job = json.loads(payload)

            # Retry logic: track attempt count inside the job envelope.
            attempt = job.get("_attempt", 0) + 1
            job["_attempt"] = attempt

            try:
                process_job(job, cfg, store, detector, backend, reid_extractor=reid_extractor)
            except Exception as job_err:  # noqa: BLE001
                # A missing clip (NoSuchKey) will never appear — retrying just blocks the
                # worker on back-off sleeps. Dead-letter it immediately instead.
                missing_clip = "NoSuchKey" in str(job_err) or "does not exist" in str(job_err)
                print(f"[cloud-ai] job error (attempt {attempt}/{MAX_RETRIES}"
                      f"{'; missing clip, not retrying' if missing_clip else ''}): {job_err}", flush=True)
                if attempt < MAX_RETRIES and not missing_clip:
                    # Re-queue the job for another attempt (push to left so it retries soon).
                    r.lpush(QUEUE_KEY, json.dumps(job))
                    time.sleep(2 ** attempt)   # 2s, 4s back-off
                else:
                    # Dead-letter: push to failed list with error annotation.
                    job["_error"] = str(job_err)
                    job["_failed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    r.lpush(DEAD_LETTER_KEY, json.dumps(job))
                    print(f"[cloud-ai] clip {job.get('clipId')} dead-lettered after "
                          f"{MAX_RETRIES} attempts", flush=True)

        except Exception as e:  # noqa: BLE001
            # Worker-level error (Redis, etc.) — don't lose the current job.
            print(f"[cloud-ai] worker error: {e}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()

