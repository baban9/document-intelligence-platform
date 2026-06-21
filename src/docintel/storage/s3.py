"""S3-compatible object storage for job artifacts."""

from __future__ import annotations

from pathlib import Path

from docintel.storage.local import LocalStorage
from docintel.storage.tenant_path import resolve_storage_tenant_slug


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

    def _object_keys(self, job_id: str, filename: str, tenant_slug: str | None = None) -> list[str]:
        slug = resolve_storage_tenant_slug(tenant_slug)
        keys = []
        if slug:
            keys.append(f"jobs/{slug}/{job_id}/{filename}")
        keys.append(f"jobs/{job_id}/{filename}")
        return keys

    def sync_file(self, job_id: str, filename: str, tenant_slug: str | None = None) -> None:
        local_path = self.file_path(job_id, filename, tenant_slug=tenant_slug)
        if not local_path.is_file():
            return
        client = self._client()
        for key in self._object_keys(job_id, filename, tenant_slug=tenant_slug):
            client.upload_file(str(local_path), self.bucket, key)

    def resolve_download(self, job_id: str, filename: str, tenant_slug: str | None = None) -> Path:
        try:
            return super().resolve_download(job_id, filename, tenant_slug=tenant_slug)
        except FileNotFoundError:
            pass

        client = self._client()
        for key in self._object_keys(job_id, filename, tenant_slug=tenant_slug):
            local_path = self.file_path(job_id, filename, tenant_slug=tenant_slug)
            try:
                client.head_object(Bucket=self.bucket, Key=key)
            except Exception:
                continue
            local_path.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(self.bucket, key, str(local_path))
            return local_path

        raise FileNotFoundError(f"Artifact not found: {job_id}/{filename}")

    def exists(self, job_id: str, filename: str, tenant_slug: str | None = None) -> bool:
        if super().exists(job_id, filename, tenant_slug=tenant_slug):
            return True
        client = self._client()
        for key in self._object_keys(job_id, filename, tenant_slug=tenant_slug):
            try:
                client.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                continue
        return False
