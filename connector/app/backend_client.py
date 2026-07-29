"""HTTP client for the ONEVO backend (registration, clips, heartbeat, ONVIF device info)."""
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

    def claim_setup_code(self, setup_code: str, name: str, version: str) -> tuple[str, str, str]:
        """Claim a dashboard-generated setup code. Returns (connector_id, api_key, store_id)."""
        r = requests.post(
            f"{self.base}/api/connectors/claim",
            json={"setupCode": setup_code, "name": name, "version": version},
            timeout=20,
        )
        if not r.ok:
            try:
                detail = r.json().get("error") or r.json().get("detail") or r.text
            except Exception:  # noqa: BLE001
                detail = r.text
            raise RuntimeError(detail or f"claim failed ({r.status_code})")
        data = r.json()
        self.connector_id = data["connectorId"]
        self.api_key = data["apiKey"]
        store_id = data.get("storeId") or data.get("store_id") or ""
        return self.connector_id, self.api_key, store_id

    def create_camera(self, body: dict) -> dict:
        """Create a camera for this connector's store (connector auth)."""
        r = requests.post(
            f"{self.base}/api/connectors/cameras",
            headers=self._auth_headers(),
            json=body,
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    def finalize_setup(self, source_keys: list[str]) -> dict:
        """Make a fully provisioned source set authoritative (safe to retry)."""
        r = requests.post(
            f"{self.base}/api/connectors/finalize-setup",
            headers=self._auth_headers(),
            json={"sourceKeys": source_keys},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

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

    def heartbeat(
        self,
        disk_free_pct: float,
        queue_depth: int,
        degraded_reason: str | None,
        version: str,
        admin_host: str | None = None,
        admin_port: int | None = None,
    ) -> None:
        payload: dict = {
            "diskFreePct": disk_free_pct,
            "uploadQueueDepth": queue_depth,
            "degradedReason": degraded_reason,
            "version": version,
        }
        if admin_host:
            payload["adminHost"] = admin_host
        if admin_port:
            payload["adminPort"] = admin_port
        r = requests.post(
            f"{self.base}/api/connectors/heartbeat",
            headers=self._auth_headers(),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()

    def update_device_info(self, camera_id: str, info: dict) -> None:
        """Push ONVIF device metadata to the backend camera record (best-effort)."""
        r = requests.put(
            f"{self.base}/api/cameras/{camera_id}/device-info",
            headers=self._auth_headers(),
            json=info,
            timeout=15,
        )
        r.raise_for_status()

    def get_cameras(self) -> list[dict]:
        """Fetch all cameras assigned to this connector's store."""
        r = requests.get(
            f"{self.base}/api/connectors/cameras",
            headers=self._auth_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
