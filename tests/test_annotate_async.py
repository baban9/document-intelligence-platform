"""Tests for async PDF annotate jobs."""

from pathlib import Path

import pytest

from docintel.app import create_app
from docintel.jobs.models import JobType


@pytest.fixture
def fake_redis(monkeypatch):
    from docintel.jobs.store import reset_redis_client_cache

    import fakeredis

    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()


def test_annotate_async_returns_202(sample_pdf: Path, tmp_path: Path, fake_redis, monkeypatch):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    def fake_enqueue(**kwargs):
        fake_enqueue.called_with = kwargs

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_annotate_job", fake_enqueue)

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/annotate?async=true",
                data={
                    "file": (handle, "sample.pdf"),
                    "pattern": "ABC123",
                    "action": "Highlight",
                },
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.PDF_ANNOTATE.value
    assert fake_enqueue.called_with is not None


def test_run_annotate_job_updates_status(sample_pdf: Path, tmp_path: Path, fake_redis):
    from docintel.jobs.store import get_job
    from docintel.jobs.tasks import create_queued_job, run_annotate_pdf_job

    job_id = "annotate-job"
    work_dir = tmp_path / "uploads" / job_id
    work_dir.mkdir(parents=True)
    input_path = work_dir / "sample.pdf"
    output_path = work_dir / "annotated_sample.pdf"
    input_path.write_bytes(sample_pdf.read_bytes())
    create_queued_job(job_id, job_type=JobType.PDF_ANNOTATE)

    run_annotate_pdf_job(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        output_filename=output_path.name,
        pattern="ABC123",
        action="Highlight",
    )

    record = get_job(job_id)
    assert record is not None
    assert record.status.value == "completed"
    assert output_path.is_file()
