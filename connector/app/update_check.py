"""Check for connector installer updates from the backend installer metadata."""
from __future__ import annotations

import requests


def check_for_update(backend_url: str, current_version: str, log) -> None:
    try:
        r = requests.get(f"{backend_url.rstrip('/')}/api/connectors/installer", timeout=15)
        if not r.ok:
            return
        data = r.json()
        latest = (data.get("version") or data.get("Version") or "").strip()
        if latest and latest != current_version:
            log(
                f"UPDATE AVAILABLE: connector {current_version} -> {latest}. "
                "Download the latest installer from the dashboard."
            )
    except Exception as exc:  # noqa: BLE001
        log(f"Update check skipped: {exc}")
