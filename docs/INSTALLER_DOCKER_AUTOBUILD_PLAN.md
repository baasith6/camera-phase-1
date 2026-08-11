# ONETIX 1.1.20 Installer and Docker Auto-Build Plan

## 1. Objective

Provide one deterministic Windows connector installer for a fresh repository clone:

`connector/dist/ONETIX-Connector-Setup-1.1.20.exe`

The supported startup flow must:

1. Validate that every active connector/installer/backend version is `1.1.20`.
2. Detect a missing or stale installer before the backend advertises a download.
3. Build the connector executable and installer automatically when required.
4. Start the Docker backend only after the installer has been verified.
5. Keep only one active Inno Setup source and one canonical release artifact.
6. Rebuild when any installer input changes, not merely when the EXE is missing.

## 2. Required User Command and Docker Constraint

The backend container is a Linux .NET container. The Windows installer requires:

- Windows Python/PyInstaller to produce the native Windows connector executable.
- Inno Setup (`ISCC.exe`) to compile the `.iss` file.
- Windows-only service and tray binaries.

A normal Linux backend Dockerfile cannot execute Windows `ISCC.exe`, and Docker
Compose has no host-side `pre-up` hook. Nevertheless, the required and only
user-facing command is:

```powershell
docker compose up -d --build
```

To satisfy that exact command, add a dedicated Linux `installer-builder` Compose
service. It will use Wine with a pinned Windows Python/PyInstaller toolchain and
Inno Setup command-line compiler. It is a build-only container, separate from the
runtime backend image. The backend must depend on its successful completion.

This is heavier than a host wrapper, but it is the architecture that meets the
requirement that a fresh clone needs only `docker compose up -d --build`.

## 3. Canonical Version Contract

Create a single source of truth, preferably `version.json` at repository root:

```json
{
  "connector": "1.1.20",
  "installerFile": "ONETIX-Connector-Setup-1.1.20.exe"
}
```

All build/runtime components must read or be validated against it:

- `connector/installer/onevo-connector.iss`
- `connector/app/config.py`
- `connector/app/tray.py`
- connector local UI footer/title
- `backend/Services/ConnectorInstallerService.cs`
- `backend/appsettings.json`
- `.env` and `.env.example`
- `docker-compose.yml`
- installer documentation and download UI

Add a validation script that fails on active `1.1.18`, `1.1.19`, `revNN`, or
`ONEVO-Connector-Setup` references. Test fixtures and historical migration text may
be explicitly excluded.

## 4. Single Active ISS File

Keep only:

`connector/installer/onevo-connector.iss`

After confirming Git history contains the previous version, remove obsolete active
workspace copies such as:

- `connector/installer/onevo-connector.iss.full.bak`
- unused/renamed wizard bitmap assets
- legacy revision-specific installer definitions

The canonical `.iss` must contain:

- `AppVersion = 1.1.20`
- `OutputBaseFilename=ONETIX-Connector-Setup-{#AppVersion}`
- valid references to `wizard-sidebar.bmp`, `wizard-small.bmp`, icon, fonts,
  FFmpeg, WinSW, service XML, and `onevo-connector.exe`
- no stale undeclared pages, controls, handlers, or revision suffixes

Deletion is a separate implementation action and must be performed only after a
reference scan proves the files are unused.

## 5. Installer Input Fingerprint

Calculate SHA-256 over every file capable of changing the installer:

- `version.json`
- `connector/app/**`
- `connector/onevo_launcher.py`
- requirements and PyInstaller spec
- canonical `.iss`
- installer assets and fonts
- WinSW executable/configuration
- FFmpeg executable/version manifest
- backend URL baked into the connector

Store successful build metadata at:

`connector/dist/.installer-build.json`

Required fields:

```json
{
  "version": "1.1.20",
  "backendUrl": "http://localhost:8081",
  "fingerprint": "...",
  "sha256": "...",
  "sizeBytes": 0,
  "builtAtUtc": "..."
}
```

The installer is current only when:

1. Canonical EXE exists.
2. Metadata exists.
3. Version equals `1.1.20`.
4. Current input fingerprint equals stored fingerprint.
5. Current installer SHA-256 equals stored SHA-256.
6. PE ProductVersion equals `1.1.20`.

## 6. Compose-Managed Installer Builder

Add:

- `connector/installer/Dockerfile.builder`
- `connector/installer/docker-entrypoint.sh`
- a pinned Wine base image/digest
- pinned Windows Python, PyInstaller, Inno Setup, FFmpeg, and WinSW versions
- an `installer-builder` service in every applicable Compose file

The builder image must copy all installer inputs into its build context. Therefore
`docker compose up -d --build` rebuilds the builder image whenever connector code,
the ISS file, UI assets, requirements, or the version manifest changes.

The `installer-builder` service must perform:

```text
Load canonical version
  -> validate active version references
  -> calculate installer input fingerprint
  -> installer missing or stale?
       yes -> ensure Python/build dependencies
              ensure pinned FFmpeg and WinSW
              run PyInstaller
              compile canonical ISS with ISCC
              verify filename/version/hash
              atomically write fingerprint metadata
       no  -> print "Installer is current"
  -> write output to /output through ./connector/dist bind mount
  -> verify backend will see the exact mounted installer
  -> exit 0 only after version/hash verification succeeds
```

Build output must be written to a temporary filename first and moved atomically to
the canonical destination only after all validation succeeds. A failed build must
not overwrite the last known-good installer.

## 7. Docker Compose Dependency Graph

Configure Compose as follows:

```yaml
services:
  installer-builder:
    build:
      context: .
      dockerfile: connector/installer/Dockerfile.builder
    volumes:
      - ./connector/dist:/output
    restart: "no"

  backend:
    depends_on:
      installer-builder:
        condition: service_completed_successfully
    volumes:
      - ./connector/dist:/app/connector-dist:ro
```

Required behaviour:

1. Compose builds the installer-builder image first.
2. The one-shot builder validates or creates the canonical installer.
3. Builder failure prevents backend startup.
4. Backend starts only after the installer exits successfully.
5. Backend resolves only `ONETIX-Connector-Setup-1.1.20.exe`.
6. Dashboard download remains unavailable until backend validates the artifact.
7. Cloud AI/dashboard runtime images must not contain the Wine build toolchain.

Compose one-shot container lifecycle must be tested carefully. Because an exited
container can otherwise be reused, the builder image must include all source inputs
and its entrypoint must always validate the output fingerprint. Source changes alter
the image digest and force recreation during `--build`. Version changes likewise
change the image and canonical output name.

## 8. Backend Installer Contract

`ConnectorInstallerService` must:

- resolve only the canonical file
- advertise version `1.1.20`
- calculate SHA-256 from disk
- never fall back to Vercel or an old remote `1.1.19` URL
- never select the newest file using a wildcard
- return `installer_not_built` when the canonical file is unavailable
- serve the local file through the authenticated installer download endpoint

The backend does not compile the Windows installer itself. The Compose-managed
`installer-builder` completes that stage before backend startup.

## 9. Dist Cleanup Policy

After the canonical installer passes verification:

- canonical release: `ONETIX-Connector-Setup-1.1.20.exe`
- build payload: `onevo-connector.exe`
- fingerprint: `.installer-build.json`
- temporary PyInstaller work may remain ignored or be cleaned by a dedicated task

Revision artifacts (`rev2` through `rev18`) and old `ONEVO-*` installers must not be
served or considered by scripts. Removing existing historical binaries is a
destructive cleanup step and should happen only after the canonical hash is recorded.

## 10. Verification Matrix

### Version checks

- Active source scan contains no `1.1.18`, `1.1.19`, or `rev18` installer contract.
- ISS, connector runtime, backend, Compose, and metadata all report `1.1.20`.

### Build checks

- Delete/move the canonical EXE in a disposable test copy; `docker-up.cmd` rebuilds it.
- Modify one connector source file; fingerprint changes and rebuild occurs.
- Run again without changes; installer build is skipped.
- Break an ISS asset reference; startup stops before Docker and preserves last good EXE.

### Artifact checks

- Inno compiler succeeds.
- PE ProductVersion is `1.1.20`.
- Filename is canonical.
- Stored SHA-256 matches the actual file.
- Backend-mounted file has identical size/hash.

### Runtime checks

- `docker compose ps` reports backend/dashboard/cloud-ai running.
- Installer metadata returns version, filename, size, hash, and local download URL.
- Downloaded file hash matches `connector/dist`.
- Connector unit tests pass.
- Setup wizard opens, minimizes/closes, accepts setup code, adds sources, configures or
  skips zones, installs the service, and shows the success page.

## 11. Implementation Order

1. Introduce canonical version manifest and validation script.
2. Update all active version/file references to the manifest contract.
3. Retain one canonical ISS and remove proven-unused legacy files.
4. Harden build scripts with temporary output and atomic promotion.
5. Implement the Wine-based `installer-builder` image and entrypoint.
6. Add it as a successful-completion dependency of the backend in Compose files.
7. Complete fingerprint detection and metadata validation inside the container.
8. Add backend missing/stale artifact guardrails.
9. Build the canonical installer through Compose.
10. Run the verification matrix.
11. Only after verification, clean historical dist artifacts.

## 12. Acceptance Criteria

The work is complete when a clean clone with Docker Desktop can run only:

```powershell
docker compose up -d --build
```

and receive a verified `1.1.20` installer plus a running Docker stack without host
Python, Inno Setup, `.cmd`, or `.ps1` execution. A second run may reuse a verified
artifact, but it must validate its fingerprint. A connector source/UI/ISS/version
change must rebuild it automatically. The backend must serve only the canonical
local artifact and must never publish an old revision or remote Vercel installer.
