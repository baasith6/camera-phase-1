"""Video capture: rolling buffer + motion/person pre-filter + event clip cutting.

The connector never runs the full retail-cue model. This is only a lightweight
candidate selector (motion, optional person presence) to reduce useless uploads.
"""
import os
import time
import uuid
from collections import deque
from typing import Callable

import cv2
import numpy as np

from .config import Config
from .runtime import RuntimeState


class CapturePipeline:
    def __init__(self, cfg: Config, state: RuntimeState):
        self.cfg = cfg
        self.state = state
        self._stop = False
        self._person_hog = None
        if cfg.use_person_filter:
            self._person_hog = cv2.HOGDescriptor()
            self._person_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def stop(self) -> None:
        self._stop = True

    def _open(self):
        # Support explicit "file://" scheme used in seed data.
        src = self.cfg.source
        if src.startswith("file://"):
            src = src[len("file://"):]
        if os.path.exists(src) or src.startswith("rtsp"):
            return cv2.VideoCapture(src)
        return cv2.VideoCapture(src)

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

    def _write_clip(self, frames: list, fps: float) -> str | None:
        if not frames:
            return None
        os.makedirs(os.path.join(self.cfg.state_dir, "clips"), exist_ok=True)
        path = os.path.join(self.cfg.state_dir, "clips", f"{uuid.uuid4().hex}.mp4")
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h))
        for f in frames:
            writer.write(f)
        writer.release()
        return path

    def run(self, on_clip: Callable[[str, float, str], None]) -> None:
        """Blocking capture loop. Calls on_clip(path, duration_sec, trigger) per event."""
        cap = self._open()
        if not cap or not cap.isOpened():
            self.state.log(f"ERROR: cannot open source {self.cfg.source}")
            return

        src_fps = cap.get(cv2.CAP_PROP_FPS) or self.cfg.fps
        fps = self.cfg.fps if self.cfg.fps > 0 else (src_fps or 10)
        pre_len = int(self.cfg.pre_seconds * fps)
        post_len = int(self.cfg.post_seconds * fps)

        rolling: deque = deque(maxlen=pre_len)
        bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=25, detectShadows=False)
        last_trigger = 0.0
        self.state.capturing = True
        self.state.log(f"Capture started (fps={fps:.1f}, pre={pre_len}f, post={post_len}f)")

        while not self._stop:
            ok, frame = cap.read()
            if not ok:
                if self.cfg.loop:
                    cap.release()
                    cap = self._open()
                    continue
                break

            rolling.append(frame.copy())
            fgmask = bg.apply(frame)
            now = time.time()

            if self._has_motion(fgmask) and (now - last_trigger) >= self.cfg.cooldown_seconds:
                if not self._has_person(frame):
                    continue
                last_trigger = now
                self.state.log("Motion trigger -> cutting event clip")

                # Collect post-event frames.
                post_frames = []
                for _ in range(post_len):
                    ok2, f2 = cap.read()
                    if not ok2:
                        if self.cfg.loop:
                            cap.release()
                            cap = self._open()
                            continue
                        break
                    post_frames.append(f2.copy())

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
