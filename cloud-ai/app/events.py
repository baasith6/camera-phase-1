"""Extract Phase 1A camera risk events from tracked detections + zones.

Emits the full Phase 1A camera-only pattern set (10 patterns). Cue-aware: open-vocabulary
cues (open_bag, product_in_hand from YOLOE) are used directly; closed-set backends fall
back to generic bag + person zone heuristics. Patterns that truly need POS/staffing
(shelf-pickup no-POS-scan, low-staff removal) use camera-only proxies; the POS/staff
cross-check is a Phase 1B concern.

Event types (match backend AiEventType):
  HighValueZoneEntry, Dwell, RepeatedHandling, BagOpen,
  Concealment, ExitWithoutCheckout, ShelfPickupNoCheckout,
  BlindSpotMovement, GroupDistraction, HighValueActivity, LowStaffRemoval
"""
from datetime import datetime, timezone

from .detector import Detection
from .zones import Zone, zones_containing

HIGH_VALUE = "HighValue"
SHELF = "Shelf"
EXIT = "Exit"
CHECKOUT = "Checkout"
BLIND_SPOT = "BlindSpot"
SHELF_LIKE = {SHELF, HIGH_VALUE}


def extract_events(fps: float, frames: list[list[Detection]], zones: list[Zone]) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    events: list[dict] = []
    if not frames:
        return events

    # Per person-track timeline: track_id -> [(idx, set(zone_types), {zone_type: zone_id})]
    per_track: dict[int, list[tuple[int, set, dict]]] = {}
    track_embeddings: dict[int, list[float]] = {}

    # Bag-open signal (prefer explicit open_bag cue; fall back to generic bag).
    open_bag_zone: str | None = None
    open_bag_conf = 0.0
    open_bag_last_idx = -1
    bag_fallback_zone: str | None = None
    bag_fallback_conf = 0.0
    bag_last_idx = -1

    # Product-in-hand handling episodes + first occurrence (for concealment ordering).
    handling_episodes = 0
    handling_zone: str | None = None
    prev_handling = False
    product_first_idx = -1
    product_in_shelf = False

    # High-value zone activity categories.
    hv_has_person = hv_has_product = hv_has_bag = False
    hv_zone_id: str | None = None

    # Group distraction: max simultaneous persons in shelf-like zones.
    max_group = 0
    group_zone: str | None = None

    for idx, dets in enumerate(frames):
        handling_now = False
        persons_in_shelf = 0
        frame_shelf_zone: str | None = None

        for d in dets:
            containing = zones_containing(d.cx, d.cy, zones)
            shelf_zones = [z for z in containing if z.zone_type in SHELF_LIKE]
            hv_zone = next((z for z in containing if z.zone_type == HIGH_VALUE), None)

            if d.cue == "person":
                types = {z.zone_type for z in containing}
                by_type = {z.zone_type: z.id for z in containing}
                per_track.setdefault(d.track_id, []).append((idx, types, by_type))
                if d.embedding and d.track_id not in track_embeddings:
                    track_embeddings[d.track_id] = d.embedding
                if shelf_zones:
                    persons_in_shelf += 1
                    frame_shelf_zone = frame_shelf_zone or shelf_zones[0].id
                if hv_zone is not None:
                    hv_has_person = True
                    hv_zone_id = hv_zone_id or hv_zone.id

            elif d.cue == "open_bag":
                for z in shelf_zones:
                    if d.conf >= open_bag_conf:
                        open_bag_zone, open_bag_conf, open_bag_last_idx = z.id, d.conf, idx
                if hv_zone is not None:
                    hv_has_bag = True

            elif d.cue == "bag":
                for z in shelf_zones:
                    if d.conf >= bag_fallback_conf:
                        bag_fallback_zone, bag_fallback_conf, bag_last_idx = z.id, d.conf, idx
                if hv_zone is not None:
                    hv_has_bag = True

            elif d.cue == "product_in_hand":
                if shelf_zones:
                    handling_now = True
                    product_in_shelf = True
                    handling_zone = handling_zone or shelf_zones[0].id
                    if product_first_idx < 0:
                        product_first_idx = idx
                if hv_zone is not None:
                    hv_has_product = True

        if handling_now and not prev_handling:
            handling_episodes += 1
        prev_handling = handling_now

        if persons_in_shelf > max_group:
            max_group = persons_in_shelf
            group_zone = frame_shelf_zone

    # --- Per-track derived signals ---
    high_value_seen_zone: str | None = None
    max_dwell_seconds = 0.0
    max_dwell_zone: str | None = None
    max_reentries = 0
    reentry_zone: str | None = None

    exit_no_checkout_zone: str | None = None
    blind_spot_zone: str | None = None

    for _track, timeline in per_track.items():
        run = best_run = 0
        best_zone = None
        prev_in = False
        reentries = 0

        visited: set[str] = set()
        first_idx_by_type: dict[str, int] = {}
        exit_zone_id: str | None = None
        blindspot_zone_id: str | None = None

        for (idx, types, by_type) in timeline:
            hv = by_type.get(HIGH_VALUE)
            if hv is not None:
                high_value_seen_zone = high_value_seen_zone or hv
                run += 1
                if run > best_run:
                    best_run, best_zone = run, hv
            else:
                run = 0

            in_shelf = bool(types & SHELF_LIKE)
            if in_shelf and not prev_in:
                reentries += 1
                shelf_id = by_type.get(HIGH_VALUE) or by_type.get(SHELF)
                reentry_zone = reentry_zone or shelf_id
            prev_in = in_shelf

            for t in types:
                visited.add(t)
                first_idx_by_type.setdefault(t, idx)
            if EXIT in types:
                exit_zone_id = exit_zone_id or by_type.get(EXIT)
            if BLIND_SPOT in types:
                blindspot_zone_id = blindspot_zone_id or by_type.get(BLIND_SPOT)

        dwell_seconds = best_run / max(fps, 1e-6)
        if dwell_seconds > max_dwell_seconds:
            max_dwell_seconds, max_dwell_zone = dwell_seconds, best_zone
        max_reentries = max(max_reentries, reentries)

        shelf_visited = bool(visited & SHELF_LIKE)
        shelf_first = min((first_idx_by_type[t] for t in (SHELF_LIKE & visited)), default=None)

        # Exit after shelf interaction, never passing checkout.
        if shelf_visited and EXIT in visited and CHECKOUT not in visited:
            if shelf_first is not None and first_idx_by_type.get(EXIT, 1 << 30) >= shelf_first:
                exit_no_checkout_zone = exit_no_checkout_zone or exit_zone_id or reentry_zone

        # Blind-spot movement (bonus signal when it follows a shelf interaction).
        if BLIND_SPOT in visited:
            blind_spot_zone = blind_spot_zone or blindspot_zone_id

    # --- Emit events (all evidence is observable-signal language, never conclusions) ---
    if high_value_seen_zone is not None:
        events.append(_ev("HighValueZoneEntry", high_value_seen_zone, 1.0, 0.9, now))

    if max_dwell_seconds > 0:
        events.append(_ev("Dwell", max_dwell_zone, round(max_dwell_seconds, 1), 0.9, now))

    if handling_episodes > 0:
        events.append(_ev("RepeatedHandling", handling_zone, float(handling_episodes), 0.85, now))
    elif max_reentries > 0:
        events.append(_ev("RepeatedHandling", reentry_zone, float(max_reentries), 0.7, now))

    # Concealment: item handled at a shelf, then a bag/open-bag cue appears afterwards.
    latest_bag_idx = max(open_bag_last_idx, bag_last_idx)
    concealment_zone = open_bag_zone or bag_fallback_zone or handling_zone
    if product_in_shelf and product_first_idx >= 0 and latest_bag_idx > product_first_idx:
        events.append(_ev("Concealment", concealment_zone, 1.0, 0.7, now))

    # Exit without checkout, and its stronger "carried a product out" variant.
    if exit_no_checkout_zone is not None:
        # Find the track ID that triggered this to grab the embedding
        trigger_embedding = None
        for track_id, timeline in per_track.items():
            visited = set()
            for (_, types, _) in timeline:
                visited.update(types)
            if EXIT in visited and CHECKOUT not in visited and bool(visited & SHELF_LIKE):
                trigger_embedding = track_embeddings.get(track_id)
                break

        if product_in_shelf:
            events.append(_ev("ShelfPickupNoCheckout", exit_no_checkout_zone, 1.0, 0.7, now, embedding=trigger_embedding))
        else:
            events.append(_ev("ExitWithoutCheckout", exit_no_checkout_zone, 1.0, 0.7, now, embedding=trigger_embedding))

    if blind_spot_zone is not None:
        events.append(_ev("BlindSpotMovement", blind_spot_zone, 1.0, 0.8, now))

    if max_group >= 2:
        events.append(_ev("GroupDistraction", group_zone, float(max_group), 0.7, now))

    hv_activity = int(hv_has_person) + int(hv_has_product) + int(hv_has_bag)
    if hv_activity >= 2:
        events.append(_ev("HighValueActivity", hv_zone_id, float(hv_activity), 0.8, now))

    # Low-staff removal proxy: a product was removed at a shelf.
    if product_in_shelf:
        trigger_embedding = None
        for track_id, timeline in per_track.items():
            visited = set()
            for (_, types, _) in timeline:
                visited.update(types)
            if bool(visited & SHELF_LIKE):
                trigger_embedding = track_embeddings.get(track_id)
                break
        events.append(_ev("LowStaffRemoval", handling_zone, 1.0, 0.6, now, embedding=trigger_embedding))

    # Bag-open (prefer explicit open_bag cue; else generic bag near a shelf).
    if open_bag_zone is not None:
        events.append(_ev("BagOpen", open_bag_zone, 1.0, round(open_bag_conf, 3), now))
    elif bag_fallback_zone is not None:
        events.append(_ev("BagOpen", bag_fallback_zone, 1.0, round(bag_fallback_conf, 3), now))

    return events


def _ev(event_type: str, zone_id: str | None, value: float, conf: float, ts: str, embedding: list[float] = None) -> dict:
    ev = {
        "trackId": 0,
        "zoneId": zone_id,
        "eventType": event_type,
        "value": value,
        "confidence": conf,
        "startTs": ts,
        "endTs": ts,
        "evidenceFrames": [],
    }
    if embedding:
        ev["embedding"] = embedding
    return ev
