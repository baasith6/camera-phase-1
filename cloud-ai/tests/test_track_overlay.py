"""Unit tests for track overlay + event trackId wiring."""
import unittest

from app.detector import Detection
from app.events import _ev, _nearest_person_track, extract_events
from app.track_merge import build_person_id_remap, merge_fragmented_person_tracks
from app.track_overlay import OVERLAY_STRIDE, build_track_overlay
from app.zones import Zone


def _hv_zone() -> Zone:
    return Zone(
        id="hv-1",
        name="HV",
        zone_type="HighValue",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    )


def _emb(seed: float) -> list[float]:
    """Tiny L2-ish embedding for merge tests (same seed ≈ same person)."""
    return [seed, seed * 0.5, 1.0 - seed]


class TrackOverlayTests(unittest.TestCase):
    def test_build_track_overlay_keeps_person_boxes_and_ids(self):
        frames = [
            [Detection("person", 3, 0.5, 0.5, 0.9, x1=0.1, y1=0.2, x2=0.3, y2=0.8)],
            [Detection("bag", 1, 0.4, 0.4, 0.8, x1=0.2, y1=0.2, x2=0.5, y2=0.5)],
            [Detection("person", 3, 0.55, 0.5, 0.95, x1=0.12, y1=0.2, x2=0.32, y2=0.82)],
        ]
        overlay = build_track_overlay(10.0, frames)
        self.assertEqual(overlay["fps"], 10.0)
        self.assertEqual(overlay["stride"], OVERLAY_STRIDE)
        # stride=2 keeps source frames 0 and 2 (frame 1 bag-only is skipped)
        self.assertEqual(len(overlay["frames"]), 2)
        self.assertEqual(overlay["frames"][0][0]["trackId"], 3)
        self.assertEqual(overlay["frames"][0][0]["x1"], 0.1)
        self.assertEqual(overlay["frames"][1][0]["trackId"], 3)
        self.assertEqual(overlay["frames"][1][0]["x1"], 0.12)

    def test_ev_persists_track_id(self):
        ev = _ev("Dwell", "zone-1", 12.0, 0.9, "ts", track_id=11)
        self.assertEqual(ev["trackId"], 11)

    def test_extract_events_emits_dwell_track_id(self):
        frames = [
            [Detection("person", 9, 0.5, 0.5, 0.9, x1=0.4, y1=0.4, x2=0.6, y2=0.8)]
            for _ in range(5)
        ]
        events = extract_events(10.0, frames, [_hv_zone()])
        dwell = next(e for e in events if e["eventType"] == "Dwell")
        self.assertEqual(dwell["trackId"], 9)
        entry = next(e for e in events if e["eventType"] == "HighValueZoneEntry")
        self.assertEqual(entry["trackId"], 9)

    def test_nearest_person_track_picks_spatially_closest(self):
        dets = [
            Detection("person", 1, 0.2, 0.5, 0.9),
            Detection("person", 7, 0.8, 0.5, 0.9),
            Detection("open_bag", 54, 0.75, 0.55, 0.8),
        ]
        self.assertEqual(_nearest_person_track(0.75, 0.55, dets), 7)

    def test_bag_open_uses_person_id_not_bag_id(self):
        # Sustained open_bag (bag ByteTrack id 54) beside person id 1.
        frames = []
        for _ in range(12):
            frames.append([
                Detection("person", 1, 0.5, 0.5, 0.9, x1=0.4, y1=0.3, x2=0.6, y2=0.9),
                Detection("open_bag", 54, 0.55, 0.6, 0.85, x1=0.5, y1=0.5, x2=0.65, y2=0.75),
            ])
        events = extract_events(10.0, frames, [_hv_zone()])
        bag_open = next(e for e in events if e["eventType"] == "BagOpen")
        self.assertEqual(bag_open["trackId"], 1)
        self.assertNotEqual(bag_open["trackId"], 54)

    def test_bag_open_track_id_zero_when_no_person(self):
        frames = [
            [Detection("open_bag", 54, 0.5, 0.5, 0.9)]
            for _ in range(12)
        ]
        events = extract_events(10.0, frames, [_hv_zone()])
        bag_open = next(e for e in events if e["eventType"] == "BagOpen")
        self.assertEqual(bag_open["trackId"], 0)

    def test_merge_fragmented_person_tracks_remaps_later_id(self):
        emb = _emb(0.8)
        frames: list[list[Detection]] = []
        # Track 10 early in the clip.
        for _ in range(5):
            frames.append([
                Detection("person", 10, 0.5, 0.5, 0.9, embedding=emb,
                          x1=0.4, y1=0.3, x2=0.6, y2=0.9),
            ])
        # Gap, then ByteTrack re-IDs same body as 40.
        for _ in range(5):
            frames.append([])
        for _ in range(5):
            frames.append([
                Detection("person", 40, 0.52, 0.51, 0.9, embedding=emb,
                          x1=0.42, y1=0.32, x2=0.62, y2=0.92),
            ])

        remap = build_person_id_remap(frames)
        self.assertEqual(remap.get(40), 10)

        merge_fragmented_person_tracks(frames)
        later_ids = {d.track_id for dets in frames[10:] for d in dets if d.cue == "person"}
        self.assertEqual(later_ids, {10})

        overlay = build_track_overlay(10.0, frames)
        person_ids = {
            box["trackId"]
            for sampled in overlay["frames"]
            for box in sampled
        }
        self.assertEqual(person_ids, {10})

    def test_merge_without_embeddings_on_single_person_clip(self):
        """ByteTrack ID flips still merge when ReID is disabled (no embeddings)."""
        frames: list[list[Detection]] = []
        for _ in range(5):
            frames.append([Detection("person", 108, 0.5, 0.5, 0.9)])
        for _ in range(8):
            frames.append([])
        for _ in range(5):
            frames.append([Detection("person", 144, 0.53, 0.52, 0.9)])

        remap = build_person_id_remap(frames)
        self.assertEqual(remap.get(144), 108)
        merge_fragmented_person_tracks(frames)
        ids = {d.track_id for dets in frames for d in dets if d.cue == "person"}
        self.assertEqual(ids, {108})


if __name__ == "__main__":
    unittest.main()
