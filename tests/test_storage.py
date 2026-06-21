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


def test_tenant_scoped_job_dir(tmp_path: Path):
    storage = LocalStorage(str(tmp_path))
    path = storage.job_dir("job456", tenant_slug="acme-corp")
    assert path == tmp_path / "acme-corp" / "job456"
    assert path.is_dir()


def test_resolve_download_falls_back_to_legacy_flat_path(tmp_path: Path):
    storage = LocalStorage(str(tmp_path))
    legacy = tmp_path / "job789" / "out.pdf"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy")

    resolved = storage.resolve_download("job789", "out.pdf")
    assert resolved.read_bytes() == b"legacy"

