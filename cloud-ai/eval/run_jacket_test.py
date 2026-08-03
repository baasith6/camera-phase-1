"""Re-evaluate local clips using production DEFAULT_YOLOE_PROMPTS (same as Azure cloud-ai).

Jacket/clothing phrases map to the concealment cue (not open_bag). Matches
cloud-ai/app/detector.py and the deployed Azure cloud-ai container.

Usage:  cd cloud-ai && python -m eval.run_jacket_test
"""
import json
import os
import time
from collections import Counter

from app.detector import build_detector, DEFAULT_YOLOE_PROMPTS
from app.events import extract_events
from app.zones import Zone
from eval.run_eval import score_events


def main() -> int:
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "ground_truth.json"), "r", encoding="utf-8") as f:
        gt = json.load(f)

    threshold = gt.get("alert_threshold", 70)
    dz = gt["default_zone"]
    default_zone = Zone(id="default", name=dz["name"], zone_type=dz["zoneType"],
                        polygon=[(float(x), float(y)) for x, y in dz["polygon"]])

    detector = build_detector("yoloe", "yoloe-11s-seg.pt", "cpu", yoloe_prompts=DEFAULT_YOLOE_PROMPTS)

    per_clip = []
    for clip in gt["clips"]:
        path = os.path.join(base_dir, clip["file"])
        t0 = time.time()
        fps, frames = detector.track_clip(path)
        cues = Counter(d.cue for fr in frames for d in fr)
        events = extract_events(fps, frames, [default_zone])
        score = score_events(events)
        per_clip.append({
            "id": clip["id"],
            "gt_label": clip["label"],
            "score": score,
            "predicted": "alert" if score >= threshold else "no_alert",
            "cue_counts": dict(cues),
            "events": [f'{e["eventType"]}={e["value"]}' for e in events],
            "elapsed_s": round(time.time() - t0, 2),
        })
        print(json.dumps(per_clip[-1]))

    out = os.path.join(base_dir, "results_jacket_prompts.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"prompts": DEFAULT_YOLOE_PROMPTS, "alert_threshold": threshold,
                   "per_clip": per_clip}, f, indent=2)
    print(f"[jacket-test] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
