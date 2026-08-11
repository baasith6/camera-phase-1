# ONETIX Connector Installer — Four-Step Wizard Implementation Plan

## Target experience

The Windows installer must use one consistent 1.1.20 wizard shell and finish in four user-facing steps:

1. **Connect ONETIX** — setup-code input, with Next disabled until a non-empty code is entered.
2. **Add Camera Sources** — RTSP, ONVIF, and Video File tabs; multiple sources; drag/drop plus Browse Files for MP4; per-row edit and delete icon actions; optional Skip.
3. **Configure Detection Zones** — source-specific stable reference frame, explicit Refresh Frame, editable/deletable saved zones, Back, and dynamic Skip/Install action.
4. **Installation Successful** — success state rendered inside the same wizard with setup/source/zone/service summary and Finish.

## Visual contract

- Use the supplied ONETIX sidebar artwork on every user-facing page.
- Keep the compact desktop wizard dimensions and fixed footer from the approved screenshots.
- Use Segoe UI as the guaranteed Windows fallback. Optional bundled IBM Plex fonts may only be used when loading succeeds; font loading must never abort setup.
- Maintain consistent title, body, label, table, muted text, border, selected-tab, success, and primary-action styling.
- Keep the standard Windows title bar. Minimize and Close must work on every page; no custom title-bar replacement is allowed.
- Use deterministic control creation and z-order. No declared control may be styled, shown, or invoked before it is created.

## Functional contract

- Setup code validation gates Next.
- RTSP and ONVIF forms validate required connection fields.
- Video selection accepts multiple MP4 files and reports every accepted source.
- A source row owns its own edit/delete actions.
- Zones are stored against one source index only.
- The reference frame is stable across navigation and changes only through Refresh Frame.
- Zone setup is optional; skipping it must not prevent Live View from working.
- Installation writes sources, pending zones, and reference-frame paths before the service starts.
- The finished page must be part of the same wizard process.

## Runtime-safety requirements

- Base the rewrite on git revision `59080ea` (`Fix installer and wizard changes`), the last complete custom four-step implementation.
- Remove ad-hoc timer-based mouse polling if it causes Pascal callback dispatch failures; use a deterministic supported interaction.
- Guard optional font and shell integrations so unavailable procedures fall back without terminating setup.
- Ensure every sidebar, source control, zone row, and success label is constructed before `CurPageChanged` can access it.
- Keep native Close/Minimize behavior and avoid unsafe custom window-procedure hooks unless verified on the built Windows EXE.

## Build and acceptance checks

1. Compile through `docker compose up -d --build` from a fresh workspace.
2. Confirm Inno Setup reports `Successful compile` and produces `ONETIX-Connector-Setup-1.1.20.exe`.
3. Launch the produced EXE and verify no `Could not call proc` dialog appears.
4. Verify Connect, Sources, Zones, and Success pages against the supplied screenshots.
5. Verify title-bar Minimize and Close on every step.
6. Verify RTSP, ONVIF, multiple MP4, source edit/delete, zone save/edit/delete, Skip, Install, and Finish paths.
7. Verify the backend-mounted installer SHA-256 matches `connector/dist`.

