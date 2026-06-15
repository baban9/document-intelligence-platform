"""Tests for async document process jobs."""

from pathlib import Path

import pytest

from docintel.app import create_app
from docintel.jobs.models import JobType
from docintel.jobs.tasks import run_document_process_job


@pytest.fixture
def fake_redis(monkeypatch):
    from docintel.jobs.store import reset_redis_client_cache

    import fakeredis

    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    path = tmp_path / "contract.txt"
    path.write_text(
        "Master service agreement between the parties. "
        "This contract defines jurisdiction and liability clauses.",
        encoding="utf-8",
    )
    return path


def test_process_async_queues_job(fake_redis, sample_txt: Path, monkeypatch):
    enqueued = {}

    def fake_enqueue(**kwargs):
        enqueued.update(kwargs)

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_document_process_job", fake_enqueue)

    app = create_app()
    with app.test_client() as client:
        with sample_txt.open("rb") as handle:
            response = client.post(
                "/v1/documents/process?async=true",
                data={"file": (handle, "contract.txt"), "include_pii": "false"},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.DOCUMENT_PROCESS.value
    assert enqueued["filename"] == "contract.txt"


def test_run_document_process_job(fake_redis, sample_txt: Path):
    from docintel.jobs.store import save_job
    from docintel.jobs.models import JobRecord, JobStatus

    job_id = "jobproc01"
    save_job(
        JobRecord(
            job_id=job_id,
            job_type=JobType.DOCUMENT_PROCESS,
            status=JobStatus.QUEUED,
        )
    )

    result = run_document_process_job(
        job_id=job_id,
        input_path=str(sample_txt),
        filename="contract.txt",
        content_type="text/plain",
        options={"include_pii": False, "sentences": 2},
    )
    assert result["classification"]["category"] == "legal"
    assert result["summary"]["sentence_count"] == 2
