# ONEVO — Phase 1A (Camera Loss-Prevention Pipeline)

Plug-and-play retail AI loss-prevention platform. This repository implements the **Phase 1A camera path** end to end:

```
IP Camera (RTSP / test video)
      -> Local Connector (edge)       cuts 10-20s event clips, uploads via signed URL
      -> Object Storage (MinIO/S3)    stores clips + thumbnails
      -> Cloud AI Worker (YOLO)       detection + tracking + zone mapping + event extraction
      -> Backend API (.NET)           persistence + Risk Engine (scoring) + alerts
      -> Dashboard (Angular)          staff review, zone drawing, tuning, health
```

The system produces **evidence-based risk indicators for staff review** — it never confirms theft automatically. Design is documented in the `camera-module/` knowledge base (second brain).

## Components

| Path | Component | Stack |
|------|-----------|-------|
| `backend/` | Backend API + Risk Engine | .NET 10 Web API, EF Core, PostgreSQL |
| `cloud-ai/` | Cloud AI Video Engine worker | Python 3.11, pluggable detector (YOLOE / YOLO26 / RF-DETR), ByteTrack |
| `connector/` | Local Connector (edge) | Python 3.11, OpenCV/FFmpeg, SQLite, FastAPI |
| `dashboard/` | Staff dashboard | Angular |
| `docker-compose.yml` | Local dev orchestration | Postgres, Redis, MinIO, backend, cloud-ai |

## Quick start (local dev)

Prerequisites: Docker + Docker Compose.

```bash
cp .env.example .env       # (Windows: copy .env.example .env)
docker compose up -d --build
```

This starts Postgres, Redis, MinIO (+bucket), the backend API, and the cloud-ai worker.
On first boot the backend creates the schema and seeds an admin user plus a demo
store / camera / high-value zone.

- Backend API: http://localhost:8080 (Swagger at `/swagger`)
- MinIO console: http://localhost:9001 (see `.env` for credentials)
- Default login: `admin@onevo.local` / `Admin123!`

### Run the dashboard
```bash
cd dashboard
npm install
npm start           # http://localhost:4200
```

## End-to-end test (no physical camera)

1) Generate a synthetic test clip (creates motion so the connector cuts clips):
```bash
cd connector
pip install -r requirements.txt
python samples/make_sample.py            # writes connector/samples/test.mp4
```

2) Get the seeded store + camera IDs (needed by the connector). Log in and query:
```bash
# login -> token
curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@onevo.local","password":"Admin123!"}'

# then, with the token:
curl -s http://localhost:8080/api/stores  -H "Authorization: Bearer <TOKEN>"
curl -s http://localhost:8080/api/cameras -H "Authorization: Bearer <TOKEN>"
```
(You can also browse to the dashboard **Setup & Zones** page to see/create them.)

3) Run the connector against the test video:
```bash
cd connector
python -m app.main \
  --source samples/test.mp4 --loop \
  --store-id <STORE_ID> --camera-id <CAMERA_ID>
# connector admin UI: http://localhost:8099
```

The connector registers, cuts event clips on motion, and uploads them via signed URLs.
The cloud-ai worker picks up each clip, runs YOLO + tracking + zone mapping, and posts
AI events; the backend Risk Engine scores them and (for score >= 40) creates an alert.

> Note: the synthetic clip has no real people, so YOLO produces no retail cues and no
> alert fires — it validates the full pipeline plumbing. Use real retail footage as the
> `--source` for meaningful detections and alerts.

> Alert visibility: the demo store defaults to **Silent** pilot mode, so only an Admin
> sees alerts. Change it on the dashboard (Setup) or via `ALERT_VISIBILITY_MODE` before
> exposing alerts to reviewers.

## Phase 1A patterns (all 10)
Camera-only patterns are fully implemented. Two patterns use camera-only **proxies** now,
with the true POS/staff cross-check deferred to Phase 1B.

1. **Shelf pick-up but no POS scan** — *proxy*: product taken from shelf and carried to an exit zone without passing checkout (`ShelfPickupNoCheckout`). POS scan check = Phase 1B.
2. **Concealment movement** — item handled at a shelf, then a `bag`/`open_bag` cue follows (`Concealment`).
3. **Long dwell near high-value shelf** — person inside a `high_value` zone beyond a dwell threshold (`Dwell`).
4. **Repeated shelf handling** — repeated `product_in_hand`/shelf interactions (`RepeatedHandling`).
5. **Exit after shelf interaction without checkout** — visits shelf then exit, never checkout (`ExitWithoutCheckout`).
6. **Blind-spot movement** — track enters a configured `blind_spot` zone (`BlindSpotMovement`).
7. **Group distraction** — ≥ N persons active together in a shelf zone (`GroupDistraction`).
8. **Bag opening near shelf** — `open_bag` (or `bag`) cue within a shelf zone (`BagOpen`).
9. **High-value zone suspicious activity** — multiple activity cues co-occur in a `high_value` zone (`HighValueActivity`).
10. **Product removed during low-staff time** — *proxy*: product removal scored only within a configurable low-staff hour window (`LowStaffRemoval`). Real staff-count = Phase 1B.

Patterns 5/6/7 need the relevant zones (Exit, Checkout, BlindSpot) drawn on the camera; the demo seed creates them.

## Risk scoring (V4 starter weights)
| Signal | Weight |
|--------|--------|
| Enters high-value shelf zone | +15 |
| Dwell exceeds threshold | +10..20 |
| Repeated shelf handling | +15 |
| Bag / open-bag near shelf | +20 |

| Score | Behavior |
|-------|----------|
| 0-39 | no alert (event log only) |
| 40-69 | analytics only |
| 70-89 | medium alert (dashboard) |
| 90+ | high alert (prioritized) |

## Guardrails
- Evidence language only ("dwell 58s in high-value zone"), never "theft".
- Human review is final; the system never acts automatically.
- Connector receives only short-lived signed upload URLs (no broad storage credentials).
- Every alert stores model + rule version for governance.
- Configurable thresholds per store / camera / zone.

## Detection model (pluggable backends)

The Cloud AI worker's detector is model-agnostic. Choose the backend with
`CLOUD_AI_MODEL_BACKEND` (and weights with `CLOUD_AI_MODEL`):

| Backend | `CLOUD_AI_MODEL_BACKEND` | Example weights | Notes |
|---------|--------------------------|-----------------|-------|
| YOLOE (default) | `yoloe` | `yoloe-11s-seg.pt` | Open-vocabulary: detects `open_bag` / `product_in_hand` by prompt, no training |
| YOLO26 | `yolo26` | `yolo26s.pt` (or `yolov8n.pt`) | Cheapest closed-set option; person + bag only |
| RF-DETR | `rfdetr` | `rfdetr-base` | Highest accuracy / best on occlusion; needs a GPU + `requirements-rfdetr.txt` |

All backends emit the same canonical cues (`person`, `bag`, `open_bag`, `product_in_hand`),
so the Risk Engine and dashboard are unchanged; only the alert's `modelVersion` string differs.
YOLOE prompt->cue mappings can be customized via `CLOUD_AI_YOLOE_PROMPTS`.

> Licensing: Ultralytics YOLO/YOLOE are **AGPL-3.0** (a commercial license is required for a
> closed-source product). RF-DETR (base) is **Apache-2.0**. Factor this into production choice.

## Evaluation
`cloud-ai/eval/` contains a harness that runs the same detection -> tracking -> event
extraction -> risk scoring path over labeled clips and writes `results.json`
(precision / recall / F1 / FPR), mirroring the knowledge-base eval template.

```bash
cd cloud-ai
pip install -r requirements.txt
# place labeled clips in cloud-ai/eval/clips/ and list them in eval/ground_truth.json
python -m eval.run_eval                          # default backend: yoloe
python -m eval.run_eval --backend yolo26 --model yolo26s.pt
```

## Not in this build
Phase 1B POS fraud, VLM verification, model fine-tuning, cloud deployment, multi-store scale.
