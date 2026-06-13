"""Local filesystem storage for job artifacts."""

from __future__ import annotations

from pathlib import Path


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def job_dir(self, job_id: str) -> Path:
        path = self.base_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def file_path(self, job_id: str, filename: str) -> Path:
        return self.job_dir(job_id) / filename

    def sync_file(self, job_id: str, filename: str) -> None:
        """No-op for local storage."""

    def resolve_download(self, job_id: str, filename: str) -> Path:
        path = self.file_path(job_id, filename)
        if not path.is_file():
            raise FileNotFoundError(f"Artifact not found: {job_id}/{filename}")
        return path

    def exists(self, job_id: str, filename: str) -> bool:
        return self.file_path(job_id, filename).is_file()
