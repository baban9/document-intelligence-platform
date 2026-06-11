"""Tests for async job queue and status API."""

from pathlib import Path

import fakeredis
import pytest

from docintel.app import create_app
from docintel.jobs.models import JobStatus, JobType
from docintel.jobs.store import get_job, reset_redis_client_cache, save_job
from docintel.jobs.models import JobRecord
from docintel.jobs.tasks import create_queued_job, run_structure_pdf_job
from docintel.services.pdf.structure_schema import (
    SectionBlock,
    StructuredDocument,
    StructuredPage,
)


@pytest.fixture
def fake_redis(monkeypatch):
    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()


def test_job_record_roundtrip():
    record = JobRecord(
        job_id="abc123",
        job_type=JobType.PDF_STRUCTURE,
        status=JobStatus.QUEUED,
        progress=0,
    )
    restored = JobRecord.from_dict(record.to_dict())
    assert restored.job_id == "abc123"
    assert restored.status == JobStatus.QUEUED


def test_save_and_get_job(fake_redis):
    record = create_queued_job("job001", job_type=JobType.PDF_STRUCTURE)
    loaded = get_job("job001")
    assert loaded is not None
    assert loaded.status == JobStatus.QUEUED


def test_get_job_status_endpoint(fake_redis):
    app = create_app()
    save_job(
        JobRecord(
            job_id="job002",
            job_type=JobType.PDF_STRUCTURE,
            status=JobStatus.COMPLETED,
            progress=100,
            download_url="/v1/pdf/files/job002/out.pdf",
        )
    )

    with app.test_client() as client:
        response = client.get("/v1/jobs/job002")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["job_status"] == "completed"
    assert payload["download_url"] == "/v1/pdf/files/job002/out.pdf"


def test_structure_async_returns_202(sample_pdf: Path, tmp_path: Path, fake_redis, monkeypatch):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    def fake_enqueue(**kwargs):
        fake_enqueue.called_with = kwargs

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_structure_job", fake_enqueue)

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/structure?async=true",
                data={"file": (handle, "sample.pdf"), "mode": "curate"},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_status"] == "queued"
    assert "poll_url" in payload
    assert fake_enqueue.called_with is not None


def _fake_structure(page_texts, progress_callback=None):
    pages = []
    for page_index, text in page_texts:
        pages.append(
            StructuredPage(
                page_index=page_index,
                title="Invoice",
                sections=[
                    SectionBlock(
                        heading="Details",
                        level=1,
                        paragraphs=[text.strip()],
                        list_items=[],
                        tables=[],
                    )
                ],
                plain_text=text.strip(),
            )
        )
    return StructuredDocument.from_pages(pages)


def test_run_structure_pdf_job_updates_status(
    sample_pdf: Path, tmp_path: Path, fake_redis, monkeypatch
):
    from docintel.services.pdf import structure as structure_module

    job_id = "workerjob"
    work_dir = tmp_path / "uploads" / job_id
    work_dir.mkdir(parents=True)
    input_path = work_dir / "sample.pdf"
    output_path = work_dir / "structured_sample.pdf"
    input_path.write_bytes(sample_pdf.read_bytes())
    create_queued_job(job_id, job_type=JobType.PDF_STRUCTURE)

    monkeypatch.setattr(structure_module, "structure_document", _fake_structure)

    result = run_structure_pdf_job(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        mode="curate",
        force_ocr=False,
        output_filename=output_path.name,
    )

    record = get_job(job_id)
    assert record is not None
    assert record.status == JobStatus.COMPLETED
    assert record.download_url == f"/v1/pdf/files/{job_id}/{output_path.name}"
    assert result["document_title"] == "Invoice"
    assert output_path.is_file()
