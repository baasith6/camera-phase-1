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

# Bag/concealment cues must be seen on at least this many detections before they can
# fire BagOpen / Concealment / count toward HighValueActivity. Rejects one-off false
# positives (e.g. a normal shopper adjusting a jacket for a few frames).
SUSTAINED_CUE_DETECTIONS = 10


def _nearest_person_track(cx: float, cy: float, dets: list[Detection]) -> int:
    """Return the person ByteTrack ID closest to (cx, cy), or 0 if none in frame.

    Cue events must attribute to a person ID (matching the clip overlay), never to the
    bag/cue's own ByteTrack ID which shares the same ID space.
    """
    best_id = 0
    best_dist = float("inf")
    for p in dets:
        if p.cue != "person" or p.track_id < 0:
            continue
        dist = (p.cx - cx) ** 2 + (p.cy - cy) ** 2
        if dist < best_dist:
            best_dist = dist
            best_id = int(p.track_id)
    return best_id


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
    open_bag_dets = 0
    open_bag_track = 0
    bag_fallback_zone: str | None = None
    bag_fallback_conf = 0.0
    bag_last_idx = -1
    bag_dets = 0
    bag_fallback_track = 0

    # Product-in-hand handling episodes + first occurrence (for concealment ordering).
    handling_episodes = 0
    handling_zone: str | None = None
    handling_track = 0
    prev_handling = False
    product_first_idx = -1
    product_in_shelf = False

    # Direct concealment cue (item being hidden inside jacket/clothing).
    conceal_dets = 0
    conceal_zone: str | None = None
    conceal_last_idx = -1
    conceal_in_hv = False
    conceal_track = 0

    # High-value zone activity categories.
    hv_has_person = hv_has_product = hv_has_bag = False
    hv_zone_id: str | None = None
    hv_person_track = 0

    # Group distraction: max simultaneous persons in shelf-like zones.
    max_group = 0
    group_zone: str | None = None
    group_track = 0

    for idx, dets in enumerate(frames):
        handling_now = False
        persons_in_shelf = 0
        frame_shelf_zone: str | None = None
        frame_shelf_track = 0

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
                    frame_shelf_track = frame_shelf_track or d.track_id
                if hv_zone is not None:
                    hv_has_person = True
                    hv_zone_id = hv_zone_id or hv_zone.id
                    hv_person_track = hv_person_track or d.track_id

            elif d.cue == "open_bag":
                open_bag_dets += 1
                person_track = _nearest_person_track(d.cx, d.cy, dets)
                for z in shelf_zones:
                    if d.conf >= open_bag_conf:
                        open_bag_zone, open_bag_conf, open_bag_last_idx = z.id, d.conf, idx
                        if person_track:
                            open_bag_track = person_track
                if hv_zone is not None:
                    hv_has_bag = True

            elif d.cue == "bag":
                bag_dets += 1
                person_track = _nearest_person_track(d.cx, d.cy, dets)
                for z in shelf_zones:
                    if d.conf >= bag_fallback_conf:
                        bag_fallback_zone, bag_fallback_conf, bag_last_idx = z.id, d.conf, idx
                        if person_track:
                            bag_fallback_track = person_track
                if hv_zone is not None:
                    hv_has_bag = True

            elif d.cue == "product_in_hand":
                if shelf_zones:
                    handling_now = True
                    product_in_shelf = True
                    handling_zone = handling_zone or shelf_zones[0].id
                    person_track = _nearest_person_track(d.cx, d.cy, dets)
                    if handling_track == 0 and person_track:
                        handling_track = person_track
                    if product_first_idx < 0:
                        product_first_idx = idx
                if hv_zone is not None:
                    hv_has_product = True

            elif d.cue == "concealment":
                conceal_dets += 1
                conceal_last_idx = idx
                person_track = _nearest_person_track(d.cx, d.cy, dets)
                if conceal_track == 0 and person_track:
                    conceal_track = person_track
                if shelf_zones:
                    conceal_zone = conceal_zone or shelf_zones[0].id
                if hv_zone is not None:
                    conceal_in_hv = True

        if handling_now and not prev_handling:
            handling_episodes += 1
        prev_handling = handling_now

        if persons_in_shelf > max_group:
            max_group = persons_in_shelf
            group_zone = frame_shelf_zone
            group_track = frame_shelf_track

    # --- Per-track derived signals ---
    high_value_seen_zone: str | None = None
    high_value_track = 0
    max_dwell_seconds = 0.0
    max_dwell_zone: str | None = None
    max_dwell_track = 0
    max_reentries = 0
    reentry_zone: str | None = None
    reentry_track = 0

    exit_no_checkout_zone: str | None = None
    exit_no_checkout_track = 0
    blind_spot_zone: str | None = None
    blind_spot_track = 0

    for track_id, timeline in per_track.items():
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
                if high_value_track == 0:
                    high_value_track = track_id
                run += 1
                if run > best_run:
                    best_run, best_zone = run, hv
            else:
                run = 0

            in_shelf = bool(types & SHELF_LIKE)
            if in_shelf and not prev_in:
                reentries += 1
                shelf_id = by_type.get(HIGH_VALUE) or by_type.get(SHELF)
                if reentry_zone is None:
                    reentry_zone = shelf_id
                    reentry_track = track_id
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
            max_dwell_track = track_id
        if reentries > max_reentries:
            max_reentries = reentries
            reentry_track = track_id

        shelf_visited = bool(visited & SHELF_LIKE)
        shelf_first = min((first_idx_by_type[t] for t in (SHELF_LIKE & visited)), default=None)

        # Exit after shelf interaction, never passing checkout.
        if shelf_visited and EXIT in visited and CHECKOUT not in visited:
            if shelf_first is not None and first_idx_by_type.get(EXIT, 1 << 30) >= shelf_first:
                if exit_no_checkout_zone is None:
                    exit_no_checkout_zone = exit_zone_id or reentry_zone
                    exit_no_checkout_track = track_id

        # Blind-spot movement (bonus signal when it follows a shelf interaction).
        if BLIND_SPOT in visited and blind_spot_zone is None:
            blind_spot_zone = blindspot_zone_id
            blind_spot_track = track_id

    # --- Emit events (all evidence is observable-signal language, never conclusions) ---
    # Gate bag/concealment cues on sustained detection counts so a handful of
    # one-off detections (jacket adjust, misfire) cannot drive BagOpen/Concealment.
    open_bag_sustained = open_bag_dets >= SUSTAINED_CUE_DETECTIONS
    bag_sustained = bag_dets >= SUSTAINED_CUE_DETECTIONS
    if not open_bag_sustained:
        open_bag_zone = None
    if not bag_sustained:
        bag_fallback_zone = None
    if not (open_bag_sustained or bag_sustained):
        hv_has_bag = False

    if high_value_seen_zone is not None:
        events.append(_ev(
            "HighValueZoneEntry", high_value_seen_zone, 1.0, 0.9, now,
            track_id=high_value_track,
        ))

    if max_dwell_seconds > 0:
        events.append(_ev(
            "Dwell", max_dwell_zone, round(max_dwell_seconds, 1), 0.9, now,
            track_id=max_dwell_track,
        ))

    if handling_episodes > 0:
        events.append(_ev(
            "RepeatedHandling", handling_zone, float(handling_episodes), 0.85, now,
            track_id=handling_track,
        ))
    elif max_reentries > 0:
        events.append(_ev(
            "RepeatedHandling", reentry_zone, float(max_reentries), 0.7, now,
            track_id=reentry_track,
        ))

    # Concealment requires evidence of an ITEM being hidden — a product in hand alone,
    # or an open bag alone, is never concealment. Two valid paths:
    #   A) product handled at a shelf, THEN a bag/open-bag cue appears afterwards
    #      (item picked up -> moved into a bag), or
    #   B) a sustained direct concealment cue ("hiding item inside jacket" style) —
    #      the detection itself encodes item-being-hidden.
    latest_bag_idx = max(open_bag_last_idx, bag_last_idx)
    conceal_sustained = conceal_dets >= SUSTAINED_CUE_DETECTIONS
    handled_then_bag = product_in_shelf and product_first_idx >= 0 and latest_bag_idx > product_first_idx
    if handled_then_bag or conceal_sustained:
        concealment_zone = (conceal_zone if conceal_sustained else None) \
            or open_bag_zone or bag_fallback_zone or handling_zone
        conceal_event_track = conceal_track or handling_track or open_bag_track or bag_fallback_track
        events.append(_ev(
            "Concealment", concealment_zone, 1.0, 0.7, now,
            track_id=conceal_event_track,
        ))

    # Exit without checkout, and its stronger "carried a product out" variant.
    if exit_no_checkout_zone is not None:
        trigger_embedding = track_embeddings.get(exit_no_checkout_track)
        if product_in_shelf:
            events.append(_ev(
                "ShelfPickupNoCheckout", exit_no_checkout_zone, 1.0, 0.7, now,
                track_id=exit_no_checkout_track, embedding=trigger_embedding,
            ))
        else:
            events.append(_ev(
                "ExitWithoutCheckout", exit_no_checkout_zone, 1.0, 0.7, now,
                track_id=exit_no_checkout_track, embedding=trigger_embedding,
            ))

    if blind_spot_zone is not None:
        events.append(_ev(
            "BlindSpotMovement", blind_spot_zone, 1.0, 0.8, now,
            track_id=blind_spot_track,
        ))

    if max_group >= 2:
        events.append(_ev(
            "GroupDistraction", group_zone, float(max_group), 0.7, now,
            track_id=group_track,
        ))

    # A sustained concealment cue in a high-value zone implies an item is involved.
    if conceal_sustained and conceal_in_hv:
        hv_has_product = True

    hv_activity = int(hv_has_person) + int(hv_has_product) + int(hv_has_bag)
    if hv_activity >= 2:
        events.append(_ev(
            "HighValueActivity", hv_zone_id, float(hv_activity), 0.8, now,
            track_id=hv_person_track,
        ))

    # Low-staff removal proxy: a product was removed at a shelf.
    if product_in_shelf:
        low_staff_track = handling_track
        if low_staff_track == 0:
            for track_id, timeline in per_track.items():
                visited = set()
                for (_, types, _) in timeline:
                    visited.update(types)
                if bool(visited & SHELF_LIKE):
                    low_staff_track = track_id
                    break
        events.append(_ev(
            "LowStaffRemoval", handling_zone, 1.0, 0.6, now,
            track_id=low_staff_track,
            embedding=track_embeddings.get(low_staff_track),
        ))

    # Bag-open (prefer explicit open_bag cue; else generic bag near a shelf).
    if open_bag_zone is not None:
        events.append(_ev(
            "BagOpen", open_bag_zone, 1.0, round(open_bag_conf, 3), now,
            track_id=open_bag_track,
        ))
    elif bag_fallback_zone is not None:
        events.append(_ev(
            "BagOpen", bag_fallback_zone, 1.0, round(bag_fallback_conf, 3), now,
            track_id=bag_fallback_track,
        ))

    return events


def _ev(
    event_type: str,
    zone_id: str | None,
    value: float,
    conf: float,
    ts: str,
    track_id: int = 0,
    embedding: list[float] = None,
) -> dict:
    ev = {
        "trackId": int(track_id) if track_id is not None else 0,
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
