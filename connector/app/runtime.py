"""Shared runtime state for status reporting and the admin UI."""
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .capture import CapturePipeline


class RuntimeState:
    def __init__(self, max_logs: int = 200):
        self._lock = threading.Lock()
        self.logs: deque[str] = deque(maxlen=max_logs)
        self.connector_id: str | None = None
        self.paired = False
        self.camera_id: str | None = None
        self.source: str | None = None
        self.capturing = False
        self.capture_paused = False
        self.clips_created = 0
        self.uploads_ok = 0
        self.uploads_failed = 0
        self.queue_depth = 0
        self.disk_free_pct = 100.0
        self.degraded_reason: str | None = None
        self.last_heartbeat: float | None = None
        self.started_at = time.time()

        # RTSP reliability
        self.rtsp_reconnects = 0

        # ONVIF device metadata (populated after ONVIF connect)
        self.camera_manufacturer: str | None = None
        self.camera_model: str | None = None
        self.camera_serial: str | None = None
        self.camera_firmware: str | None = None
        self.onvif_profiles: list[dict] = []

        # Last captured frame (JPEG bytes) per camera ID for the dashboard
        self.last_frames: dict[str, bytes] = {}
        self.camera_states: dict[str, dict[str, Any]] = {}
        self.zone_revisions: dict[str, int] = {}

        # Active capture pipeline(s) — set from main.py / orchestrator for admin control
        self.pipeline: CapturePipeline | None = None
        self.pipelines: dict[str, Any] = {}
        # Remains set while connector work is allowed. The local HTTP control
        # host intentionally stays alive when this event is cleared.
        self._monitoring_active = threading.Event()
        self._monitoring_active.set()

    def publish_frame(
        self, camera_id: str, jpeg: bytes, width: int, height: int, source_fps: float
    ) -> None:
        now = time.time()
        with self._lock:
            self.last_frames[camera_id] = jpeg
            current = self.camera_states.setdefault(camera_id, {})
            current.update({
                "cameraId": camera_id,
                "status": "Live",
                "lastFrameAt": now,
                "width": width,
                "height": height,
                "sourceFps": round(source_fps, 2),
                "lastError": None,
            })
            current["frameSequence"] = int(current.get("frameSequence", 0)) + 1

    def set_camera_status(self, camera_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            current = self.camera_states.setdefault(camera_id, {"cameraId": camera_id})
            current["status"] = status
            current["lastError"] = error
            if status == "Reconnecting":
                current["reconnectCount"] = int(current.get("reconnectCount", 0)) + 1

    def remove_camera(self, camera_id: str) -> None:
        with self._lock:
            self.last_frames.pop(camera_id, None)
            self.camera_states.pop(camera_id, None)
            self.pipelines.pop(camera_id, None)
            self.zone_revisions.pop(camera_id, None)

    def invalidate_zones(self, camera_id: str) -> None:
        """Tell the capture worker to reload this camera's saved polygons."""
        with self._lock:
            self.zone_revisions[camera_id] = self.zone_revisions.get(camera_id, 0) + 1

    def zone_revision(self, camera_id: str) -> int:
        with self._lock:
            return self.zone_revisions.get(camera_id, 0)

    def get_frame(self, camera_id: str) -> bytes | None:
        with self._lock:
            return self.last_frames.get(camera_id)

    def camera_statuses(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(value) for value in self.camera_states.values()]

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        with self._lock:
            self.logs.append(line)
        print(line, flush=True)

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            was = self.capture_paused
            self.capture_paused = paused
            if paused:
                self._monitoring_active.clear()
                self.capturing = False
            else:
                self._monitoring_active.set()
            if paused:
                self.last_frames.clear()
                for current in self.camera_states.values():
                    current["status"] = "Paused"
                    current["lastError"] = None
        if paused and not was:
            self.log("Capture paused — no new motion clips")
        elif not paused and was:
            self.log("Capture resumed")

    def wait_until_running(self, stop: threading.Event, timeout: float = 0.5) -> bool:
        """Wait for a managed-stop to be released without stopping the UI host."""
        while not stop.is_set():
            if self._monitoring_active.wait(timeout=timeout):
                return True
        return False

    def request_trigger(self) -> bool:
        """Ask the primary pipeline to cut a clip on the next frame."""
        if self.pipeline is not None:
            self.pipeline.request_trigger()
            return True
        triggered = False
        for pipeline in self.pipelines.values():
            pipeline.request_trigger()
            triggered = True
        return triggered

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "connectorId": self.connector_id,
                "paired": self.paired,
                "cameraId": self.camera_id,
                "source": self.source,
                "capturing": self.capturing,
                "capturePaused": self.capture_paused,
                "monitoringState": "stopped" if self.capture_paused else "running",
                "clipsCreated": self.clips_created,
                "uploadsOk": self.uploads_ok,
                "uploadsFailed": self.uploads_failed,
                "queueDepth": self.queue_depth,
                "diskFreePct": round(self.disk_free_pct, 1),
                "degradedReason": self.degraded_reason,
                "uptimeSec": round(time.time() - self.started_at, 1),
                "lastHeartbeat": self.last_heartbeat,
                "rtspReconnects": self.rtsp_reconnects,
                "cameraManufacturer": self.camera_manufacturer,
                "cameraModel": self.camera_model,
                "cameraSerial": self.camera_serial,
                "cameraFirmware": self.camera_firmware,
                "onvifProfiles": self.onvif_profiles,
                "logs": list(self.logs)[-50:],
            }
