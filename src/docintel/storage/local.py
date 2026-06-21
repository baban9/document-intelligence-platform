"""Local filesystem storage for job artifacts."""

from __future__ import annotations

from pathlib import Path

from docintel.storage.tenant_path import resolve_storage_tenant_slug


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def _job_roots(self, job_id: str, tenant_slug: str | None = None) -> list[Path]:
        slug = resolve_storage_tenant_slug(tenant_slug)
        roots: list[Path] = []
        if slug:
            roots.append(self.base_dir / slug / job_id)
        roots.append(self.base_dir / job_id)
        return roots

    def job_dir(self, job_id: str, tenant_slug: str | None = None) -> Path:
        roots = self._job_roots(job_id, tenant_slug)
        path = roots[0]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def file_path(self, job_id: str, filename: str, tenant_slug: str | None = None) -> Path:
        return self.job_dir(job_id, tenant_slug=tenant_slug) / filename

    def sync_file(self, job_id: str, filename: str, tenant_slug: str | None = None) -> None:
        """No-op for local storage."""

    def resolve_download(self, job_id: str, filename: str, tenant_slug: str | None = None) -> Path:
        for root in self._job_roots(job_id, tenant_slug):
            path = root / filename
            if path.is_file():
                return path

        from docintel.jobs.store import get_job

        record = get_job(job_id)
        if record and record.tenant_slug:
            legacy = self.base_dir / record.tenant_slug / job_id / filename
            if legacy.is_file():
                return legacy

        raise FileNotFoundError(f"Artifact not found: {job_id}/{filename}")

    def exists(self, job_id: str, filename: str, tenant_slug: str | None = None) -> bool:
        try:
            self.resolve_download(job_id, filename, tenant_slug=tenant_slug)
            return True
        except FileNotFoundError:
            return False
