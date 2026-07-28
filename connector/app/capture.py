"""Video capture: rolling buffer + motion/person pre-filter + event clip cutting.

The connector never runs the full retail-cue model. This is only a lightweight
candidate selector (motion, optional person presence) to reduce useless uploads.

RTSP reliability:
  - Initial open retries with exponential back-off before giving up.
  - Mid-stream read failures re-open the stream with the same back-off.
  File sources loop as before.
"""
import os
import subprocess
import time
import uuid
from collections import deque
from typing import Callable

import cv2
import numpy as np

from .config import Config
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
    def __init__(self, cfg: Config, state: RuntimeState):
        self.cfg = cfg
        self.state = state
        self._stop = False
        self._is_rtsp = cfg.source.lower().startswith("rtsp")
        self._person_hog = None
        if cfg.use_person_filter:
            self._person_hog = cv2.HOGDescriptor()
            self._person_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def stop(self) -> None:
        self._stop = True

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
        return new_cap

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _has_motion(self, fgmask) -> bool:
        nonzero = int(np.count_nonzero(fgmask))
        frac = nonzero / float(fgmask.size)
        return frac >= self.cfg.motion_area_frac

    def _has_person(self, frame) -> bool:
        if self._person_hog is None:
            return True  # person filter disabled -> do not block
        small = cv2.resize(frame, (min(640, frame.shape[1]), min(360, frame.shape[0])))
        rects, _ = self._person_hog.detectMultiScale(small, winStride=(8, 8))
        return len(rects) > 0

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
        cap = self._open_initial()
        if not cap:
            self.state.log(f"ERROR: cannot open source {self.cfg.source}")
            return

        src_fps = cap.get(cv2.CAP_PROP_FPS) or self.cfg.fps
        fps = self.cfg.fps if self.cfg.fps > 0 else (src_fps or 10)
        pre_len = int(self.cfg.pre_seconds * fps)
        post_len = int(self.cfg.post_seconds * fps)

        rolling: deque = deque(maxlen=pre_len)
        bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=25, detectShadows=False)
        last_trigger = 0.0
        reconnect_attempt = 0
        self.state.capturing = True
        self.state.log(
            f"Capture started  source={'RTSP' if self._is_rtsp else 'file'} "
            f"fps={fps:.1f} pre={pre_len}f post={post_len}f"
        )

        while not self._stop:
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
                    continue
                else:
                    break   # file ended, stop normally

            # ---- Successful read — reset reconnect counter --------------------------
            reconnect_attempt = 0

            rolling.append(frame.copy())
            fgmask = bg.apply(frame)
            now = time.time()

            # Save snapshot to state for the dashboard (max 1 per second)
            if now - getattr(self, "_last_snap", 0) > 1.0:
                self._last_snap = now
                if self.cfg.camera_id:
                    ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    if ret:
                        self.state.last_frames[self.cfg.camera_id] = jpeg.tobytes()

            # ---- Motion / person gate -----------------------------------------------
            if self._has_motion(fgmask) and (now - last_trigger) >= self.cfg.cooldown_seconds:
                if not self._has_person(frame):
                    continue
                last_trigger = now
                self.state.log("Motion trigger -> cutting event clip")

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
                    post_frames.append(f2.copy())
                    reconnect_attempt = 0

                clip_frames = list(rolling) + post_frames
                duration = len(clip_frames) / fps
                path = self._write_clip(clip_frames, fps)
                if path:
                    self.state.clips_created += 1
                    on_clip(path, duration, "motion")
                rolling.clear()

        cap.release()
        self.state.capturing = False
        self.state.log("Capture stopped")
