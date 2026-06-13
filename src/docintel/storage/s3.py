"""S3-compatible object storage for job artifacts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from docintel.storage.local import LocalStorage


class S3Storage(LocalStorage):
    """Stage files locally, mirror outputs to S3 for multi-node deploys."""

    def __init__(
        self,
        base_dir: str,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ):
        super().__init__(base_dir)
        if not bucket:
            raise ValueError("DOCINTEL_S3_BUCKET is required when DOCINTEL_STORAGE_BACKEND=s3")
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url

    def _client(self):
        import boto3

        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
        )

    def _object_key(self, job_id: str, filename: str) -> str:
        return f"jobs/{job_id}/{filename}"

    def sync_file(self, job_id: str, filename: str) -> None:
        local_path = self.file_path(job_id, filename)
        if not local_path.is_file():
            return
        self._client().upload_file(
            str(local_path),
            self.bucket,
            self._object_key(job_id, filename),
        )

    def resolve_download(self, job_id: str, filename: str) -> Path:
        local_path = self.file_path(job_id, filename)
        if local_path.is_file():
            return local_path

        key = self._object_key(job_id, filename)
        client = self._client()
        try:
            client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise FileNotFoundError(f"Artifact not found: {job_id}/{filename}") from exc

        local_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(self.bucket, key, str(local_path))
        return local_path

    def exists(self, job_id: str, filename: str) -> bool:
        if super().exists(job_id, filename):
            return True
        try:
            self._client().head_object(
                Bucket=self.bucket,
                Key=self._object_key(job_id, filename),
            )
            return True
        except Exception:
            return False
