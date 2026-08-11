"""Build compact per-frame person track overlays for clip review UI."""

from .detector import Detection

# Keep payload small while remaining smooth enough for canvas redraw.
OVERLAY_STRIDE = 2


def build_track_overlay(fps: float, frames: list[list[Detection]]) -> dict:
    """Return JSON-serializable overlay: person boxes + ByteTrack IDs per sampled frame."""
    sampled: list[list[dict]] = []
    for idx, dets in enumerate(frames):
        if idx % OVERLAY_STRIDE != 0:
            continue
        persons = []
        for d in dets:
            if d.cue != "person":
                continue
            persons.append({
                "trackId": int(d.track_id),
                "cue": d.cue,
                "x1": round(float(d.x1), 4),
                "y1": round(float(d.y1), 4),
                "x2": round(float(d.x2), 4),
                "y2": round(float(d.y2), 4),
                "conf": round(float(d.conf), 3),
            })
        sampled.append(persons)
    return {
        "fps": float(fps),
        "stride": OVERLAY_STRIDE,
        "frames": sampled,
    }
