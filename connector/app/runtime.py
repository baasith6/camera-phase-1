"""Shared runtime state for status reporting and the admin UI."""
import os
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
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
        self.backend_available = True
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
        self.reference_frames: dict[str, bytes] = {}
        self.camera_states: dict[str, dict[str, Any]] = {}
        self.zone_revisions: dict[str, int] = {}

        # Active capture pipeline(s) — set from main.py / orchestrator for admin control
        self.pipeline: CapturePipeline | None = None
        self.pipelines: dict[str, Any] = {}
        # Remains set while connector work is allowed. The local HTTP control
        # host intentionally stays alive when this event is cleared.
        self._monitoring_active = threading.Event()
        self._monitoring_active.set()
        self._backend_active = threading.Event()
        self._backend_active.set()
        self._event_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="onevo-event"
        )
        # CPU-aware bounded worker pools. OpenCV is restricted to one internal
        # worker so the Python analysis pool does not multiply native threads.
        logical_cpus = max(1, os.cpu_count() or 1)
        self.logical_cpus = logical_cpus
        self.analysis_workers = min(4, max(1, logical_cpus - 2))
        self.ffmpeg_workers = 1 if logical_cpus < 8 else 2
        self._analysis_executor = ThreadPoolExecutor(
            max_workers=self.analysis_workers, thread_name_prefix="onevo-analysis"
        )
        self._clip_executor = ThreadPoolExecutor(
            max_workers=self.ffmpeg_workers, thread_name_prefix="onevo-ffmpeg"
        )
        self._analysis_slots = threading.BoundedSemaphore(self.analysis_workers * 2)
        self._clip_slots = threading.BoundedSemaphore(self.ffmpeg_workers * 2)
        self.analysis_queue_depth = 0
        self.analysis_dropped = 0
        self.clip_queue_depth = 0
        self.clip_jobs_dropped = 0
        self.analysis_active = 0
        self.ffmpeg_active = 0

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

    def remove_camera(self, camera_id: str, *, preserve_frame: bool = False) -> None:
        with self._lock:
            if not preserve_frame:
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

    def cache_frame(self, camera_id: str, jpeg: bytes) -> None:
        """Keep a stable camera-specific setup frame without changing runtime status."""
        if not camera_id or not jpeg:
            return
        with self._lock:
            self.last_frames[camera_id] = jpeg

    def get_reference_frame(self, camera_id: str) -> bytes | None:
        with self._lock:
            return self.reference_frames.get(camera_id)

    def cache_reference_frame(self, camera_id: str, jpeg: bytes) -> None:
        if camera_id and jpeg:
            with self._lock:
                self.reference_frames[camera_id] = jpeg

    def camera_statuses(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(value) for value in self.camera_states.values()]

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        with self._lock:
            self.logs.append(line)
        print(line, flush=True)

    def clear_logs(self) -> int:
        """Atomically clear the local UI log ring and return removed row count."""
        with self._lock:
            removed = len(self.logs)
            self.logs.clear()
            return removed

    def submit_event(self, callback, *args):
        """Run short I/O event work on the shared bounded executor."""
        def run():
            if self.capture_paused:
                return None
            return callback(*args)
        return self._event_executor.submit(run)

    def run_analysis(self, callback, *args, timeout: float = 3.0):
        """Run CPU analysis on the shared bounded pool.

        When every worker and waiting slot is occupied, the newest request is
        dropped instead of creating an unbounded stale-frame backlog.
        """
        if not self._analysis_slots.acquire(blocking=False):
            with self._lock:
                self.analysis_dropped += 1
            return None
        with self._lock:
            self.analysis_queue_depth += 1

        def run():
            with self._lock:
                self.analysis_queue_depth -= 1
                self.analysis_active += 1
            try:
                if self.capture_paused:
                    return None
                return callback(*args)
            finally:
                with self._lock:
                    self.analysis_active -= 1

        future = self._analysis_executor.submit(run)
        future.add_done_callback(lambda _done: self._analysis_slots.release())
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            with self._lock:
                self.analysis_dropped += 1
            return None

    def submit_clip_job(self, callback, *args, on_complete=None) -> bool:
        """Queue one clip encode/transcode without blocking the capture loop."""
        if not self._clip_slots.acquire(blocking=False):
            with self._lock:
                self.clip_jobs_dropped += 1
            return False
        with self._lock:
            self.clip_queue_depth += 1

        def run():
            with self._lock:
                self.clip_queue_depth -= 1
                self.ffmpeg_active += 1
            try:
                if self.capture_paused:
                    return None
                return callback(*args)
            finally:
                with self._lock:
                    self.ffmpeg_active -= 1

        future: Future = self._clip_executor.submit(run)

        def finished(done: Future) -> None:
            try:
                if on_complete is not None:
                    on_complete(done)
            finally:
                self._clip_slots.release()

        future.add_done_callback(finished)
        return True

    def shutdown_workers(self) -> None:
        self._event_executor.shutdown(wait=False, cancel_futures=True)
        self._analysis_executor.shutdown(wait=False, cancel_futures=True)
        self._clip_executor.shutdown(wait=True, cancel_futures=False)

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
                # Keep the last frame per camera so the zone editor remains
                # usable while capture, motion detection, uploads, and
                # heartbeat are stopped. A paused frame is intentionally
                # immutable until an explicit Refresh Frame action.
                for current in self.camera_states.values():
                    current["status"] = "Paused"
                    current["lastError"] = None
        if paused and not was:
            self.log("Capture paused — no new motion clips")
        elif not paused and was:
            self.log("Capture resumed")

    def set_backend_available(self, available: bool) -> None:
        """Gate capture/cloud work while retaining the local control surface."""
        with self._lock:
            changed = self.backend_available != available
            self.backend_available = available
            if available:
                self._backend_active.set()
            else:
                self._backend_active.clear()
                self.capturing = False
                for current in self.camera_states.values():
                    current["status"] = "Backend unavailable"
                    current["lastError"] = "Cloud backend is unavailable"
        if changed:
            self.log("Backend connection restored" if available else "Backend unavailable; monitoring stopped")

    def wait_until_running(self, stop: threading.Event, timeout: float = 0.5) -> bool:
        """Wait for a managed-stop to be released without stopping the UI host."""
        while not stop.is_set():
            if (
                self._monitoring_active.wait(timeout=timeout)
                and self._backend_active.is_set()
            ):
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
                "backendAvailable": self.backend_available,
                "monitoringState": "stopped" if self.capture_paused else "running",
                "clipsCreated": self.clips_created,
                "uploadsOk": self.uploads_ok,
                "uploadsFailed": self.uploads_failed,
                "queueDepth": self.queue_depth,
                "logicalCpus": self.logical_cpus,
                "analysisWorkers": self.analysis_workers,
                "analysisActive": self.analysis_active,
                "analysisQueueDepth": self.analysis_queue_depth,
                "analysisDropped": self.analysis_dropped,
                "ffmpegWorkers": self.ffmpeg_workers,
                "ffmpegActive": self.ffmpeg_active,
                "clipQueueDepth": self.clip_queue_depth,
                "clipJobsDropped": self.clip_jobs_dropped,
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
