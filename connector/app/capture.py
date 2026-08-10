"""Video capture: rolling buffer + motion/person pre-filter + event clip cutting.

The connector never runs the full retail-cue model. This is only a lightweight
candidate selector (motion, optional person presence) to reduce useless uploads.

RTSP reliability:
  - Initial open retries with exponential back-off before giving up.
  - Mid-stream read failures re-open the stream with the same back-off.
  File sources loop as before.
"""
import os
import json
import subprocess
import threading
import time
import uuid
from collections import deque
from typing import Callable

import cv2
import numpy as np

from .config import Config
from .live_tracker import try_build_live_tracker
from .runtime import RuntimeState

# OpenCV environment hints for lower-latency RTSP (set before any VideoCapture).
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

# Initial RTSP connect: up to 10 attempts (~2 min total with default max backoff).
RTSP_INITIAL_MAX_ATTEMPTS = 10


def _normalize_source(source: str) -> str:
    if source.startswith("file://"):
        return source[len("file://"):]
    return source


def _build_video_capture(source: str) -> cv2.VideoCapture:
    """Open a video source with RTSP-friendly options when applicable."""
    src = _normalize_source(source)
    if source.lower().startswith("rtsp"):
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        try:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10_000)
        except Exception:
            pass
        return cap
    return cv2.VideoCapture(src)


def validate_rtsp_stream(source: str, read_frame: bool = True) -> tuple[bool, str]:
    """Preflight check: try to open an RTSP stream (and optionally read one frame).

    Returns (ok, message). Safe to call from installer provisioning / wizard setup.
    """
    if not source.lower().startswith("rtsp"):
        return True, "not an RTSP source"

    cap = _build_video_capture(source)
    try:
        if not cap or not cap.isOpened():
            return False, f"cannot open RTSP stream: {source}"
        if read_frame:
            ok, _frame = cap.read()
            if not ok:
                return False, f"RTSP stream opened but no frame received: {source}"
        return True, "RTSP stream OK"
    finally:
        try:
            cap.release()
        except Exception:
            pass


class CapturePipeline:
    def __init__(
        self,
        cfg: Config,
        state: RuntimeState,
        zone_provider: Callable[[], list[dict]] | None = None,
        zone_revision: Callable[[], int] | None = None,
        reference_frame_publisher: Callable[[str, bytes], bool] | None = None,
    ):
        self.cfg = cfg
        self.state = state
        self._stop = False
        self._trigger_requested = False
        self._trigger_lock = threading.Lock()
        self._is_rtsp = cfg.source.lower().startswith("rtsp")
        self._person_hog = None
        self._source_fps = cfg.fps
        self._zone_provider = zone_provider
        self._zone_revision = zone_revision
        self._zone_points: list[np.ndarray] = []
        self._zone_mask: np.ndarray | None = None
        self._zone_mask_shape: tuple[int, int] | None = None
        self._zone_loaded_at = 0.0
        self._zone_loaded_revision = -1
        self._zone_fetch_failures = 0
        self._zone_signature = ""
        self._reference_frame_publisher = reference_frame_publisher
        self._reference_frame_pending = False
        self._reference_frame_inflight = False
        self._live_tracker = try_build_live_tracker(
            enabled=cfg.live_track,
            model_path=cfg.live_track_model,
            device=cfg.live_track_device,
            stride=cfg.live_track_stride,
        )
        if cfg.use_person_filter:
            self._person_hog = cv2.HOGDescriptor()
            self._person_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def _update_live_tracks(self, frame) -> None:
        if self._live_tracker is None or not self.cfg.camera_id:
            return
        try:
            tracks = self._live_tracker.update(frame)
            self.state.publish_tracks(
                self.cfg.camera_id,
                [t.as_dict() for t in tracks],
            )
        except Exception as exc:  # noqa: BLE001
            self.state.log(f"live-tracker update failed: {exc}")

    def stop(self) -> None:
        self._stop = True

    def request_trigger(self) -> None:
        with self._trigger_lock:
            self._trigger_requested = True

    def _consume_trigger(self) -> bool:
        with self._trigger_lock:
            if self._trigger_requested:
                self._trigger_requested = False
                return True
            return False

    def _clip_window_frames(self, fps: float) -> tuple[int, int]:
        pre_len = max(1, int(self.cfg.pre_seconds * fps))
        post_len = max(1, int(self.cfg.post_seconds * fps))
        return pre_len, post_len

    # ------------------------------------------------------------------
    # Stream open helpers
    # ------------------------------------------------------------------

    def _open(self) -> cv2.VideoCapture:
        """Open the configured video source with RTSP-friendly options."""
        return _build_video_capture(self.cfg.source)

    def _open_initial(self) -> cv2.VideoCapture | None:
        """Open source; for RTSP, retry with exponential back-off before giving up."""
        if not self._is_rtsp:
            cap = self._open()
            return cap if cap and cap.isOpened() else None

        for attempt in range(RTSP_INITIAL_MAX_ATTEMPTS):
            if self._stop:
                return None
            cap = self._open()
            if cap and cap.isOpened():
                if attempt > 0:
                    self.state.log(
                        f"RTSP initial connect OK on attempt {attempt + 1} [{self.cfg.source}]"
                    )
                return cap
            try:
                cap.release()
            except Exception:
                pass

            if attempt + 1 >= RTSP_INITIAL_MAX_ATTEMPTS:
                break

            backoff = min(2 ** attempt, self.cfg.rtsp_reconnect_max_sec)
            self.state.log(
                f"RTSP initial connect failed — retry {attempt + 2}/"
                f"{RTSP_INITIAL_MAX_ATTEMPTS} in {backoff:.0f}s [{self.cfg.source}]"
            )
            deadline = time.time() + backoff
            while not self._stop and time.time() < deadline:
                time.sleep(0.5)

        return None

    def _reconnect_rtsp(self, cap: cv2.VideoCapture, attempt: int) -> cv2.VideoCapture:
        """Release the old capture and re-open with exponential back-off."""
        try:
            cap.release()
        except Exception:
            pass

        backoff = min(2 ** attempt, self.cfg.rtsp_reconnect_max_sec)
        self.state.rtsp_reconnects += 1
        if self.cfg.camera_id:
            self.state.set_camera_status(self.cfg.camera_id, "Reconnecting")
        self.state.log(
            f"RTSP stream lost — reconnect attempt {attempt + 1} "
            f"(waiting {backoff:.0f}s) [{self.cfg.source}]"
        )

        deadline = time.time() + backoff
        while not self._stop and time.time() < deadline:
            time.sleep(0.5)

        new_cap = self._open()
        if new_cap.isOpened():
            self.state.log("RTSP reconnected OK")
        elif self.cfg.camera_id:
            self.state.set_camera_status(
                self.cfg.camera_id, "Offline", "RTSP reconnect failed"
            )
        return new_cap

    def _publish_preview(self, frame, now: float, fps: float) -> None:
        if not self.cfg.camera_id or now - getattr(self, "_last_snap", 0) < 0.5:
            return
        self._last_snap = now
        height, width = frame.shape[:2]
        preview = frame
        if width > 960:
            scale = 960 / float(width)
            preview = cv2.resize(frame, (960, max(1, int(height * scale))))
        ret, jpeg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ret:
            ph, pw = preview.shape[:2]
            self.state.publish_frame(
                self.cfg.camera_id, jpeg.tobytes(), pw, ph, fps
            )
            if (
                self._reference_frame_pending
                and not self._reference_frame_inflight
                and self._reference_frame_publisher is not None
            ):
                self._reference_frame_pending = False
                self._reference_frame_inflight = True
                payload = jpeg.tobytes()

                def publish() -> None:
                    try:
                        ok = self._reference_frame_publisher(self.cfg.camera_id, payload)
                        if not ok:
                            self._reference_frame_pending = True
                    finally:
                        self._reference_frame_inflight = False

                threading.Thread(target=publish, daemon=True).start()

    def _processing_frame(self, frame):
        """Bound per-camera RAM while retaining enough detail for cloud analysis."""
        height, width = frame.shape[:2]
        max_width = self.cfg.processing_max_width
        if width <= max_width:
            return frame
        scale = max_width / float(width)
        return cv2.resize(
            frame,
            (max_width, max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    def _wait_while_paused(self, cap: cv2.VideoCapture | None) -> cv2.VideoCapture | None:
        if not self.state.capture_paused:
            return cap
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        if self.cfg.camera_id:
            self.state.set_camera_status(self.cfg.camera_id, "Paused")
        while self.state.capture_paused and not self._stop:
            time.sleep(0.25)
        if self._stop:
            return None
        return self._open_initial()

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_zone_points(zone: dict) -> np.ndarray | None:
        raw = zone.get("polygonJson", zone.get("PolygonJson", zone.get("polygon", [])))
        try:
            points = json.loads(raw) if isinstance(raw, str) else raw
            polygon = np.asarray(points, dtype=np.float32)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if polygon.ndim != 2 or polygon.shape[0] < 3 or polygon.shape[1] != 2:
            return None
        if not np.isfinite(polygon).all() or (polygon < 0).any() or (polygon > 1).any():
            return None
        return polygon

    def _refresh_zones(self, frame_shape: tuple[int, int]) -> None:
        """Reload saved zones on edits and periodically; failed fetches fail closed."""
        if self._zone_provider is None:
            self._zone_points = []
            self._zone_mask = None
            return
        now = time.monotonic()
        revision = self._zone_revision() if self._zone_revision else 0
        if (
            self._zone_mask_shape == frame_shape
            and self._zone_loaded_revision == revision
            and now - self._zone_loaded_at < 10.0
        ):
            return
        try:
            zones = self._zone_provider() or []
            signature = json.dumps(zones, sort_keys=True, default=str)
            self._zone_points = [
                polygon for zone in zones
                if isinstance(zone, dict)
                for polygon in [self._parse_zone_points(zone)]
                if polygon is not None
            ]
            self._zone_loaded_revision = revision
            self._zone_loaded_at = now
            if self._zone_points and signature != self._zone_signature:
                self._reference_frame_pending = True
            self._zone_signature = signature
            self._zone_fetch_failures = 0
        except Exception as exc:  # noqa: BLE001
            self._zone_loaded_revision = revision
            self._zone_loaded_at = now
            self._zone_fetch_failures += 1
            self.state.log(f"WARNING: could not refresh camera zones: {exc}")
            if self._zone_points and self._zone_fetch_failures < 3:
                return
            self._zone_points = []
        height, width = frame_shape
        mask = np.zeros((height, width), dtype=np.uint8)
        for polygon in self._zone_points:
            pixels = np.round(
                polygon * np.array([max(width - 1, 1), max(height - 1, 1)], dtype=np.float32)
            ).astype(np.int32)
            cv2.fillPoly(mask, [pixels], 255)
        self._zone_mask = mask
        self._zone_mask_shape = frame_shape
        if self.cfg.camera_id:
            self.state.set_camera_status(
                self.cfg.camera_id,
                "Live" if self._zone_points else "Waiting for zones",
                None if self._zone_points else "No saved detection zones",
            )

    def _has_motion(self, fgmask) -> bool:
        if self._zone_mask is None or not np.any(self._zone_mask):
            return False
        masked = cv2.bitwise_and(fgmask, fgmask, mask=self._zone_mask)
        zone_pixels = int(np.count_nonzero(self._zone_mask))
        if zone_pixels == 0:
            return False
        nonzero = int(np.count_nonzero(masked))
        frac = nonzero / float(zone_pixels)
        return frac >= self.cfg.motion_area_frac

    def _has_person(self, frame) -> bool:
        if self._person_hog is None:
            return True  # person filter disabled -> do not block
        small = cv2.resize(frame, (min(640, frame.shape[1]), min(360, frame.shape[0])))
        rects, _ = self._person_hog.detectMultiScale(small, winStride=(8, 8))
        if not len(rects) or not self._zone_points:
            return False
        height, width = small.shape[:2]
        for x, y, w, h in rects:
            point = (float(x + w / 2) / width, float(y + h / 2) / height)
            if any(cv2.pointPolygonTest(polygon, point, False) >= 0 for polygon in self._zone_points):
                return True
        return False

    # ------------------------------------------------------------------
    # Clip writing
    # ------------------------------------------------------------------

    def _write_clip(self, frames: list, fps: float) -> str | None:
        if not frames:
            return None
        os.makedirs(os.path.join(self.cfg.state_dir, "clips"), exist_ok=True)
        clip_id = uuid.uuid4().hex
        raw_path = os.path.join(self.cfg.state_dir, "clips", f"{clip_id}.raw.mp4")
        path = os.path.join(self.cfg.state_dir, "clips", f"{clip_id}.mp4")
        h, w = frames[0].shape[:2]
        # OpenCV's mp4v (MPEG-4 Part 2) isn't playable in browsers — write it here,
        # then transcode to H.264 below so the dashboard's <video> tag can play it.
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(raw_path, fourcc, fps, (w, h))
        for f in frames:
            writer.write(f)
        writer.release()

        try:
            from .paths import resolve_ffmpeg
            ffmpeg_bin = resolve_ffmpeg()
            subprocess.run(
                [ffmpeg_bin, "-y", "-i", raw_path, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", "-loglevel", "error", path],
                check=True, timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            self.state.log(f"WARNING: H.264 transcode failed ({exc}); uploading raw clip instead")
            os.replace(raw_path, path)
            return path
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)
        return path

    # ------------------------------------------------------------------
    # Main capture loop
    # ------------------------------------------------------------------

    def run(self, on_clip: Callable[[str, float, str], None]) -> None:
        """Blocking capture loop. Calls on_clip(path, duration_sec, trigger) per event.

        For RTSP sources, read failures trigger automatic reconnect with exponential
        back-off.  The loop only exits when self._stop is set or a file source ends.
        """
        cap = self._wait_while_paused(None)
        if cap is None and not self.state.capture_paused and not self._stop:
            cap = self._open_initial()
        if not cap:
            self.state.log(f"ERROR: cannot open source {self.cfg.source}")
            if self.cfg.camera_id:
                self.state.set_camera_status(
                    self.cfg.camera_id, "Offline", "Cannot open source"
                )
            return

        src_fps = cap.get(cv2.CAP_PROP_FPS) or self.cfg.fps
        fps = self.cfg.fps if self.cfg.fps > 0 else (src_fps or 10)
        self._source_fps = max(1.0, float(src_fps or fps or 10))
        file_frame_interval = 1.0 / self._source_fps
        next_file_frame_at = time.monotonic()
        pre_len, post_len = self._clip_window_frames(fps)

        rolling: deque = deque(maxlen=pre_len)
        bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=25, detectShadows=False)
        last_trigger = 0.0
        reconnect_attempt = 0
        self.state.capturing = True
        track_note = "live-track=on" if self._live_tracker is not None else "live-track=off"
        self.state.log(
            f"Capture started  source={'RTSP' if self._is_rtsp else 'file'} "
            f"fps={fps:.1f} pre={pre_len}f post={post_len}f {track_note}"
        )

        while not self._stop:
            if self.state.capture_paused:
                rolling.clear()
                cap = self._wait_while_paused(cap)
                bg = cv2.createBackgroundSubtractorMOG2(
                    history=200, varThreshold=25, detectShadows=False
                )
                if cap is None:
                    break
                next_file_frame_at = time.monotonic()
                # RuntimeState is set to not-capturing while paused. Once the
                # source is successfully reopened, immediately reflect the
                # real running state in the local dashboard.
                self.state.capturing = True
                self.state.log("Capture source reopened after resume")
                continue
            ok, frame = cap.read()

            # ---- Handle read failure ------------------------------------------------
            if not ok:
                if self._is_rtsp:
                    # RTSP stream dropped → reconnect with back-off.
                    cap = self._reconnect_rtsp(cap, reconnect_attempt)
                    reconnect_attempt += 1
                    # Reset background model after reconnect to avoid spurious motion.
                    bg = cv2.createBackgroundSubtractorMOG2(
                        history=200, varThreshold=25, detectShadows=False
                    )
                    rolling.clear()
                    continue
                elif self.cfg.loop:
                    # File loop: restart from beginning.
                    cap.release()
                    cap = self._open()
                    next_file_frame_at = time.monotonic()
                    continue
                else:
                    break   # file ended, stop normally

            # ---- Successful read — reset reconnect counter --------------------------
            reconnect_attempt = 0

            if not self._is_rtsp:
                now_mono = time.monotonic()
                delay = next_file_frame_at - now_mono
                if delay > 0:
                    time.sleep(delay)
                next_file_frame_at = max(
                    next_file_frame_at + file_frame_interval, time.monotonic()
                )

            frame = self._processing_frame(frame)
            rolling.append(frame.copy())
            self._refresh_zones(frame.shape[:2])
            fgmask = bg.apply(frame)
            now = time.time()

            # Live-apply pre/post window changes from admin settings.
            new_pre, new_post = self._clip_window_frames(fps)
            if new_pre != pre_len:
                pre_len = new_pre
                rolling = deque(list(rolling)[-pre_len:], maxlen=pre_len)
            post_len = new_post

            self._update_live_tracks(frame)
            self._publish_preview(frame, now, self._source_fps)

            manual_trigger = self._consume_trigger()
            motion = self._has_motion(fgmask)
            should_cut = manual_trigger or (
                motion and (now - last_trigger) >= self.cfg.cooldown_seconds
            )
            if should_cut:
                if not manual_trigger and not self._has_person(frame):
                    continue
                last_trigger = now
                reason = "manual-trigger" if manual_trigger else "motion"
                self.state.log(f"{reason} -> cutting event clip")

                # Collect post-event frames.
                post_frames: list = []
                for _ in range(post_len):
                    ok2, f2 = cap.read()
                    if not ok2:
                        if self._is_rtsp:
                            cap = self._reconnect_rtsp(cap, reconnect_attempt)
                            reconnect_attempt += 1
                        elif self.cfg.loop:
                            cap.release()
                            cap = self._open()
                        break
                    if not self._is_rtsp:
                        now_mono = time.monotonic()
                        delay = next_file_frame_at - now_mono
                        if delay > 0:
                            time.sleep(delay)
                        next_file_frame_at = max(
                            next_file_frame_at + file_frame_interval,
                            time.monotonic(),
                        )
                    f2 = self._processing_frame(f2)
                    post_frames.append(f2.copy())
                    self._update_live_tracks(f2)
                    self._publish_preview(f2, time.time(), self._source_fps)
                    reconnect_attempt = 0

                clip_frames = list(rolling) + post_frames
                duration = len(clip_frames) / fps
                path = self._write_clip(clip_frames, fps)
                if path:
                    self.state.clips_created += 1
                    on_clip(path, duration, reason)
                rolling.clear()

        if cap is not None:
            cap.release()
        self.state.capturing = False
        if self.cfg.camera_id:
            self.state.set_camera_status(self.cfg.camera_id, "Offline", "Capture stopped")
        self.state.log("Capture stopped")
