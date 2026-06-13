"""Job artifact storage backends."""

from __future__ import annotations

import os


def _base_dir(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    try:
        from flask import current_app

        return str(current_app.config.get("UPLOAD_DIR", "uploads"))
    except RuntimeError:
        return os.getenv("DOCINTEL_UPLOAD_DIR", "uploads")


def get_storage(base_dir: str | None = None):
    backend = os.getenv("DOCINTEL_STORAGE_BACKEND", "local").strip().lower()
    root = _base_dir(base_dir)
    if backend == "s3":
        from docintel.storage.s3 import S3Storage

        return S3Storage(
            base_dir=root,
            bucket=os.getenv("DOCINTEL_S3_BUCKET", ""),
            region=os.getenv("DOCINTEL_S3_REGION", "us-east-1"),
            endpoint_url=os.getenv("DOCINTEL_S3_ENDPOINT_URL", "") or None,
        )
    from docintel.storage.local import LocalStorage

    return LocalStorage(base_dir=root)
