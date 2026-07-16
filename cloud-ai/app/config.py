"""Cloud AI worker configuration from environment variables."""
import os
from dataclasses import dataclass, field


def _parse_prompts(raw: str) -> dict[str, str] | None:
    """Parse "prompt=cue,prompt=cue" into {prompt: canonical_cue}. Empty -> None (use defaults)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    out: dict[str, str] = {}
    for pair in raw.split(","):
        if "=" in pair:
            prompt, cue = pair.split("=", 1)
            prompt, cue = prompt.strip(), cue.strip()
            if prompt and cue:
                out[prompt] = cue
    return out or None


@dataclass
class Config:
    redis_connection: str
    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    backend_url: str
    service_key: str
    model_backend: str          # yoloe | yolo26 | rfdetr
    model: str                  # weights file / name
    device: str                 # cpu | cuda
    yoloe_prompts: dict[str, str] | None = field(default=None)

    @staticmethod
    def load() -> "Config":
        return Config(
            redis_connection=os.getenv("REDIS_CONNECTION", "localhost:6379"),
            s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
            s3_bucket=os.getenv("S3_BUCKET", "onevo-clips"),
            s3_access_key=os.getenv("S3_ACCESS_KEY", "onevo_minio"),
            s3_secret_key=os.getenv("S3_SECRET_KEY", "onevo_minio_pw"),
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            backend_url=os.getenv("CLOUD_AI_BACKEND_URL", "http://localhost:8080").rstrip("/"),
            service_key=os.getenv("CONNECTOR_BOOTSTRAP_KEY", "dev-connector-bootstrap-key"),
            model_backend=os.getenv("CLOUD_AI_MODEL_BACKEND", "yoloe"),
            model=os.getenv("CLOUD_AI_MODEL", "yoloe-11s-seg.pt"),
            device=os.getenv("CLOUD_AI_DEVICE", "cpu"),
            yoloe_prompts=_parse_prompts(os.getenv("CLOUD_AI_YOLOE_PROMPTS", "")),
        )
