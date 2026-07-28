"""Persisted clip tuning (pre/post/cooldown) for the connector admin UI."""
from __future__ import annotations

import json
from dataclasses import dataclass

from .paths import program_data_root


@dataclass
class ClipSettings:
    pre_seconds: float = 10.0
    post_seconds: float = 10.0
    cooldown_seconds: float = 60.0

    def apply_to_config(self, cfg) -> None:
        cfg.pre_seconds = self.pre_seconds
        cfg.post_seconds = self.post_seconds
        cfg.cooldown_seconds = self.cooldown_seconds


def _settings_path():
    return program_data_root() / "clip_settings.json"


def load_clip_settings(defaults: ClipSettings | None = None) -> ClipSettings:
    base = defaults or ClipSettings()
    path = _settings_path()
    if not path.exists():
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ClipSettings(
            pre_seconds=float(data.get("pre_seconds", base.pre_seconds)),
            post_seconds=float(data.get("post_seconds", base.post_seconds)),
            cooldown_seconds=float(data.get("cooldown_seconds", base.cooldown_seconds)),
        )
    except Exception:
        return base


def save_clip_settings(settings: ClipSettings) -> None:
    root = program_data_root()
    root.mkdir(parents=True, exist_ok=True)
    path = _settings_path()
    path.write_text(
        json.dumps(
            {
                "pre_seconds": settings.pre_seconds,
                "post_seconds": settings.post_seconds,
                "cooldown_seconds": settings.cooldown_seconds,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
