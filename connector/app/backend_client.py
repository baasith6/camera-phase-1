"""HTTP client for the ONEVO backend (registration, clips, heartbeat)."""
import requests


class BackendClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.connector_id: str | None = None
        self.api_key: str | None = None

    def _auth_headers(self) -> dict:
        return {
            "X-Connector-Id": self.connector_id or "",
            "X-Connector-Key": self.api_key or "",
        }

    def register(self, store_id: str, name: str, version: str, bootstrap_key: str) -> tuple[str, str]:
        r = requests.post(
            f"{self.base}/api/connectors/register",
            json={"storeId": store_id, "name": name, "version": version, "bootstrapKey": bootstrap_key},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        self.connector_id = data["connectorId"]
        self.api_key = data["apiKey"]
        return self.connector_id, self.api_key

    def set_credentials(self, connector_id: str, api_key: str) -> None:
        self.connector_id = connector_id
        self.api_key = api_key

    def request_upload_url(self, camera_id: str, duration_sec: float, trigger: str) -> dict:
        r = requests.post(
            f"{self.base}/api/clips/upload-url",
            headers=self._auth_headers(),
            json={"cameraId": camera_id, "durationSec": duration_sec, "triggerReason": trigger},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def upload_file(self, upload_url: str, file_path: str) -> None:
        with open(file_path, "rb") as f:
            r = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
        r.raise_for_status()

    def complete_clip(self, clip_id: str) -> None:
        r = requests.post(
            f"{self.base}/api/clips/{clip_id}/complete",
            headers=self._auth_headers(),
            json={"clipId": clip_id},
            timeout=30,
        )
        r.raise_for_status()

    def heartbeat(self, disk_free_pct: float, queue_depth: int, degraded_reason: str | None, version: str) -> None:
        r = requests.post(
            f"{self.base}/api/connectors/heartbeat",
            headers=self._auth_headers(),
            json={
                "diskFreePct": disk_free_pct,
                "uploadQueueDepth": queue_depth,
                "degradedReason": degraded_reason,
                "version": version,
            },
            timeout=15,
        )
        r.raise_for_status()
