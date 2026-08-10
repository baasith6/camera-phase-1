"""Optional live person tracker for connector MJPEG overlays.

Uses Ultralytics YOLO + ByteTrack (person class only). Disabled cleanly when the
dependency/model is unavailable so motion capture still works.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LiveTrack:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "trackId": self.track_id,
            "x1": round(self.x1, 4),
            "y1": round(self.y1, 4),
            "x2": round(self.x2, 4),
            "y2": round(self.y2, 4),
            "conf": round(self.conf, 3),
        }


class LiveTracker:
    """Stateful ByteTrack wrapper; call update() on processing-resolution frames."""

    def __init__(self, model_path: str = "yolov8n.pt", device: str = "cpu", stride: int = 2):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.device = device
        self.stride = max(1, int(stride))
        self._frame_i = 0
        self._last: list[LiveTrack] = []

    def update(self, frame) -> list[LiveTrack]:
        self._frame_i += 1
        if self._frame_i % self.stride != 0 and self._last:
            return list(self._last)

        h, w = frame.shape[:2]
        results = self.model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],  # COCO person
            device=self.device,
            verbose=False,
        )
        tracks: list[LiveTrack] = []
        if not results:
            self._last = tracks
            return tracks

        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None or boxes.xyxy is None:
            self._last = tracks
            return tracks

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else []
        ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else [-1] * len(xyxy)
        for i in range(len(xyxy)):
            tid = int(ids[i]) if i < len(ids) else -1
            if tid < 0:
                continue
            x1, y1, x2, y2 = xyxy[i]
            tracks.append(LiveTrack(
                track_id=tid,
                x1=float(x1 / max(1, w)),
                y1=float(y1 / max(1, h)),
                x2=float(x2 / max(1, w)),
                y2=float(y2 / max(1, h)),
                conf=float(confs[i]) if i < len(confs) else 0.0,
            ))
        self._last = tracks
        return list(tracks)


def try_build_live_tracker(
    enabled: bool,
    model_path: str = "yolov8n.pt",
    device: str = "cpu",
    stride: int = 2,
) -> LiveTracker | None:
    if not enabled:
        return None
    try:
        return LiveTracker(model_path=model_path, device=device, stride=stride)
    except Exception as exc:  # noqa: BLE001
        print(f"[live-tracker] disabled: {exc}", flush=True)
        return None
