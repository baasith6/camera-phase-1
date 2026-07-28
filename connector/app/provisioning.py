"""Shared connector pairing and camera provisioning workflow."""
from __future__ import annotations

from pathlib import Path

from . import paths
from .paths import CameraSource, WizardConfig


def validate_sources(sources: list[CameraSource]) -> None:
    if not sources:
        raise ValueError("configure at least one camera source")

    for source in sources:
        modes = sum(bool(value) for value in (
            source.rtsp_url, source.source_file, source.onvif_host
        ))
        if modes != 1:
            raise ValueError(f"{source.name}: configure exactly one source type")
        if source.rtsp_url and not source.rtsp_url.lower().startswith("rtsp://"):
            raise ValueError(f"{source.name}: RTSP URL must start with rtsp://")
        if source.source_file and not Path(source.source_file).is_file():
            raise ValueError(f"{source.name}: video file does not exist")
        if source.onvif_host and not (1 <= int(source.onvif_port) <= 65535):
            raise ValueError(f"{source.name}: invalid ONVIF port")


def claim_setup(client, store, wizard: WizardConfig, version: str) -> tuple[str, str]:
    cid, key, store_id = client.claim_setup_code(
        wizard.setup_code, wizard.connector_name, version
    )
    store.set_cred("connector_id", cid)
    store.set_cred("api_key", key)
    store.set_cred("store_id", store_id)
    client.set_credentials(cid, key)
    wizard.store_id = store_id
    wizard.setup_code = ""
    wizard.setup_complete = False
    paths.save_wizard_config(wizard)
    return cid, store_id


def provision_sources(client, sources: list[CameraSource], state) -> list[CameraSource]:
    validate_sources(sources)
    created: list[CameraSource] = []

    for source in sources:
        rtsp_url = source.rtsp_url
        device_info = None
        if source.onvif_host:
            from .onvif_client import OnvifCamera
            onvif = OnvifCamera().connect(
                source.onvif_host,
                source.onvif_port,
                source.onvif_user or "admin",
                source.onvif_pass,
            )
            profile = None if source.onvif_profile == "auto" else source.onvif_profile
            rtsp_url = onvif.get_rtsp_url(profile)
            device_info = onvif.get_device_info()

        camera = client.create_camera({
            "name": source.name,
            "rtspUrl": rtsp_url or f"file://{source.source_file}",
            "onvifHost": source.onvif_host or None,
            "onvifPort": source.onvif_port if source.onvif_host else None,
            "useDemoZones": bool(source.source_file),
        })
        source.camera_id = camera.get("id") or camera.get("Id") or ""
        source.rtsp_url = rtsp_url

        if device_info and source.camera_id:
            try:
                client.update_device_info(source.camera_id, {
                    "manufacturer": device_info.manufacturer,
                    "model": device_info.model,
                    "serial": device_info.serial,
                    "firmware": device_info.firmware,
                })
            except Exception as exc:  # noqa: BLE001
                state.log(f"WARNING: ONVIF device info update failed: {exc}")
        created.append(source)

    return created


def complete_setup(wizard: WizardConfig, sources: list[CameraSource]) -> None:
    wizard.sources = sources
    wizard.use_backend_cameras = True
    wizard.setup_code = ""
    wizard.setup_complete = True
    paths.save_wizard_config(wizard)
