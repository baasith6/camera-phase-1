# ONETIX Connector Current Audit and Execution Plan

Status: implementation in progress against the second five-image UI reference set  
Primary priority: exact native wizard parity for Connect ONETIX, source upload, zones, and success  
Reference release inspected: `1.1.20`

## 0. Confirmed decisions and scope

1. **The setup wizard UI is the first and most important deliverable.** Rewrite `connector/installer/onevo-connector.iss`, build it locally, and compare every page with the supplied sample images before doing lower-priority runtime polish.
2. **Runtime/kernel choice is fixed for this iteration:** Windows x64, Python 3.11, PyInstaller 6, OpenCV CPU/headless, FastAPI, and Inno Setup 6. The connector must not bundle Torch, CUDA, the cloud detection model, or GPU kernels. Cloud AI remains in `cloud-ai`.
3. **Installer optimization is required**, but only after the rewritten wizard produces a working clean build. Optimize the clean Python dependency graph, FFmpeg, WinSW/service packaging, and Inno/PyInstaller settings with before/after measurements.
4. **Vercel installer hosting and deployment are out of scope and must be removed from the active local flow.** The backend serves the installer only from `connector/dist`.
5. **Fresh-clone startup must be one command on a Windows development host.** A repository bootstrap script must install/check prerequisites, build a missing or stale installer, and then run Docker Compose.
6. A Linux Docker container cannot natively produce the required Windows PyInstaller/Inno Setup executable. Therefore the Windows installer build runs on the Windows host before the Linux Docker stack starts. We will not add Wine or a mixed Windows-container service to the normal development stack.
7. The second reference set is authoritative for this iteration: left illustration panel, `Connect ONETIX`, three horizontal source tabs, MP4 drop zone, split zone editor, and illustrated success summary.

## 1. Product contract

One store owns one active connector. One connector may own multiple RTSP, ONVIF, and MP4 sources. Each source is provisioned as its own camera and must keep its own frame, zones, live stream, health state, and motion pipeline.

The required first-install journey is:

1. Enter the setup code generated for the selected store in the cloud dashboard.
2. Optionally add, edit, validate, or remove one or more RTSP/ONVIF/MP4 sources.
3. Optionally capture one stable frame per selected source and add, edit, or delete zones on that frame.
4. Install the service, verify activation and service health, then show a truthful success summary.

The zone frame may change only when the user first selects/loads that camera or explicitly presses **Refresh Frame**. Drawing, saving, editing, polling, or background capture must not replace it.

## 2. Surfaces and ownership

| Surface | Current owner | Required role |
| --- | --- | --- |
| Native setup wizard | `connector/installer/onevo-connector.iss` | Main UI target; match the supplied screenshots |
| Installer helper/runtime package | `connector/installer/onevo-connector.spec`, `connector/onevo_launcher.py`, `connector/app/*` | Validate sources, capture frames, persist config, run local API/tray/service |
| Local browser setup fallback | `connector/app/wizard.py`, `connector/app/wizard_html.py` | Recovery/fallback flow with the same source/zone semantics |
| Local operational UI | `connector/app/admin.py` | Multi-camera grid/single view, sources, zones, start/stop push, logs |
| Native tray | `connector/app/tray.py`, `tray_dashboard.py`, `tray_zone_editor.py` | Local status and control entry point |
| Cloud dashboard | `dashboard/src/app/pages/setup/*`, `get-started/*`, `admin-stores/*` | Store selection, setup-code generation, installer download, remote reference frames/zones |
| Backend | `backend/Controllers/ConnectorsController.cs`, `CamerasController.cs`, `ZonesController.cs` | Store/connector ownership, provisioning, frame and zone persistence |
| MinIO/S3 | `backend/Services/S3Service.cs` | Durable camera-specific JPEGs and clips |
| Local installer artifact | `connector/dist/*` | Backend-served versioned installer, checksum, and size |

Changing `wizard_html.py` does not change the native installer. The screenshot-matching work belongs first in `onevo-connector.iss`.

## 3. Verified current state

### Already present

- Dashboard-generated one-time setup codes and connector claim endpoints exist.
- Backend pairing enforces the one-active-connector-per-store rule.
- Multiple source provisioning uses stable `sourceKey` values and camera IDs.
- Connector-authenticated camera-scoped zone CRUD exists.
- Camera-specific reference-frame columns and MinIO upload/download endpoints exist.
- Capture pipelines accept camera-specific zone providers and revisions.
- Motion detection fails closed when a camera has no usable zones.
- The local dashboard already renders multiple active cameras as a grid and supports a focused single-camera view.
- Persistent pause state, backend availability state, and local control surfaces exist.
- A `1.1.20` installer artifact was inspected at `131,604,741` bytes. The revised local flow will calculate metadata from `connector/dist`; it will not depend on the Vercel Blob URL or `installer-site/latest.json`.

### Gaps found in the native wizard

1. **Layout mismatch:** the wizard is forced to `480 x 630`; the supplied references are wide desktop layouts around `920–1070 x 680–710`. Controls are manually positioned and cannot align cleanly at the current width.
2. **Source navigation state is wrong:** selecting a source type can change the forward action to `Next` even when the user has not added/saved a source. Required behavior is `Skip` until at least one source is staged, then `Next`.
3. **Source validation is incomplete:** RTSP checks mostly validate the prefix; ONVIF “Connected” and RTSP “Valid” display text can be produced before a real bounded connection test. MP4 metadata/codec/duration and drag/drop are not fully represented by the native controls.
4. **Zone list is not camera-scoped in the UI:** `RebuildZoneList` displays saved zones for all sources together. The selected camera must show only its own zones.
5. **Zone editor parity is incomplete:** the native editor supports rectangle drawing and saved arrays, but not the screenshot-level polygon/vertex editing experience or camera-scoped zone cards.
6. **Backend failure is detected too late:** the native installer accepts any non-empty setup code, writes pending config, installs, then relies on the service to claim it. A backend outage or invalid code can therefore reach an inaccurate completion screen.
7. **Success can be optimistic:** the completion copy/counts are based on staged installer state and do not constitute proof that claim, provisioning, zone sync, service start, and `/health` all succeeded.
8. **Accessibility/responsiveness:** fixed pixel positioning lacks a shared spacing system, DPI-safe layout rules, keyboard/focus validation, and reusable card/list primitives.

### Runtime/data risks to close

- Every frame cache key, reference-frame object key, zone query, overlay, and motion mask must be keyed by `cameraId`; never fall back to the last frame from another camera.
- A reference frame should be uploaded on the initial accepted frame and explicit refresh, not because a background pipeline happened to produce a newer frame.
- Local memory gives offline-with-service-running behavior, while MinIO gives durable behavior after service/PC shutdown. Both paths need an explicit same-camera fallback order.
- Pausing/backend outage must stop capture, motion generation, uploader work, and heartbeat while keeping the localhost UI reachable.
- Backend recovery must verify credentials before restarting pipelines; UI state must come from the runtime API rather than an optimistic local button toggle.

## 4. Installer size audit and runtime choice

The last verified installer build before this UI iteration is **129.45 MiB** (`135,741,239` bytes). Inspected bundled tools are:

| Component | Uncompressed size | Finding |
| --- | ---: | --- |
| `ffmpeg.exe` | about 97.2 MiB | Largest clear contributor |
| `WinSW-x64.exe` | about 17.4 MiB | Second large external binary |
| Python/OpenCV/Numpy/runtime | compressed into the PyInstaller payload | Necessary subset must be measured from a clean build |

### Selected kernel/runtime

- OS/architecture: Windows 10/11 x64.
- Python runtime: CPython 3.11 x64.
- Packaging kernel: PyInstaller 6 one-file baseline, wrapped by Inno Setup 6.
- Video kernel: OpenCV CPU with a minimal external FFmpeg x64 build.
- Local motion: OpenCV background subtraction/mask pipeline.
- AI inference: not included in the installer; it stays in the Dockerized `cloud-ai` service.
- GPU/Torch/CUDA: explicitly excluded from the connector build.

Kernel decision remains CPython/OpenCV CPU. The UI rewrite does not justify a runtime rewrite. Size work must target the measured FFmpeg, WinSW, OpenCV, and PyInstaller payloads; visual assets add only compressed kilobytes and are not the dominant size source.

This is the smallest-risk choice because the current service, tray, source capture, ONVIF, and local API are already Python-based. Rewriting the runtime in Rust/.NET/Nuitka before the UI and correctness work would expand scope without proving a size benefit.

The safe optimization order is:

1. Build in a clean Python 3.11/3.12 virtual environment containing only locked runtime/build requirements.
2. Produce and archive a PyInstaller dependency report and component-size baseline.
3. Replace the generic FFmpeg binary with a license-compatible minimal x64 build containing only required protocols/demuxers/decoders/encoders after RTSP, ONVIF-derived RTSP, and MP4 tests pass.
4. Evaluate a smaller supported service wrapper or Windows service implementation only after upgrade/uninstall recovery tests; do not trade reliability for a few MB blindly.
5. Add explicit PyInstaller exclusions only when import analysis and smoke tests prove the modules unused.
6. Compare `onefile` versus `onedir` plus Inno compression for installer size, startup speed, antivirus behavior, and update reliability.
7. Sign the final binaries and calculate size/SHA-256 from `connector/dist` automatically.

Target: first establish a reproducible baseline, then aim for **under 80 MiB** only if codec/protocol coverage and Windows 10/11 reliability remain intact. This target is a release gate to validate, not a promise before the minimal FFmpeg experiment.

## 5. Fresh-clone local build and Docker startup

### Required developer command

Add a root script such as:

```powershell
.\scripts\dev-up.ps1 -BackendUrl http://localhost:8081
```

The script must:

1. Resolve repository root and read the expected connector version from one canonical version file.
2. Check whether `connector/dist/ONETIX-Connector-Setup-<version>.exe` exists and whether its build fingerprint is current.
3. If the installer is missing/stale:
   - verify Windows x64;
   - locate Python 3.11 and Inno Setup 6;
   - create/reuse `connector/.venv-build`;
   - install locked runtime/build packages like `npm install` does for Node projects;
   - run `scripts/ensure-installer-tools.ps1` with checksummed downloads;
   - run the connector PyInstaller build and compile the rewritten `.iss`;
   - verify filename, version, size, SHA-256, and executable signature/launch metadata.
4. If build fails, stop immediately with the exact missing prerequisite or compiler error. Do not start a backend that advertises a nonexistent installer.
5. Run `docker compose up -d --build` only after the artifact passes verification.
6. Poll backend health and `GET /api/connectors/installer`; confirm the backend reports the local artifact.

### Build fingerprint

Store a local generated fingerprint beside the EXE. It must include hashes of:

- connector Python source used by the package;
- `requirements.txt` and `requirements-build.txt`/lock file;
- PyInstaller spec;
- rewritten `.iss` and installer assets;
- FFmpeg and WinSW binaries;
- baked backend URL;
- connector version.

Rebuild only when the EXE is absent or this fingerprint changes. Provide `-ForceInstallerBuild` for manual rebuilds and `-SkipInstallerBuild` only for users who intentionally do not need the installer.

### Docker/backend changes

- Keep `./connector/dist:/app/connector-dist:ro` on the backend.
- Remove `ConnectorInstaller__DownloadUrl`, `CONNECTOR_INSTALLER_URL`, and Vercel fallback behavior from the active local configuration.
- Remove `installer-site` manifest mounting from the normal compose file.
- `ConnectorInstallerService` must inspect the local versioned EXE and calculate size/SHA-256. If absent, return a clear `installer_not_built` response with the bootstrap command—not a remote redirect.
- Align the default compose version with the canonical version; it currently defaults to `1.1.19` while the inspected installer is `1.1.20`.
- The dashboard download button must be disabled with a useful local-build message when the artifact is absent.

Important limitation: plain `docker compose up` cannot invoke a PowerShell build on the host. The supported fresh-clone command is `dev-up.ps1`, which then invokes Docker Compose. This gives the requested automatic package/install/build behavior without an unreliable Windows cross-build inside Linux containers.

## 6. Execution phases

### Phase 0 — Freeze contracts, runtime, and local build contract

- Preserve current dirty/untracked user changes; make scoped commits only after review.
- Define one version source and generate installer, backend, tray, Docker, and local artifact versions from it.
- Implement the Windows host `dev-up.ps1` contract and remove Vercel fallback from the planned flow.
- Lock source payload, zone polygon (`[[x,y], ...]`, normalized `0..1`), reference-frame, status, and success-summary contracts.
- Add a camera ownership assertion to every connector frame/zone endpoint and test cross-store/cross-connector denial.

Exit gate: contract tests pass and `1.1.20` upgrade data remains readable.

### Phase 1 — Rewrite the native wizard shell and Stage 1 UI

- Replace the existing fixed `480 x 630` manual layout with a wide DPI-aware page shell matching the supplied screenshots.
- Create reusable header, title/subtitle, content, footer, card, error, and primary/secondary button helpers in the `.iss` code.
- Add proper transparent ONETIX assets (logo, key, shield, camera, video, zone, success); do not use screenshots as backgrounds.
- Rebuild Setup Code spacing, typography, paste affordance, example, security hint, focus order, and inline error state.
- Keep the footer buttons aligned consistently across every stage.
- Compile the `.iss` immediately and perform visual comparison at 100%, 125%, and 150% DPI before continuing.

Exit gate: the first installer page visually matches the reference and the shared shell is approved for reuse.

### Phase 2 — Make setup-code/backend validation authoritative

- Add an installer-helper preflight that checks backend reachability and validates/claims the setup code before installation can start.
- Persist returned connector/store credentials atomically in the pending state; make retries idempotent and avoid consuming a code without recoverable local state.
- Disable `Next` during validation, show an inline spinner/error, apply bounded timeouts, and allow retry/back.
- If backend is unavailable, invalid, expired, already used, or belongs to a store with another active connector, remain on Stage 1. Do not install or show success.
- Keep upgrades separate: a valid existing paired installation must not require a new setup code.

Exit gate: offline/invalid/expired/duplicate cases cannot pass Stage 1; valid claim survives installer restart.

### Phase 3 — Rebuild source setup UI

- Render three equal selectable RTSP/ONVIF/MP4 cards.
- RTSP: support multiple URLs, normalization, duplicates, credential-safe display, and bounded real frame preflight.
- ONVIF: validate host/port/credentials, discover profile/RTSP URI, perform connection test, and never expose the password in summaries/logs.
- MP4: support picker plus real Windows drag/drop, copy to a durable staging directory, validate extension/container/codec/readability/size/duration, and show metadata.
- Implement per-row Add/Edit/Delete without losing other staged sources.
- Keep `Skip` while zero sources exist; change to `Next` only after at least one source is successfully staged.
- Back navigation must retain validated staged data.

Exit gate: all three types and mixed multi-source setups survive Back/Next and installer restart/retry.

### Phase 4 — Rebuild zone setup UI and frame lifecycle

- Show a camera selector and only that camera's frame/zones.
- Capture once on first load. Thereafter only **Refresh Frame** may replace the frozen image.
- Maintain `cameraId -> framePath/hash/capturedAt` and `cameraId -> zones[]` maps; remove index-only ownership assumptions.
- Support Add/Edit/Delete/View, polygon/rectangle drawing, vertex drag, whole-polygon move, undo, clear, colors, and selected state.
- Filter the zone list by selected camera. Switching cameras restores each camera's own frozen frame and draft/saved zones.
- Save the exact displayed JPEG and camera ID through the backend/MinIO flow. Record object key and timestamp on that camera.
- Same-camera display fallback order: frozen installer frame → local cached JPEG → backend reference-frame endpoint → clear “no saved frame” state. Never use another camera.
- Keep `Skip` with no zones; change the primary action to `Install` when at least one zone is saved. `Back` preserves source and zone state.

Exit gate: two-camera isolation test proves frames, polygons, refreshes, edits, and deletes never cross cameras; saved frame remains visible with connector stopped.

### Phase 5 — Transactional install and truthful success page

- Write pending config atomically, copy staged MP4/frame assets, then install/register/start the service.
- Wait for localhost `/health`, pairing identity, expected camera count, zone sync result, and service state with bounded retries.
- On failure, keep the wizard open with a precise failed step and retry/log action; do not show green success.
- On success, render the reference design with real Setup Code status, Sources Added count, Detection Zones count, Connector Service status, and Finish.
- Make rollback/retry safe for partial service registration and locked files. Preserve existing identity/camera/zone data during upgrades.

Exit gate: clean install, partial failure retry, upgrade, repair, and uninstall all pass on Windows 10/11 x64.

### Phase 6 — Align local UI, tray, and multi-camera behavior

- Reuse the same validation and camera/zone/frame API semantics in `wizard.py`/`wizard_html.py`.
- Ensure local dashboard grid and single view display all cameras/videos and camera-specific overlays.
- Make Start push/Stop push state server-backed and consistent in browser/tray.
- Remove unnecessary normal-user connector/camera IDs and legacy ONEVO branding while retaining internal compatibility paths/service names until migration is proven.
- Ensure backend-offline mode leaves localhost UI available but blocks monitoring/upload and reports `Backend unavailable`.

Exit gate: browser/tray/native views agree on counts, states, camera names, zones, and pause/backend status.

### Phase 7 — Optimize, verify, and serve locally

- Add unit/integration tests for source parsing, ownership, polygon validation, frozen-frame semantics, pause/outage lifecycle, and setup idempotency.
- Run Python compile/tests, backend build/tests, Angular production build, PyInstaller clean build, and Inno compile.
- Run installer UI screenshot checks at supported DPI levels.
- Measure clean component sizes and perform the minimal-FFmpeg experiment.
- Sign installer/runtime and calculate SHA-256 beside the local artifact.
- Start the Docker stack through `dev-up.ps1` and verify the backend serves the installer directly from `connector/dist`.
- Verify dashboard download metadata and downloaded hash/size/version against the local file.
- Do not deploy or reference Vercel in this workflow.

Exit gate: a fresh clone on a supported Windows host builds the missing installer, starts Docker, and passes a fresh-machine end-to-end test without Vercel.

## 7. Acceptance matrix

| Scenario | Expected result |
| --- | --- |
| Backend off before setup | Stage 1 blocks with retry; no false install success |
| Invalid/expired/used setup code | Inline failure; code is not treated as configured |
| Store already has active connector | Clear conflict; second connector cannot claim |
| Zero sources | Source button is `Skip`; zone stage is skipped |
| One or more validated sources | Source button becomes `Next` |
| Zero zones | Zone button is `Skip` |
| One or more saved zones | Zone button becomes `Install` |
| Camera A frame refreshed | Camera B frame and zones remain unchanged |
| Background frames arrive | Frozen zone frame does not change |
| Connector/service off | Saved camera-specific MinIO frame remains viewable remotely |
| Camera has no zones | No motion clips are produced for that camera |
| Stop push | Capture handles, motion, uploader, and heartbeat stop; local UI stays up |
| Backend outage while running | Pipelines stop after threshold; queued work remains durable |
| Backend recovers | Credentials verified, then camera-specific pipelines resume |
| Successful install | Summary counts and service state are measured, not hardcoded |
| Upgrade/repair | Existing store identity, sources, zones, frames, and pause marker are preserved |
| Fresh clone, installer absent | `dev-up.ps1` installs build packages, obtains verified tools, builds EXE, then starts Docker |
| Installer sources unchanged | Bootstrap reuses the valid artifact instead of rebuilding |
| Installer source/version/backend URL changed | Fingerprint forces rebuild before Docker starts |
| Installer build fails | Docker backend does not start with a false download option |
| Plain Docker started without artifact | Backend reports `installer_not_built`; no Vercel redirect |

## 8. First implementation slice

The first code change should prioritize the native wizard and a buildable artifact:

1. Add the wide reusable layout/theme helpers and real ONETIX assets.
2. Rebuild Stage 1 to match the screenshot.
3. Correct the footer state machine (`Next`, `Skip`, `Install`, `Finish`).
4. Compile the `.iss`, run the installer, and compare Stage 1 with the supplied sample.
5. Add backend preflight/claim with inline validation and retry.
6. Add the fresh-clone `dev-up.ps1` installer-build gate before Docker Compose.
7. Add automated checks for page transitions, failure states, artifact presence, and backend download metadata.

Only after this slice is visually approved should source and zone page controls be rebuilt. This minimizes rework because every later installer page uses the same shell, spacing, typography, and footer behavior.

## 9. Definition of done

The work is done only when the rewritten native wizard matches the supplied designs, backend-offline or invalid setup cannot produce success, multiple sources operate under one connector, frames and zones are strictly camera-scoped, frames change only on initial load or explicit refresh, MinIO keeps the selected frame available while the connector is offline, no-zone cameras produce no motion clips, Start/Stop push controls the full runtime, clean install/upgrade/repair/uninstall pass, a fresh clone automatically builds a missing installer before Docker starts, the backend serves that artifact directly from `connector/dist`, and no Vercel installer fallback remains in the active flow.

## 10. Third visual audit — current build versus approved blue references

Status: plan-only correction pass requested on 2026-08-10. The three latest screenshots are the actual current installer output and override earlier assumptions that the previous UI pass was visually complete.

### 10.1 Current-output findings

#### Setup-code page

- The approved left blue illustration panel is missing; only the small standard Inno header logo remains at the top-right.
- Content starts too close to the left edge and uses almost the full window width, creating excessive empty white space on the right and bottom.
- Heading, description, label, input, helper, example, and security text do not share the compact vertical rhythm of the approved reference.
- The input is too wide and looks like a default Windows edit control rather than the bordered form field in the target.
- Secondary example/security copy adds visual noise not present in the latest approved `Connect ONETIX` reference.
- Footer height, separator, and Next-button placement are not aligned to the reference grid.

#### Source page

- The left illustration panel is absent, so the entire content is displaced upward/left relative to the approved blue-shell layout.
- Default Inno header title/description and top-right small image are still visible, producing a second competing header system.
- Source buttons look like large default Windows buttons; target tabs are compact cards with icons, selected-blue border/fill, and consistent spacing.
- The MP4 area visually says drag/drop, but the current implementation is only a panel plus Browse button; Explorer file-drop behavior is not yet wired.
- Drop area height, border, icon, typography, and Browse button do not match the reference.
- `Add Source` spans the complete form width in the current output; target places it as a compact action associated with the source form.
- Added-source table/card is absent until data exists and has no persistent column structure, so the page jumps vertically.
- Back/Skip/Next actions do not use the target primary/secondary hierarchy.

#### Success page

- Current output is blank except for the left illustration and Finish button.
- Root cause: built-in `FinishedHeadingLabel`/`FinishedLabel` are hidden, while custom success controls are parented to `InnerNotebook`; the finished page uses a different active notebook/page layer and covers those controls.
- Success must be a dedicated page rendered before the standard finished page, or the standard finished page controls must be restyled in their own container. Overlaying form/notebook controls is not reliable.
- The approved output needs green success mark, heading, description, four aligned summary rows, explanatory footer copy, and Finish.

### 10.2 Layout architecture correction

Do not continue patching `Surface.Left`, global form overlays, or `BringToFront` calls. Replace the current mixed standard/custom layout with one deterministic shell:

1. Create every onboarding stage as a `CreateCustomPage` page, including setup code and success.
2. Give every page its own two-column root:
   - fixed `180–200 px` blue sidebar bitmap on the left;
   - fixed content panel on the right;
   - no standard Inno page header inside the page.
3. Parent all page controls to that page's content panel. Never parent onboarding controls directly to `WizardForm` or `InnerNotebook`.
4. Use one reusable layout procedure for sidebar, heading, subtitle, footer separator, Back/Skip/Next/Install/Finish positions, colors, and fonts.
5. Keep controls within a `920 x 650` design canvas and calculate scaled positions using `ScaleX/ScaleY` from one token table.
6. Use z-order only inside each page. Do not depend on cross-notebook overlays.
7. Replace the standard `wpFinished` experience with a custom `SuccessPage`; skip `wpFinished` visual content or leave it only as an internal terminal page.

### 10.3 Window behavior

- Minimize must remain enabled on all non-installing pages and during safe installation phases.
- Close (`X`) must work on setup/source/zone pages and ask a single confirmation when staged changes exist.
- During file-copy/service-registration critical sections, Close must be disabled or intercepted with a clear “installation in progress” message.
- After completion, Close and Finish must exit cleanly and stop any temporary capture/helper process.
- Remove the current unconditional `WizardForm.CancelButton.Visible := False`; use a visible Cancel/Close policy driven by page/install state.
- Test title-bar minimize, restore, Alt+F4, taskbar close, Finish, and cancellation before/after staging an MP4.

### 10.4 Exact visual tokens

| Token | Target |
| --- | --- |
| Window | `920 x 650`, DPI-aware |
| Sidebar | `180–200 px`, `#EFF8FF`/soft blue gradient, centered connector illustration |
| Content background | white |
| Primary blue | approximately `#0668E8` |
| Selected card | pale blue fill + 1 px primary border |
| Heading | Segoe UI 18–20 px semibold/bold |
| Body | Segoe UI 9–11 px, dark gray |
| Field height | 34–40 px |
| Card radius | native approximation with consistent 6–8 px visual radius |
| Footer | 68–72 px with top separator |
| Primary button | blue fill, white text, right aligned |
| Secondary button | white fill, gray border |
| Success | green circle/check and four rows aligned to a two-column summary grid |

### 10.5 Page-specific target

#### Connect ONETIX

- Sidebar visible from content top to footer separator.
- Heading, one-sentence description, Setup Code label, one input, one helper sentence only.
- Remove duplicate example/security paragraphs unless product/security explicitly requires them.
- Next remains disabled until non-empty format-valid code; backend validation error appears inline without a modal.

#### Add Camera Sources

- Three compact source tabs: RTSP, ONVIF, Video File.
- Keep table headers visible even when empty: Source Name, Type, Source, Status, Actions.
- RTSP: compact URL field and right-side Add Source.
- ONVIF: Discover Cameras action and stable table below.
- MP4: dashed border, upload icon, `Drag & drop your video file here`, `or`, blue Browse Files button.
- Implement real native Windows Explorer drop handling; visual copy alone is not acceptance.
- Edit/Delete/Clear All must not cause layout movement.

#### Configure Detection Zones

- Source selector and Refresh Frame in a top row.
- Frozen 16:9 frame on the left; zone name/type, zone list, edit/delete, undo/clear/save on the right.
- Back left and Install right in the common footer.
- No frame replacement except first load or explicit Refresh Frame.

#### Success

- Dedicated custom success page with the blue sidebar.
- Green check, `Installation Successful!`, description, and aligned rows for Setup Code, Sources, Detection Zones, Connector Service.
- Show only after local health, pairing, source provisioning, zone sync, and service checks pass.
- Finish exits without navigating through another blank page.

## 11. Local dashboard and logs redesign plan

The local browser UI (`connector/app/admin.py`) and native tray dashboard (`connector/app/tray_dashboard.py`) must use the approved blue ONETIX language rather than the current plain/default white presentation.

### Shared visual system

- Introduce one token set: navy sidebar, primary blue, pale-blue selected states, white cards, light gray/blue page background, success/warning/danger colors, consistent borders and shadows.
- Use the same ONETIX logo, typography, button hierarchy, status pills, spacing, and icon language as the installer.
- Preserve WCAG-readable contrast and visible keyboard focus.

### Dashboard

- Fixed blue/navy left navigation with ONETIX brand and active-item blue highlight.
- Header contains page title, connector/backend state, and Start Push/Stop Push primary action.
- Summary cards: Sources, Running Cameras, Zones, Queue, Backend.
- Camera grid supports responsive multi-camera and single focus view without exposing normal-user IDs.
- Empty/offline/error states use designed cards, not raw text.

### Logs

- Separate Logs page with blue-shell navigation retained.
- Toolbar: severity filter, camera/source filter, search, auto-refresh toggle, Refresh, Export.
- Monospace log table/stream with timestamp, level pill, component/source, and message.
- Errors/warnings use restrained semantic colors; page background remains consistent with Dashboard.
- Avoid uncontrolled five-second full-page rerenders; append or refresh data without losing selection/scroll unless the user enables follow mode.

### Local UI acceptance

- Dashboard and Logs match at 100%, 125%, and 150% scaling and common desktop widths.
- Start/Stop state is backend-driven and consistent with tray state.
- Backend unavailable and connector paused are visually distinct.
- Multiple cameras retain camera-specific frames and zone overlays in grid and focus views.
- No Connector ID/Camera ID in standard cards or tables.

## 12. Revised implementation sequence

1. Freeze the approved blue screenshots and create an installer visual checklist with exact coordinates/tokens.
2. Remove the current global sidebar/notebook overlay implementation.
3. Build the reusable per-page custom shell and window close/minimize state controller.
4. Rebuild Connect ONETIX and approve its screenshot before continuing.
5. Rebuild source tabs/table and implement actual MP4 Explorer drag/drop.
6. Rebuild zone editor in the same shell while preserving camera/frame isolation.
7. Add the dedicated success page and health-gated navigation.
8. Rebuild installer and capture all pages at 100%, 125%, and 150% DPI.
9. Apply shared blue tokens to local Dashboard and Logs, then verify browser/tray state parity.
10. Run functional, visual, upgrade, cancellation, and packaging-size gates before replacing the served artifact.

## 13. Implementation result — 2026-08-10

- Installer pages use the fixed ONETIX light-blue brand rail and deterministic content offsets.
- Zone reference viewport is fixed at 480 × 362 pixels.
- Setup Code keeps Next disabled until a non-empty value is entered.
- Native minimize, close, and cancel behavior is retained.
- Finished-page content is placed above the Inno notebook layer to prevent the blank success screen.
- Local Dashboard and Logs use the supplied dark navy visual system without replacing the ONETIX identity.
- Optimized installer rebuilt at `connector/dist/ONETIX-Connector-Setup-1.1.20.exe` (129.55 MB).
- Verification: connector tests 45/45, Inno compile successful, backend Docker build successful, `/api/health` reports `ok`.
