"""Local clip file helpers for admin operations."""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import cv2

from .config import Config
from .paths import load_wizard_config, resolve_ffmpeg


def _normalize_source(source: str) -> str:
    if source.startswith("file://"):
        return source[len("file://") :]
    return source


def resolve_file_source(cfg: Config) -> Path | None:
    """Return local MP4 path from config or wizard, or None if RTSP-only."""
    raw = cfg.source or ""
    src = _normalize_source(raw)
    if src and not raw.lower().startswith("rtsp"):
        path = Path(src)
        if path.is_file():
            return path

    wizard = load_wizard_config()
    if wizard:
        for item in wizard.sources:
            if item.source_file and Path(item.source_file).is_file():
                return Path(item.source_file)
    return None


def video_duration_sec(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if frames > 0 and fps > 0:
            return frames / fps
    finally:
        cap.release()
    return 0.0


def prepare_clip_file(source: Path, state_dir: str) -> tuple[str, float]:
    """Copy/transcode source video into clips dir; return (path, duration_sec)."""
    os.makedirs(os.path.join(state_dir, "clips"), exist_ok=True)
    clip_id = uuid.uuid4().hex
    dest = os.path.join(state_dir, "clips", f"{clip_id}.mp4")

    try:
        ffmpeg_bin = resolve_ffmpeg()
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(source),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-loglevel",
                "error",
                dest,
            ],
            check=True,
            timeout=600,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        shutil.copy2(source, dest)

    duration = video_duration_sec(Path(dest))
    return dest, duration


def list_local_clip_files(state_dir: str) -> list[dict]:
    clips_dir = os.path.join(state_dir, "clips")
    if not os.path.isdir(clips_dir):
        return []
    items = []
    for name in sorted(os.listdir(clips_dir)):
        if not name.lower().endswith(".mp4"):
            continue
        path = os.path.join(clips_dir, name)
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        items.append({"name": name, "path": path, "sizeBytes": size})
    return items


def clear_local_clip_files(state_dir: str) -> int:
    clips_dir = os.path.join(state_dir, "clips")
    if not os.path.isdir(clips_dir):
        return 0
    deleted = 0
    for name in os.listdir(clips_dir):
        if not name.lower().endswith(".mp4"):
            continue
        try:
            os.remove(os.path.join(clips_dir, name))
            deleted += 1
        except OSError:
            pass
    return deleted
