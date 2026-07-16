"""Backend HTTP client for the cloud-ai worker (service-key authenticated)."""
import requests


class BackendClient:
    def __init__(self, base_url: str, service_key: str):
        self.base = base_url.rstrip("/")
        self.headers = {"X-Service-Key": service_key}

    def get_zones(self, camera_id: str) -> list[dict]:
        r = requests.get(
            f"{self.base}/api/service/cameras/{camera_id}/zones",
            headers=self.headers,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def post_ai_events(self, clip_id: str, model_version: str, events: list[dict]) -> dict:
        r = requests.post(
            f"{self.base}/api/ai-events",
            headers=self.headers,
            json={"clipId": clip_id, "modelVersion": model_version, "events": events},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
