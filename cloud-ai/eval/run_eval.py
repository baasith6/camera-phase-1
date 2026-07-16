"""Offline evaluation harness for the Phase 1A camera pipeline.

Runs the same detection + tracking + event-extraction + risk-scoring path used in
production over a set of labeled sample clips, and reports precision / recall / F1 / FPR.
Output mirrors the second brain eval template so results can be ingested into the wiki.

Usage:
    cd cloud-ai
    python -m eval.run_eval                         # default: yoloe
    python -m eval.run_eval --backend yolo26 --model yolo26s.pt
    python -m eval.run_eval --backend rfdetr
"""
import argparse
import json
import os
import time

from app.detector import build_detector
from app.events import extract_events
from app.zones import Zone

# Local mirror of the backend Risk Engine starter weights (keep in sync with RiskEngine.cs).
WEIGHTS = {
    "HighValueZoneEntry": 15, "Dwell": 20, "RepeatedHandling": 15, "BagOpen": 20,
    "Concealment": 20, "ExitWithoutCheckout": 20, "ShelfPickupNoCheckout": 25,
    "BlindSpotMovement": 15, "GroupDistraction": 10, "HighValueActivity": 15,
    "LowStaffRemoval": 10,
}
DWELL_THRESHOLD = 30.0
DWELL_MAX = 90.0
REPEATED_THRESHOLD = 3
GROUP_SIZE_THRESHOLD = 3

# Events whose weight is applied as-is when present.
FLAT_EVENTS = {
    "BagOpen", "Concealment", "ExitWithoutCheckout", "ShelfPickupNoCheckout",
    "BlindSpotMovement", "HighValueActivity",
}


def score_events(events: list[dict]) -> int:
    """Mirror of RiskEngine.Score. Note: LowStaffRemoval's time-gate is approximated as
    always-on here since eval clips carry no real wall-clock time."""
    score = 0
    seen = set()
    for e in events:
        t = e["eventType"]
        v = e["value"]
        if t == "HighValueZoneEntry" and t not in seen:
            score += WEIGHTS[t]
        elif t == "Dwell" and v >= DWELL_THRESHOLD:
            span = max(1.0, DWELL_MAX - DWELL_THRESHOLD)
            frac = min(1.0, max(0.0, (v - DWELL_THRESHOLD) / span))
            score += int(round(10 + frac * (WEIGHTS[t] - 10)))
        elif t == "RepeatedHandling" and v >= REPEATED_THRESHOLD:
            score += WEIGHTS[t]
        elif t == "GroupDistraction" and v >= GROUP_SIZE_THRESHOLD:
            score += WEIGHTS[t]
        elif t == "LowStaffRemoval":
            score += WEIGHTS[t]  # time-gate approximated as always-on in eval
        elif t in FLAT_EVENTS:
            score += WEIGHTS[t]
        seen.add(t)
    return score


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default=os.getenv("CLOUD_AI_MODEL_BACKEND", "yoloe"),
                   help="yoloe | yolo26 | rfdetr")
    p.add_argument("--model", default=os.getenv("CLOUD_AI_MODEL", "yoloe-11s-seg.pt"))
    p.add_argument("--device", default=os.getenv("CLOUD_AI_DEVICE", "cpu"))
    p.add_argument("--gt", default=os.path.join(os.path.dirname(__file__), "ground_truth.json"))
    args = p.parse_args()

    with open(args.gt, "r", encoding="utf-8") as f:
        gt = json.load(f)

    threshold = gt.get("alert_threshold", 70)
    dz = gt["default_zone"]
    default_zone = Zone(id="default", name=dz["name"], zone_type=dz["zoneType"],
                        polygon=[(float(x), float(y)) for x, y in dz["polygon"]])

    base_dir = os.path.dirname(args.gt)
    detector = build_detector(args.backend, args.model, args.device)

    tp = fp = tn = fn = 0
    per_clip = []
    scored = skipped = 0

    for clip in gt["clips"]:
        path = os.path.join(base_dir, clip["file"])
        if not os.path.exists(path):
            print(f"[eval] SKIP missing clip: {path}")
            skipped += 1
            continue

        t0 = time.time()
        fps, frames = detector.track_clip(path)
        events = extract_events(fps, frames, [default_zone])
        score = score_events(events)
        predicted_positive = score >= threshold
        gt_positive = clip["label"] == "shoplifting"

        if predicted_positive and gt_positive:
            tp += 1
        elif predicted_positive and not gt_positive:
            fp += 1
        elif not predicted_positive and not gt_positive:
            tn += 1
        else:
            fn += 1

        scored += 1
        per_clip.append({
            "id": clip["id"],
            "file": clip["file"],
            "gt_label": clip["label"],
            "score": score,
            "predicted": "alert" if predicted_positive else "no_alert",
            "events": [e["eventType"] for e in events],
            "elapsed_s": round(time.time() - t0, 2),
        })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    results = {
        "backend": args.backend,
        "model": args.model,
        "alert_threshold": threshold,
        "num_scored": scored,
        "num_skipped": skipped,
        "metrics": {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "fpr": round(fpr, 4),
        },
        "per_clip": per_clip,
    }

    out = os.path.join(base_dir, "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results["metrics"], indent=2))
    print(f"[eval] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
