"""Tests for job artifact storage."""

from pathlib import Path

from docintel.storage.local import LocalStorage


def test_local_storage_save_and_resolve(tmp_path: Path):
    storage = LocalStorage(str(tmp_path))
    job_id = "job123"
    dest = storage.file_path(job_id, "out.pdf")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"%PDF-1.4")

    resolved = storage.resolve_download(job_id, "out.pdf")
    assert resolved.read_bytes() == b"%PDF-1.4"
    assert storage.exists(job_id, "out.pdf")
