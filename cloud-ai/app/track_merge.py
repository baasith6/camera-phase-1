"""Merge fragmented person ByteTrack IDs within a single clip.

Uses ReID cosine similarity when embeddings exist. Falls back to spatial/temporal
continuity (especially for single-person clips) so IDs stay stable even when
CLOUD_AI_ENABLE_REID is off.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .detector import Detection

# Cosine similarity threshold for treating two person tracks as the same body.
DEFAULT_SIMILARITY = 0.75
# Max gap (frames) between end of earlier track and start of later track.
DEFAULT_MAX_GAP_FRAMES = 90
# Tighter gap when merging without embeddings in multi-person clips.
SHORT_GAP_NO_REID = 20
# Max normalized center distance between earlier last position and later first position.
DEFAULT_MAX_SPATIAL = 0.35


@dataclass
class _TrackStats:
    embeddings: list[list[float]] = field(default_factory=list)
    first_idx: int = 10**9
    last_idx: int = -1
    first_xy: tuple[float, float] = (0.0, 0.0)
    last_xy: tuple[float, float] = (0.0, 0.0)


def _mean_embedding(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    if dim == 0 or any(len(v) != dim for v in vectors):
        return None
    acc = [0.0] * dim
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += float(x)
    n = float(len(vectors))
    return [x / n for x in acc]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def _collect_person_stats(frames: list[list[Detection]]) -> dict[int, _TrackStats]:
    stats: dict[int, _TrackStats] = {}
    for idx, dets in enumerate(frames):
        for d in dets:
            if d.cue != "person" or d.track_id < 0:
                continue
            st = stats.setdefault(d.track_id, _TrackStats())
            if d.embedding:
                st.embeddings.append(d.embedding)
            if idx < st.first_idx:
                st.first_idx = idx
                st.first_xy = (d.cx, d.cy)
            if idx >= st.last_idx:
                st.last_idx = idx
                st.last_xy = (d.cx, d.cy)
    return stats


def _is_single_person_at_a_time(frames: list[list[Detection]]) -> bool:
    """True when no frame contains two simultaneous person detections."""
    for dets in frames:
        n = sum(1 for d in dets if d.cue == "person" and d.track_id >= 0)
        if n > 1:
            return False
    return True


def build_person_id_remap(
    frames: list[list[Detection]],
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    max_spatial: float = DEFAULT_MAX_SPATIAL,
) -> dict[int, int]:
    """Return mapping fragmented_id -> canonical earlier person id (identity omitted)."""
    stats = _collect_person_stats(frames)
    if len(stats) < 2:
        return {}

    means = {tid: _mean_embedding(st.embeddings) for tid, st in stats.items()}
    single_person = _is_single_person_at_a_time(frames)
    candidates = sorted(stats.keys(), key=lambda tid: (stats[tid].first_idx, tid))
    parent = {tid: tid for tid in candidates}

    def find(tid: int) -> int:
        while parent[tid] != tid:
            parent[tid] = parent[parent[tid]]
            tid = parent[tid]
        return tid

    for later in candidates:
        best_earlier: int | None = None
        best_score = -1.0
        later_st = stats[later]
        later_mean = means.get(later)

        for earlier in candidates:
            if earlier == later:
                continue
            earlier_st = stats[earlier]
            if earlier_st.first_idx >= later_st.first_idx:
                continue
            gap = later_st.first_idx - earlier_st.last_idx
            if gap < 0 or gap > max_gap_frames:
                continue

            dx = later_st.first_xy[0] - earlier_st.last_xy[0]
            dy = later_st.first_xy[1] - earlier_st.last_xy[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > max_spatial:
                continue

            earlier_mean = means.get(earlier)
            if earlier_mean is not None and later_mean is not None:
                sim = _cosine(earlier_mean, later_mean)
                if sim < similarity_threshold:
                    continue
                score = sim
            elif single_person:
                # One body in the clip: spatial continuity is enough.
                score = 1.0 - dist
            else:
                # Multi-person without ReID: only stitch brief tracker losses.
                if gap > SHORT_GAP_NO_REID:
                    continue
                score = 1.0 - dist

            if score > best_score:
                best_score = score
                best_earlier = earlier

        if best_earlier is not None:
            parent[find(later)] = find(best_earlier)

    remap: dict[int, int] = {}
    for tid in candidates:
        root = find(tid)
        if root != tid:
            remap[tid] = root
    return remap


def merge_fragmented_person_tracks(
    frames: list[list[Detection]],
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    max_spatial: float = DEFAULT_MAX_SPATIAL,
) -> list[list[Detection]]:
    """In-place remap person track_ids so one body keeps one canonical ID per clip."""
    remap = build_person_id_remap(
        frames,
        similarity_threshold=similarity_threshold,
        max_gap_frames=max_gap_frames,
        max_spatial=max_spatial,
    )
    if not remap:
        return frames
    for dets in frames:
        for d in dets:
            if d.cue != "person":
                continue
            mapped = remap.get(d.track_id)
            if mapped is not None:
                d.track_id = mapped
    return frames
