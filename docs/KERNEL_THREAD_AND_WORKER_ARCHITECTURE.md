# ONETIX Local Connector — Threading, Worker Pools, Queues, and CPU Management

**Audience:** Connector, backend, installer, QA, and operations teams  
**Scope:** Current implementation in `connector/app`  
**Document status:** Implementation handoff / architecture reference  
**Last reviewed:** 2026-08-10

## 1. Executive summary

The connector now uses CPU-aware, bounded worker pools for the two expensive processing stages:

1. motion/person candidate analysis;
2. clip encoding and FFmpeg transcoding.

It also has a small shared event executor for reference-frame uploads. Capture, upload, heartbeat, admin-server, orchestrator, and tray responsibilities run independently so slow network or FFmpeg work does not block the live capture loop.

On the current 12-logical-CPU test machine the runtime reports:

| Runtime resource | Current value |
|---|---:|
| Logical CPUs | 12 |
| Analysis workers | 4 |
| FFmpeg workers | 2 |
| Event workers | 2 |
| Maximum accepted analysis jobs (active + waiting) | 8 |
| Maximum accepted clip jobs (active + waiting) | 4 |

The most important result is **bounded concurrency with backpressure**. When an expensive pool is saturated, new work is dropped and counted instead of creating unlimited threads or an unlimited stale-frame/clip backlog.

## 2. Terminology: what “kernel thread” means here

This project does **not** contain a Windows kernel driver, kernel-mode code, or a custom kernel-thread API.

The implementation uses:

- Python `threading.Thread`;
- Python `concurrent.futures.ThreadPoolExecutor`;
- `threading.Event`, `Lock`, `RLock`, and `BoundedSemaphore`;
- external FFmpeg child processes.

On Windows, Python worker threads are native operating-system threads scheduled by the Windows kernel. Therefore it is reasonable to describe this as an **OS-thread worker architecture**, but not as kernel-mode programming.

The Python GIL still applies to Python bytecode. This design remains useful because:

- OpenCV/NumPy operations are primarily native code and can release the GIL;
- video capture and network operations are I/O-heavy;
- FFmpeg runs in a separate process;
- the pools isolate latency and enforce queue limits even when perfect CPU parallelism is not possible.

## 3. Architecture overview

```text
Windows service process
│
├─ Local admin server thread (Uvicorn / localhost:8099)
├─ Uploader daemon thread
├─ Heartbeat daemon thread
├─ Main capture path
│  ├─ single-camera mode: capture loop on main thread
│  └─ multi-camera mode: orchestrator + one capture thread per camera
│
└─ RuntimeState shared worker infrastructure
   ├─ Event pool:    2 workers (short reference-frame I/O)
   ├─ Analysis pool: CPU-calculated, maximum 4 workers
   │  └─ BoundedSemaphore: maximum 2 × workers accepted jobs
   └─ FFmpeg pool:  1 or 2 workers
      └─ BoundedSemaphore: maximum 2 × workers accepted jobs

Clip completed
└─ SQLite durable upload queue
   └─ Uploader thread → backend signed URL → MinIO/object storage
```

The tray is a separate process. Its UI/status/update threads are not part of the connector service worker pools.

## 4. CPU-aware worker calculation

`RuntimeState` calculates worker counts once during process startup using `os.cpu_count()`:

```python
logical_cpus = max(1, os.cpu_count() or 1)
analysis_workers = min(4, max(1, logical_cpus - 2))
ffmpeg_workers = 1 if logical_cpus < 8 else 2
```

Expected values:

| Logical CPUs | Analysis workers | FFmpeg workers | Reasoning |
|---:|---:|---:|---|
| 1 | 1 | 1 | Minimum viable execution |
| 2 | 1 | 1 | Avoid consuming every CPU with analysis |
| 4 | 2 | 1 | Leaves capacity for capture, UI, networking, and OS |
| 6 | 4 | 1 | Analysis reaches its safety cap |
| 8 | 4 | 2 | Allows two clip transcodes concurrently |
| 12+ | 4 | 2 | Hard caps prevent high-core systems from multiplying load |

This is intentionally conservative. Video capture, decoding, Python, OpenCV, FFmpeg, the uploader, and Windows itself share the same CPU and memory resources.

## 5. OpenCV nested-thread prevention

OpenCV may create its own internal worker threads. If four Python analysis workers each created several OpenCV threads, CPU oversubscription could become much larger than the configured pool.

The connector therefore configures OpenCV as follows:

```python
cv2.setNumThreads(max(1, int(os.getenv("CONNECTOR_OPENCV_THREADS", "1"))))
```

Default behavior is one internal OpenCV thread per analysis operation. Connector-level pools own the parallelism. `CONNECTOR_OPENCV_THREADS` is an advanced override and should normally remain `1`.

## 6. Motion-analysis worker pool

### 6.1 Purpose

The capture loop reads and buffers frames. Candidate analysis performs:

- MOG2 foreground/background subtraction;
- zone-mask motion fraction calculation;
- optional HOG person detection;
- person-in-polygon validation.

This work is submitted through `RuntimeState.run_analysis()` instead of creating a new thread for every frame.

### 6.2 Capacity and backpressure

The analysis executor has `analysis_workers` threads. A `BoundedSemaphore` has capacity:

```text
analysis capacity = analysis_workers × 2
```

This capacity includes running and waiting jobs. For a 12-CPU machine:

```text
4 active workers + up to approximately 4 waiting jobs = 8 accepted jobs
```

If no slot is immediately available:

- the new analysis request is not queued;
- `analysisDropped` increments;
- `run_analysis()` returns `None`;
- the capture pipeline treats that frame as no motion/no person and continues.

This prioritizes current frames over stale frames. A motion system should not spend seconds analysing frames that are no longer current.

### 6.3 Timeout behavior

The capture caller waits up to three seconds by default for an analysis result. On timeout:

- the caller continues;
- `analysisDropped` increments;
- the already-running worker is not forcefully terminated;
- its semaphore slot is released only when the worker actually finishes.

This is safe for thread state, but the metric name represents skipped/timed-out analysis from the caller’s perspective, not necessarily a cancelled computation.

### 6.4 Metrics

The `/status` endpoint exposes:

- `logicalCpus`;
- `analysisWorkers`;
- `analysisActive`;
- `analysisQueueDepth`;
- `analysisDropped`.

`analysisQueueDepth` counts accepted jobs that have not started. `analysisActive` counts currently executing callbacks.

## 7. Clip and FFmpeg worker pool

### 7.1 Why clip writing is asynchronous

Clip creation includes expensive work:

1. write buffered frames using OpenCV `VideoWriter` to a temporary MP4;
2. launch FFmpeg;
3. transcode to H.264/yuv420p;
4. add `faststart` metadata for browser playback;
5. return the final path;
6. enqueue the completed clip for upload.

Doing this inside the capture loop would stop frame reading and cause RTSP buffer growth, missed motion, and disconnects. `submit_clip_job()` moves the complete write/transcode operation into the dedicated FFmpeg pool.

### 7.2 Capacity

The FFmpeg executor uses:

```text
CPU < 8  → 1 FFmpeg worker
CPU >= 8 → 2 FFmpeg workers
```

The accepted-job capacity is:

```text
clip capacity = ffmpeg_workers × 2
```

For the current 12-CPU machine this means two active jobs and approximately two waiting jobs. The fifth simultaneous request is rejected.

When rejected:

- `clipJobsDropped` increments;
- the capture loop logs `clip queue full; event dropped by backpressure`;
- no extra thread or FFmpeg process is created.

### 7.3 Completion path

The executor completion callback:

- reads the worker result;
- logs encoding failures;
- increments `clipsCreated` only after a clip exists;
- calls the camera-specific `on_clip()` callback;
- writes an entry into the durable SQLite upload queue;
- releases the bounded semaphore slot.

If H.264 transcoding fails or times out after 60 seconds, the connector logs a warning and moves the raw MP4 into the final path so the event is not silently lost.

### 7.4 Memory consideration

Each accepted clip job retains its list of NumPy frames until encoding finishes. Bounding the FFmpeg queue therefore protects both CPU and RAM. It is not only a thread-count control.

## 8. Event executor and reference-frame publishing

Reference-frame uploads use a shared two-worker executor (`onevo-event`). The capture pipeline does not block while uploading the image.

Each camera pipeline also has an in-flight guard:

```text
reference_frame_pending
reference_frame_inflight
```

Only one reference-frame publish can be in flight per camera pipeline. A failed upload sets the pending flag so a later preview can retry.

Important caveat: Python’s `ThreadPoolExecutor` internal queue is unbounded and the event executor does not currently have a semaphore. The per-camera in-flight guard bounds the existing reference-frame use case, but `submit_event()` itself is not a generally bounded public queue. New event use cases must either add a global event semaphore or implement their own in-flight guard.

## 9. Capture and multi-camera threading

### 9.1 Single-camera mode

When `cfg.camera_id` is present, the capture pipeline runs on the main service thread. Expensive analysis and clip encoding are delegated to their pools.

### 9.2 Multi-camera mode

When no single camera is fixed in configuration, `StoreOrchestrator` polls backend camera configuration. It creates:

- one `CapturePipeline` object per active camera;
- one daemon `threading.Thread` per active camera.

The orchestrator detects and handles:

- newly added cameras;
- removed cameras;
- changed source fingerprints;
- capture threads that died;
- backend outages after three consecutive fetch failures.

On backend outage it stops pipelines, joins each camera thread for up to two seconds, and preserves the latest frames for local zone viewing.

Important caveat: capture threads are still **one thread per configured camera**. The expensive analysis and FFmpeg stages are globally bounded, but the number of capture threads is not capped by a camera-worker pool. A practical maximum camera count and admission policy should be defined before large-site rollout.

## 10. Upload and heartbeat threads

Two long-lived daemon threads start after connector activation:

### Uploader thread

- reads the next SQLite `pending`/`uploading` job;
- requests an upload URL;
- uploads the file;
- completes backend clip metadata;
- marks success/failure in SQLite;
- retries with exponential backoff capped at 60 seconds;
- deletes the local file only after successful upload.

### Heartbeat thread

- calculates disk-free percentage;
- reports queue depth, connector version, local admin address, and degraded state;
- runs every ten seconds;
- reports disk warning/critical and queue backlog conditions.

Both threads call `RuntimeState.wait_until_running()`. Pausing monitoring or losing backend availability gates cloud/capture work without shutting down localhost:8099.

## 11. Durable SQLite queue and thread safety

The upload queue is separate from the bounded in-memory FFmpeg queue.

- The FFmpeg queue controls concurrent clip creation.
- SQLite preserves completed clip upload jobs across crashes, service restarts, and reboots.

`LocalStore` uses:

- SQLite `check_same_thread=False`;
- a process-local `threading.RLock` around credential and enqueue/mark operations;
- WAL journal mode;
- a 5000 ms SQLite busy timeout.

This allows camera completion callbacks and the uploader thread to share one connection safely within the process. A concurrency test verifies 20 parallel camera enqueues are serialized and retained.

Current caveat: some read/maintenance methods do not acquire `_lock`. SQLite WAL and the current single-process access pattern reduce risk, but consistent locking or per-thread connections would be stronger for future higher concurrency.

## 12. Pause, backend outage, and control events

`RuntimeState` uses two events:

- `_monitoring_active` — operator pause/resume state;
- `_backend_active` — backend availability gate.

Workers proceed only when monitoring is active and the backend is available. Pausing:

- stops new capture/motion/cloud work;
- preserves the last camera frame;
- keeps the local admin server available;
- preserves the pause decision in SQLite so it survives restart/reboot.

This separation is intentional: stopping monitoring must not make the local recovery UI inaccessible.

## 13. Locks and shared-state protection

### Runtime lock

`RuntimeState._lock` protects:

- counters and queue metrics;
- logs;
- camera states;
- live/reference frame dictionaries;
- zone revisions;
- pause/backend flags.

Snapshots copy state while holding this lock, giving the local dashboard a coherent status response.

### Trigger lock

Each capture pipeline has `_trigger_lock`. A UI manual-trigger request and capture-loop consumption cannot race or cut the same request twice.

### Process instance locks

The Windows service connector and tray use separate filesystem instance locks. This prevents two service connector instances while still allowing one tray process to coexist with the service.

## 14. Shutdown semantics

`RuntimeState.shutdown_workers()` is registered with `atexit`.

| Pool | Shutdown policy | Effect |
|---|---|---|
| Event | `wait=False`, `cancel_futures=True` | Cancel pending short I/O work; do not delay process exit |
| Analysis | `wait=False`, `cancel_futures=True` | Cancel waiting analysis; do not wait for stale CPU work |
| FFmpeg | `wait=True`, `cancel_futures=False` | Allow accepted clip writes/transcodes to finish |

The FFmpeg policy favors event durability over fast shutdown. Operations must account for a possible shutdown delay, including the FFmpeg timeout.

Camera pipelines receive `stop()`. Orchestrator joins camera threads with a two-second timeout. Uploader and heartbeat observe the shared stop event.

## 15. Runtime observability

Startup writes a worker configuration line such as:

```text
Worker pools configured cpu=12 analysis=4 ffmpeg=2 event=2
```

The `/status` response contains the live worker metrics. Recommended operational alerts:

| Signal | Interpretation |
|---|---|
| `analysisDropped` increasing continuously | Analysis cannot keep up with incoming camera/frame rate |
| `analysisQueueDepth` stays near capacity | CPU analysis saturation |
| `clipJobsDropped` > 0 | Clip encoding pool/backpressure saturated; events were skipped |
| `clipQueueDepth` stays high | FFmpeg slower than incoming events |
| `ffmpegActive == ffmpegWorkers` for long periods | Encoding capacity fully used |
| SQLite `queueDepth` increasing | Cloud upload/backend/object storage is slower or unavailable |
| `diskFreePct` below threshold | Local clips/temporary files threaten service reliability |

## 16. Tests currently covering the design

`connector/tests/test_runtime_safety.py` verifies:

- CPU-aware worker calculation and caps;
- analysis execution through the shared pool;
- FFmpeg/clip queue backpressure and dropped-job counting;
- atomic log clearing;
- stable reference frame separation from live frames;
- managed pause/resume behavior;
- pause persistence across store reopen;
- 20 concurrent camera enqueues into SQLite;
- service/tray instance-lock separation.

Current full connector test result at the time of this handoff: **50 passed**.

## 17. What was fixed compared with the earlier architecture

### Before

- expensive tasks could be started from independent ad-hoc execution paths;
- no unified CPU-aware calculation;
- no explicit analysis or FFmpeg admission limit;
- queued stale analysis/clip work could increase CPU and memory pressure;
- nested OpenCV threading could oversubscribe CPU;
- worker saturation was not visible in status metrics.

### Now

- motion/person analysis uses one shared bounded CPU-aware pool;
- clip writing and FFmpeg use one shared bounded pool;
- saturation rejects newest work instead of increasing backlog;
- OpenCV defaults to one internal thread;
- completion callbacks preserve the durable upload path;
- active/queued/dropped counts are visible through `/status`;
- shutdown behavior is explicitly different for disposable analysis work and durable clip work.

## 18. Known limitations and recommended next work

These items are not hidden defects; they are the remaining engineering boundaries the team should understand.

1. **Per-camera capture threads remain uncapped.** Add a supported-camera limit or a capture-worker admission layer before high-density rollout.
2. **Event executor is not globally semaphore-bounded.** Existing reference publish is protected per camera, but future callers need a global bound.
3. **Analysis timeout does not cancel native work.** Consider cooperative cancellation or a process pool only if profiling proves long-running analysis callbacks.
4. **The Python GIL still exists.** Current OpenCV/NumPy workload benefits from native execution, but CPU profiling must validate real scaling.
5. **FFmpeg jobs hold frame arrays in memory.** Consider streaming directly to an encoder/ring file for long pre/post windows or many cameras.
6. **Worker formulas are code constants.** Add validated configuration overrides and safe min/max bounds if different hardware tiers require tuning.
7. **No dynamic resizing.** Worker counts are calculated once at startup and do not respond to thermal throttling, memory pressure, or changing camera load.
8. **Tray callbacks still use short ad-hoc daemon threads.** They are low-frequency UI operations, but can be migrated to a small tray executor for architectural consistency.
9. **Some SQLite reads are not consistently locked.** Standardize locking or use one connection per worker if write/read concurrency grows.
10. **Metrics are process-local.** Export them to the backend/monitoring system for historical capacity planning and alerts.

## 19. Recommended performance-validation matrix

Before production sign-off, run at least:

| Test | Suggested matrix | Pass criteria |
|---|---|---|
| Camera scaling | 1, 2, 4, 8 cameras | Stable capture; documented maximum camera count |
| Resolution | 720p, 1080p, 4K | No continuous queue saturation |
| Frame rate | 5, 10, 15, 25 FPS | Acceptable dropped-analysis rate |
| Motion burst | simultaneous motion on all cameras | Controlled `clipJobsDropped`; no OOM |
| Backend outage | 5, 30, 120 minutes | Durable queue, local UI available, recovery succeeds |
| Disk pressure | warning and critical thresholds | Correct degraded state and safe behavior |
| RTSP instability | disconnect/reconnect loops | No leaked capture threads or handles |
| Shutdown under FFmpeg load | full clip queue | Predictable service-stop duration, valid clips |
| 24-hour soak | realistic cameras and motion | Stable handles, memory, CPU, and queue depth |

## 20. Source-of-truth files

| Responsibility | File |
|---|---|
| Worker calculation, pools, semaphores, metrics, shutdown | `connector/app/runtime.py` |
| OpenCV thread cap, motion analysis, clip submission, FFmpeg | `connector/app/capture.py` |
| Multi-camera lifecycle and per-camera capture threads | `connector/app/orchestrator.py` |
| Service startup, uploader/heartbeat creation, single-camera mode | `connector/app/main.py` |
| Upload and heartbeat loops | `connector/app/workers.py` |
| Durable SQLite queue and locking | `connector/app/store.py` |
| Local `/status` metrics | `connector/app/admin.py` |
| Tray UI/update/status threads | `connector/app/tray.py` |
| Concurrency and safety tests | `connector/tests/test_runtime_safety.py` |

## 21. Team handoff statement

The current connector has moved from ad-hoc expensive task execution to a **CPU-aware, bounded analysis and encoding architecture**. The design prevents unlimited motion-analysis and FFmpeg work, applies backpressure, limits nested OpenCV parallelism, preserves completed clips through SQLite, and exposes capacity metrics.

It should not be represented as a fully pooled solution for every thread in the product: multi-camera capture remains one thread per camera, the event executor relies on a per-camera in-flight guard, and tray UI work still uses short ad-hoc threads. Those boundaries are documented above so the next optimization phase can be planned from the real implementation rather than an overstated claim.
