"""MinIO/S3 clip download."""
from urllib.parse import urlparse

from minio import Minio

from .config import Config


class ClipStore:
    def __init__(self, cfg: Config):
        uri = urlparse(cfg.s3_endpoint)
        secure = uri.scheme == "https"
        endpoint = uri.netloc  # host:port
        self._client = Minio(
            endpoint,
            access_key=cfg.s3_access_key,
            secret_key=cfg.s3_secret_key,
            secure=secure,
            region=cfg.s3_region,
        )
        self._bucket = cfg.s3_bucket

    def download(self, object_key: str, dest_path: str) -> None:
        self._client.fget_object(self._bucket, object_key, dest_path)
