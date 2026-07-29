"""Resolve the connector admin host reported to the backend."""
from __future__ import annotations

import os
import socket


def admin_public_host() -> str:
    explicit = os.getenv("CONNECTOR_ADMIN_PUBLIC_HOST", "").strip()
    if explicit:
        return explicit
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        host = probe.getsockname()[0]
        probe.close()
        return host
    except OSError:
        return "127.0.0.1"
