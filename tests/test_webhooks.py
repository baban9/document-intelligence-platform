"""Tests for job progress and webhooks."""

from pathlib import Path
from unittest.mock import MagicMock

import fakeredis
import pytest

from docintel.jobs.models import JobStatus, JobType
from docintel.jobs.models import JobRecord
from docintel.jobs.store import get_job, reset_redis_client_cache, save_job
from docintel.jobs.tasks import create_queued_job, run_structure_pdf_job
from docintel.jobs.webhooks import deliver_job_webhook
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


def test_deliver_job_webhook_posts_payload(monkeypatch):
    mock_post = MagicMock()
    mock_response = MagicMock()
    mock_response.ok = True
    mock_post.return_value = mock_response
    monkeypatch.setattr("requests.post", mock_post)

    ok = deliver_job_webhook(
        "https://example.com/hook",
        {"job_id": "abc", "job_status": "completed"},
    )
    assert ok is True
    mock_post.assert_called_once()


def test_run_structure_job_updates_progress(
    sample_pdf: Path, tmp_path: Path, fake_redis, monkeypatch
):
    from docintel.services.pdf import structure as structure_module

    job_id = "progress-job"
    work_dir = tmp_path / "uploads" / job_id
    work_dir.mkdir(parents=True)
    input_path = work_dir / "sample.pdf"
    output_path = work_dir / "structured_sample.pdf"
    input_path.write_bytes(sample_pdf.read_bytes())
    create_queued_job(job_id, callback_url="https://example.com/hook")

    def fake_structure(page_texts, progress_callback=None):
        pages = [
            StructuredPage(
                page_index=0,
                title="Invoice",
                sections=[
                    SectionBlock(
                        heading="Details",
                        level=1,
                        paragraphs=[page_texts[0][1]],
                        list_items=[],
                        tables=[],
                    )
                ],
                plain_text=page_texts[0][1],
            )
        ]
        return StructuredDocument.from_pages(pages)

    monkeypatch.setattr(structure_module, "structure_document", fake_structure)
    webhook = MagicMock(return_value=True)
    monkeypatch.setattr("docintel.jobs.webhooks.deliver_job_webhook", webhook)

    run_structure_pdf_job(
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
    assert record.progress == 100
    assert record.progress_message == "Job completed"
    webhook.assert_called_once()
