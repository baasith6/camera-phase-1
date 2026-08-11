"""Pluggable detection + tracking over a clip.

The connector never runs these models; detection happens only in the cloud on selected
clips. All backends emit the same canonical retail cues so the rest of the pipeline
(event extraction, risk scoring) is backend-agnostic:

    person | bag | open_bag | product_in_hand

Backends:
  - yoloe  (default): Ultralytics YOLOE open-vocabulary. Detects open_bag / product_in_hand
                      by text prompt, no training required.
  - yolo26 / yolo   : Ultralytics closed-set YOLO (COCO). Maps person + bag only.
  - rfdetr (optional): Roboflow RF-DETR (Apache-2.0). Per-frame detection, person + bag.
"""
from dataclasses import dataclass
from typing import Callable, Protocol

# Canonical retail cues used across the whole pipeline.
CANONICAL_CUES = {"person", "bag", "open_bag", "product_in_hand", "concealment"}

# Closed-set COCO class id -> canonical cue (YOLO / RF-DETR).
COCO_TO_CUE = {
    0: "person",
    24: "bag",   # backpack
    26: "bag",   # handbag
    28: "bag",   # suitcase
}

# Default open-vocabulary prompts (YOLOE) -> canonical cue.
DEFAULT_YOLOE_PROMPTS: dict[str, str] = {
    "person": "person",
    "backpack": "bag",
    "handbag": "bag",
    "open bag": "open_bag",
    "open backpack": "open_bag",
    # Direct concealment cues: the phrase itself encodes item-being-hidden, so these
    # map to a dedicated cue. A plain open bag is NOT concealment — only the act of
    # putting/hiding an item inside clothing or a bag is.
    "person hiding item inside jacket": "concealment",
    "person putting object under clothing": "concealment",
    "hand inside jacket": "concealment",
    "product in hand": "product_in_hand",
    "item in hand": "product_in_hand",
    "person holding a bottle": "product_in_hand",
    "person holding clothes": "product_in_hand",
}


@dataclass
class Detection:
    cue: str
    track_id: int
    cx: float   # normalized center x (0..1)
    cy: float   # normalized center y (0..1)
    conf: float
    embedding: list[float] = None
    # Normalized bounding box (0..1); used for track overlays / Re-ID crops.
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0


class DetectorBackend(Protocol):
    @property
    def version(self) -> str: ...
    def track_clip(self, clip_path: str, reid_extractor=None) -> tuple[float, list[list["Detection"]]]: ...


def _clip_fps(clip_path: str) -> float:
    """Read container FPS from the clip; fall back to 10 if missing/invalid."""
    import cv2
    cap = cv2.VideoCapture(clip_path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        cap.release()
    return fps if fps > 1e-3 else 10.0


def _ultralytics_results_to_frames(
    results, index_to_cue: Callable[[int], str | None],
    reid_extractor=None,
    fps: float = 10.0,
) -> tuple[float, list[list[Detection]]]:
    """Shared conversion for Ultralytics streaming track results."""
    frames: list[list[Detection]] = []
    for res in results:
        h, w = res.orig_shape if hasattr(res, "orig_shape") else (1, 1)
        orig_img = res.orig_img if hasattr(res, "orig_img") else None
        dets: list[Detection] = []
        boxes = getattr(res, "boxes", None)
        if boxes is not None and boxes.xyxy is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            clss = boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else []
            confs = boxes.conf.cpu().numpy() if boxes.conf is not None else []
            ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else [-1] * len(xyxy)
            for i in range(len(xyxy)):
                cls_id = int(clss[i]) if i < len(clss) else -1
                cue = index_to_cue(cls_id)
                if cue is None:
                    continue
                x1, y1, x2, y2 = xyxy[i]
                nx1 = float(x1 / max(1, w))
                ny1 = float(y1 / max(1, h))
                nx2 = float(x2 / max(1, w))
                ny2 = float(y2 / max(1, h))
                cx = float(((x1 + x2) / 2.0) / max(1, w))
                cy = float(((y1 + y2) / 2.0) / max(1, h))

                embedding = None
                if cue == "person" and reid_extractor is not None and orig_img is not None:
                    try:
                        box_w = (x2 - x1) / max(1, w)
                        box_h = (y2 - y1) / max(1, h)
                        embedding = reid_extractor.extract(orig_img, cx, cy, box_w, box_h)
                    except Exception as e:
                        print(f"ReID extraction failed: {e}")

                dets.append(Detection(
                    cue=cue,
                    track_id=int(ids[i]) if i < len(ids) else -1,
                    cx=cx,
                    cy=cy,
                    conf=float(confs[i]) if i < len(confs) else 0.0,
                    embedding=embedding,
                    x1=nx1,
                    y1=ny1,
                    x2=nx2,
                    y2=ny2,
                ))
        frames.append(dets)
    return fps, frames


class YoloBackend:
    """Closed-set Ultralytics YOLO (e.g. yolo26s.pt, yolov8n.pt). person + bag only."""

    def __init__(self, model_path: str, device: str = "cpu"):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.model_path = model_path
        self.device = device

    @property
    def version(self) -> str:
        return f"yolo:{self.model_path}"

    def track_clip(self, clip_path: str, reid_extractor=None):
        fps = _clip_fps(clip_path)
        results = self.model.track(
            source=clip_path, stream=True, persist=True, tracker="bytetrack.yaml",
            classes=list(COCO_TO_CUE.keys()), device=self.device, verbose=False,
        )
        return _ultralytics_results_to_frames(
            results, lambda c: COCO_TO_CUE.get(c), reid_extractor=reid_extractor, fps=fps,
        )


class YoloeBackend:
    """Open-vocabulary Ultralytics YOLOE. Detects retail cues by text prompt."""

    def __init__(self, model_path: str, device: str = "cpu", prompts: dict[str, str] | None = None):
        from ultralytics import YOLOE
        self.model = YOLOE(model_path)
        self.model_path = model_path
        self.device = device
        self.prompt_to_cue = prompts or DEFAULT_YOLOE_PROMPTS
        self.prompt_names = list(self.prompt_to_cue.keys())
        # Register the open-vocabulary classes (reparameterized -> zero inference overhead).
        self.model.set_classes(self.prompt_names, self.model.get_text_pe(self.prompt_names))

    @property
    def version(self) -> str:
        return f"yoloe:{self.model_path}"

    def _index_to_cue(self, idx: int) -> str | None:
        if 0 <= idx < len(self.prompt_names):
            return self.prompt_to_cue.get(self.prompt_names[idx])
        return None

    def track_clip(self, clip_path: str, reid_extractor=None):
        fps = _clip_fps(clip_path)
        results = self.model.track(
            source=clip_path, stream=True, persist=True, tracker="bytetrack.yaml",
            device=self.device, verbose=False,
        )
        return _ultralytics_results_to_frames(
            results, self._index_to_cue, reid_extractor=reid_extractor, fps=fps,
        )


class RfDetrBackend:
    """Optional Roboflow RF-DETR (Apache-2.0). Per-frame detection (no built-in tracking);
    all detections share a single pseudo-track, which is sufficient for zone dwell logic."""

    def __init__(self, model_path: str = "", device: str = "cpu"):
        from rfdetr import RFDETRBase  # lazy import; only required when selected
        self.model = RFDETRBase()
        self.model_path = model_path or "rfdetr-base"
        self.device = device

    @property
    def version(self) -> str:
        return f"rfdetr:{self.model_path}"

    def track_clip(self, clip_path: str):
        import cv2
        cap = cv2.VideoCapture(clip_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
        frames: list[list[Detection]] = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            dets: list[Detection] = []
            preds = self.model.predict(frame, threshold=0.4)
            xyxy = getattr(preds, "xyxy", [])
            class_ids = getattr(preds, "class_id", [])
            confs = getattr(preds, "confidence", [])
            for i in range(len(xyxy)):
                cue = COCO_TO_CUE.get(int(class_ids[i])) if i < len(class_ids) else None
                if cue is None:
                    continue
                x1, y1, x2, y2 = xyxy[i]
                dets.append(Detection(
                    cue=cue,
                    track_id=-1,
                    cx=float(((x1 + x2) / 2.0) / max(1, w)),
                    cy=float(((y1 + y2) / 2.0) / max(1, h)),
                    conf=float(confs[i]) if i < len(confs) else 0.0,
                    x1=float(x1 / max(1, w)),
                    y1=float(y1 / max(1, h)),
                    x2=float(x2 / max(1, w)),
                    y2=float(y2 / max(1, h)),
                ))
            frames.append(dets)
        cap.release()
        return fps, frames


def build_detector(backend: str, model_path: str, device: str = "cpu",
                   yoloe_prompts: dict[str, str] | None = None) -> DetectorBackend:
    backend = (backend or "yoloe").lower()
    if backend == "yoloe":
        return YoloeBackend(model_path, device, yoloe_prompts)
    if backend in ("yolo", "yolo26", "yolov8", "yolo11"):
        return YoloBackend(model_path, device)
    if backend == "rfdetr":
        return RfDetrBackend(model_path, device)
    raise ValueError(f"Unknown MODEL_BACKEND '{backend}' (expected yoloe | yolo26 | rfdetr)")
