"""Connector configuration from environment variables and CLI args."""
import argparse
import os
from dataclasses import dataclass

from . import baked_config
from .paths import default_state_dir, load_wizard_config


@dataclass
class Config:
    backend_url: str
    bootstrap_key: str
    store_id: str
    connector_name: str
    version: str
    source: str            # file path or rtsp url (auto-filled from ONVIF if onvif_host set)
    loop: bool             # loop a file source (useful for testing)
    admin_port: int
    state_dir: str
    camera_id: str

    # Clip / trigger tuning
    fps: float
    pre_seconds: float
    post_seconds: float
    cooldown_seconds: float
    motion_area_frac: float   # fraction of frame that must change to count as motion
    use_person_filter: bool

    # Reliability
    disk_warn_pct: float
    disk_critical_pct: float
    max_upload_retries: int
    rtsp_reconnect_max_sec: float  # max backoff seconds before giving up a reconnect attempt

    # ONVIF (optional — leave onvif_host empty to use --source directly)
    onvif_host: str          # IP or hostname of the camera, e.g. "192.168.1.64"
    onvif_port: int          # ONVIF HTTP port, usually 80 or 8080
    onvif_user: str          # ONVIF username
    onvif_pass: str          # ONVIF password
    onvif_profile: str       # "auto" = pick highest-res profile; or explicit token

    # Installer modes
    wizard_mode: bool = False
    service_mode: bool = False


def _default_backend_url() -> str:
    env = os.getenv("CONNECTOR_BACKEND_URL", "").strip()
    if env:
        return env
    baked = (getattr(baked_config, "BAKED_BACKEND_URL", "") or "").strip()
    if baked:
        return baked
    return "http://localhost:8081"


def load_config(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(description="ONEVO Local Connector")
    p.add_argument("--source", default=os.getenv("CONNECTOR_SOURCE", "samples/test.mp4"),
                   help="Video source: file path or rtsp:// URL (auto-set from ONVIF if --onvif-host given)")
    p.add_argument("--loop", action="store_true", default=os.getenv("CONNECTOR_LOOP", "false").lower() == "true",
                   help="Loop a file source forever (testing)")
    p.add_argument("--backend", default=_default_backend_url())
    p.add_argument("--store-id", default=os.getenv("CONNECTOR_STORE_ID", ""))
    p.add_argument("--bootstrap-key", default=os.getenv("CONNECTOR_BOOTSTRAP_KEY", "dev-connector-bootstrap-key"))
    p.add_argument("--name", default=os.getenv("CONNECTOR_NAME", "edge-connector-1"))
    p.add_argument("--admin-port", type=int, default=int(os.getenv("CONNECTOR_ADMIN_PORT", "8099")))
    p.add_argument("--camera-id", default=os.getenv("CONNECTOR_CAMERA_ID"),
                   help="Camera GUID this connector feeds (optional — omit for multi-camera mode)")
    p.add_argument("--wizard", action="store_true",
                   help="Open the first-run setup wizard in the browser")
    p.add_argument("--service", action="store_true",
                   help="Windows service mode (load ProgramData config, no interactive wizard)")

    # ONVIF arguments
    p.add_argument("--onvif-host", default=os.getenv("CONNECTOR_ONVIF_HOST", ""),
                   help="Camera IP/hostname for ONVIF connection (enables auto RTSP URL extraction)")
    p.add_argument("--onvif-port", type=int, default=int(os.getenv("CONNECTOR_ONVIF_PORT", "80")),
                   help="Camera ONVIF HTTP port (default 80)")
    p.add_argument("--onvif-user", default=os.getenv("CONNECTOR_ONVIF_USER", "admin"),
                   help="ONVIF username")
    p.add_argument("--onvif-pass", default=os.getenv("CONNECTOR_ONVIF_PASS", "admin"),
                   help="ONVIF password")
    p.add_argument("--onvif-profile", default=os.getenv("CONNECTOR_ONVIF_PROFILE", "auto"),
                   help="ONVIF profile token (default: auto = highest-res profile)")

    args = p.parse_args(argv)

    store_id = args.store_id
    connector_name = args.name
    source = args.source
    loop = args.loop
    camera_id = args.camera_id or ""

    # Installed / wizard-persisted overrides (service mode).
    wizard = load_wizard_config()
    if args.service and wizard and wizard.setup_complete:
        if wizard.store_id:
            store_id = wizard.store_id
        if wizard.connector_name:
            connector_name = wizard.connector_name
        # Prefer multi-camera orchestrator when wizard saved backend cameras.
        if wizard.use_backend_cameras and wizard.sources:
            camera_id = ""  # orchestrator mode
        elif wizard.sources:
            first = wizard.sources[0]
            camera_id = first.camera_id or camera_id
            if first.rtsp_url:
                source = first.rtsp_url
                loop = False
            elif first.source_file:
                source = first.source_file
                loop = first.loop

    cfg = Config(
        backend_url=args.backend.rstrip("/"),
        bootstrap_key=args.bootstrap_key,
        store_id=store_id,
        connector_name=connector_name,
        version="1.1.0",
        source=source,
        loop=loop,
        admin_port=args.admin_port,
        state_dir=str(default_state_dir()),
        camera_id=camera_id,
        fps=float(os.getenv("CONNECTOR_FPS", "10")),
        pre_seconds=float(os.getenv("CONNECTOR_PRE_SECONDS", "10")),
        post_seconds=float(os.getenv("CONNECTOR_POST_SECONDS", "10")),
        # CPU inference commonly takes longer than a short event clip. A one-minute
        # default prevents a looping file or noisy camera from outrunning cloud-ai.
        cooldown_seconds=float(os.getenv("CONNECTOR_COOLDOWN_SECONDS", "60")),
        motion_area_frac=float(os.getenv("CONNECTOR_MOTION_AREA_FRAC", "0.02")),
        use_person_filter=os.getenv("CONNECTOR_PERSON_FILTER", "false").lower() == "true",
        disk_warn_pct=float(os.getenv("CONNECTOR_DISK_WARN_PCT", "20")),
        disk_critical_pct=float(os.getenv("CONNECTOR_DISK_CRITICAL_PCT", "10")),
        max_upload_retries=int(os.getenv("CONNECTOR_MAX_RETRIES", "5")),
        rtsp_reconnect_max_sec=float(os.getenv("CONNECTOR_RTSP_RECONNECT_MAX_SEC", "60")),
        onvif_host=args.onvif_host.strip(),
        onvif_port=args.onvif_port,
        onvif_user=args.onvif_user,
        onvif_pass=args.onvif_pass,
        onvif_profile=args.onvif_profile,
        wizard_mode=bool(args.wizard),
        service_mode=bool(args.service),
    )
    return cfg
