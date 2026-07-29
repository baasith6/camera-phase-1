"""Installed-mode paths and persisted wizard config (Windows ProgramData)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    """Directory containing the connector executable (or repo connector/ in dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def program_data_root() -> Path:
    # Explicit connector override comes first so tests and portable deployments
    # never touch the machine-wide Windows ProgramData directory.
    base = os.environ.get("CONNECTOR_PROGRAM_DATA") or os.environ.get("PROGRAMDATA")
    if base:
        return Path(base) / "ONEVO" / "Connector"
    # Non-Windows / Docker fallback
    return Path(os.environ.get("CONNECTOR_STATE_DIR", "data")).resolve().parent / "onevo-connector"


def default_state_dir() -> Path:
    env = os.environ.get("CONNECTOR_STATE_DIR")
    if env:
        return Path(env)
    if is_frozen() or os.name == "nt":
        return program_data_root() / "data"
    return Path("data")


def media_dir() -> Path:
    d = program_data_root() / "media"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return program_data_root() / "config.json"


def source_update_path() -> Path:
    return program_data_root() / "source-update.json"


def pause_marker_path() -> Path:
    """Machine-wide marker: monitoring must stay stopped across reboot/update."""
    return default_state_dir() / "monitoring.paused"


@dataclass
class CameraSource:
    name: str
    rtsp_url: str = ""
    source_file: str = ""  # local mp4 path
    camera_id: str = ""    # filled after backend create
    source_key: str = ""   # stable backend idempotency identity
    resolved_rtsp_url: str = ""  # ONVIF output; not part of physical identity
    loop: bool = False
    onvif_host: str = ""
    onvif_port: int = 80
    onvif_user: str = ""
    onvif_pass: str = ""
    onvif_profile: str = "auto"


@dataclass
class WizardConfig:
    """Persisted after the setup wizard completes."""
    setup_complete: bool = False
    store_id: str = ""
    connector_name: str = "edge-connector-1"
    sources: list[CameraSource] = field(default_factory=list)
    # When True and no local sources, use multi-cam orchestrator (backend camera list).
    use_backend_cameras: bool = True
    setup_code: str = ""
    activation_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "setup_complete": self.setup_complete,
            "store_id": self.store_id,
            "connector_name": self.connector_name,
            "use_backend_cameras": self.use_backend_cameras,
            "setup_code": self.setup_code,
            "activation_error": self.activation_error,
            "sources": [asdict(s) for s in self.sources],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WizardConfig":
        allowed = set(CameraSource.__dataclass_fields__)
        sources = [
            CameraSource(**{key: value for key, value in s.items() if key in allowed})
            for s in data.get("sources") or []
            if isinstance(s, dict)
        ]
        if not sources:
            rtsp_text = str(data.get("rtsp_text") or "")
            urls = [
                value.strip()
                for value in rtsp_text.replace("\r", "\n").replace(";", "\n").splitlines()
                if value.strip()
            ]
            sources.extend(
                CameraSource(name=f"Camera {index}", rtsp_url=url)
                for index, url in enumerate(urls, start=1)
            )
            onvif_text = str(data.get("onvif_text") or "")
            onvif_port = int(data.get("onvif_port") or 80)
            onvif_user = str(data.get("onvif_user") or "admin")
            onvif_pass = str(data.get("onvif_pass") or "")
            onvif_hosts = [
                value.strip()
                for value in onvif_text.replace("\r", "\n").replace(";", "\n").splitlines()
                if value.strip()
            ]
            for index, value in enumerate(onvif_hosts, start=1):
                host, port = value, onvif_port
                if value.count(":") == 1:
                    maybe_host, maybe_port = value.rsplit(":", 1)
                    if maybe_port.isdigit():
                        host, port = maybe_host.strip(), int(maybe_port)
                sources.append(
                    CameraSource(
                        name=f"ONVIF Camera {index}",
                        onvif_host=host,
                        onvif_port=port,
                        onvif_user=onvif_user,
                        onvif_pass=onvif_pass,
                    )
                )
            source_file = str(data.get("source_file") or "")
            if source_file:
                sources.append(
                    CameraSource(
                        name="Test Video",
                        source_file=source_file,
                        loop=bool(data.get("loop_file", True)),
                    )
                )
        return cls(
            setup_complete=bool(data.get("setup_complete")),
            store_id=str(data.get("store_id") or ""),
            connector_name=str(data.get("connector_name") or "edge-connector-1"),
            use_backend_cameras=bool(data.get("use_backend_cameras", True)),
            setup_code=str(data.get("setup_code") or ""),
            activation_error=str(data.get("activation_error") or ""),
            sources=sources,
        )


def load_wizard_config() -> WizardConfig | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WizardConfig.from_dict(data)
    except Exception:
        return None


def save_wizard_config(cfg: WizardConfig) -> Path:
    root = program_data_root()
    root.mkdir(parents=True, exist_ok=True)
    path = config_path()
    path.write_text(json.dumps(cfg.to_dict(), indent=2), encoding="utf-8")
    return path


def apply_pending_source_update(cfg: WizardConfig) -> bool:
    """Apply installer source changes without replacing connector identity."""
    path = source_update_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        update = WizardConfig.from_dict({"sources": data.get("sources") or []})
        if not update.sources:
            return False
        cfg.sources = update.sources
        cfg.setup_complete = False
        save_wizard_config(cfg)
        path.unlink()
        return True
    except Exception:
        return False


def resolve_ffmpeg() -> str:
    """Prefer bundled ffmpeg next to the exe, then env, then PATH name."""
    env = os.environ.get("FFMPEG_PATH")
    if env and Path(env).exists():
        return env
    bundled = install_dir() / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"
