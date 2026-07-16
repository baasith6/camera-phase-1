"""Shared runtime state for status reporting and the admin UI."""
import threading
import time
from collections import deque


class RuntimeState:
    def __init__(self, max_logs: int = 200):
        self._lock = threading.Lock()
        self.logs: deque[str] = deque(maxlen=max_logs)
        self.connector_id: str | None = None
        self.camera_id: str | None = None
        self.source: str | None = None
        self.capturing = False
        self.clips_created = 0
        self.uploads_ok = 0
        self.uploads_failed = 0
        self.queue_depth = 0
        self.disk_free_pct = 100.0
        self.degraded_reason: str | None = None
        self.last_heartbeat: float | None = None
        self.started_at = time.time()

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        with self._lock:
            self.logs.append(line)
        print(line, flush=True)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "connectorId": self.connector_id,
                "cameraId": self.camera_id,
                "source": self.source,
                "capturing": self.capturing,
                "clipsCreated": self.clips_created,
                "uploadsOk": self.uploads_ok,
                "uploadsFailed": self.uploads_failed,
                "queueDepth": self.queue_depth,
                "diskFreePct": round(self.disk_free_pct, 1),
                "degradedReason": self.degraded_reason,
                "uptimeSec": round(time.time() - self.started_at, 1),
                "lastHeartbeat": self.last_heartbeat,
                "logs": list(self.logs)[-50:],
            }
