"""One-off: re-evaluate the 5 local clips with jacket-concealment-aware YOLOE prompts.

The stock prompt set only covers bag-based concealment (open bag / backpack). All four
theft clips here conceal items inside a jacket, so we extend the prompt set with
jacket/clothing concealment phrases mapped onto the existing canonical cues:
  - concealment-in-clothing phrases -> open_bag  (drives BagOpen + Concealment)
  - extra holding phrases           -> product_in_hand (drives RepeatedHandling/Concealment)

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

JACKET_PROMPTS = {
    **DEFAULT_YOLOE_PROMPTS,
    # Clothing-concealment cues (proxy onto open_bag so Concealment/BagOpen logic fires).
    "person hiding item inside jacket": "open_bag",
    "person putting object under clothing": "open_bag",
    "hand inside jacket": "open_bag",
    # Extra holding phrasings for small items / clothing items.
    "person holding a bottle": "product_in_hand",
    "person holding clothes": "product_in_hand",
}


def main() -> int:
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "ground_truth.json"), "r", encoding="utf-8") as f:
        gt = json.load(f)

    threshold = gt.get("alert_threshold", 70)
    dz = gt["default_zone"]
    default_zone = Zone(id="default", name=dz["name"], zone_type=dz["zoneType"],
                        polygon=[(float(x), float(y)) for x, y in dz["polygon"]])

    detector = build_detector("yoloe", "yoloe-11s-seg.pt", "cpu", yoloe_prompts=JACKET_PROMPTS)

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
        json.dump({"prompts": JACKET_PROMPTS, "alert_threshold": threshold,
                   "per_clip": per_clip}, f, indent=2)
    print(f"[jacket-test] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
