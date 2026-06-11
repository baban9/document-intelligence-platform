"""Tests for async detect-sensitive jobs."""

from pathlib import Path

import fakeredis
import pytest

from docintel.app import create_app
from docintel.jobs.models import JobType
from docintel.services.pdf.models import Action
from docintel.services.pdf.pii import PIIHit


@pytest.fixture
def fake_redis(monkeypatch):
    from docintel.jobs.store import reset_redis_client_cache

    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()


def test_detect_sensitive_async_returns_202(
    sample_pdf: Path, tmp_path: Path, fake_redis, monkeypatch
):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    def fake_enqueue(**kwargs):
        fake_enqueue.called_with = kwargs

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_detect_sensitive_job", fake_enqueue)

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/detect-sensitive?async=true",
                data={"file": (handle, "sample.pdf"), "action": "Highlight"},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.PDF_DETECT_SENSITIVE.value
    assert fake_enqueue.called_with is not None


def test_run_detect_sensitive_job_updates_status(
    sample_pdf: Path, tmp_path: Path, fake_redis, monkeypatch
):
    from docintel.jobs.store import get_job
    from docintel.jobs.tasks import create_queued_job, run_detect_sensitive_pdf_job

    def fake_detect(text, entities=None, language="en", min_score=0.35):
        if "ABC123" in text:
            start = text.index("ABC123")
            return [
                PIIHit(
                    entity_type="US_SSN",
                    text="ABC123",
                    start=start,
                    end=start + 6,
                    score=0.99,
                )
            ]
        return []

    monkeypatch.setattr("docintel.services.pdf.sensitive.detect_pii_in_text", fake_detect)
    monkeypatch.setattr("docintel.services.pdf.sensitive._ensure_ocr_stack", lambda: None)

    job_id = "sensitive-job"
    work_dir = tmp_path / "uploads" / job_id
    work_dir.mkdir(parents=True)
    input_path = work_dir / "sample.pdf"
    output_path = work_dir / "sensitive_sample.pdf"
    input_path.write_bytes(sample_pdf.read_bytes())
    create_queued_job(job_id, job_type=JobType.PDF_DETECT_SENSITIVE)

    run_detect_sensitive_pdf_job(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        output_filename=output_path.name,
        action=Action.HIGHLIGHT.value,
        force_ocr=False,
        add_text_layer=False,
        min_score=0.35,
    )

    record = get_job(job_id)
    assert record is not None
    assert record.status.value == "completed"
    assert output_path.is_file()
