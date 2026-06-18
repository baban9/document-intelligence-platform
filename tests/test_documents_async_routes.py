"""Tests for async document workflow routes."""

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


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    path = tmp_path / "contract.txt"
    path.write_text(
        "Master service agreement between the parties. "
        "This contract defines jurisdiction and liability clauses.",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("endpoint", "job_type", "enqueue_attr"),
    [
        ("/v1/documents/classify", JobType.DOCUMENT_CLASSIFY, "enqueue_classify_document_job"),
        ("/v1/documents/summarize", JobType.DOCUMENT_SUMMARIZE, "enqueue_summarize_document_job"),
        ("/v1/documents/extract-text", JobType.DOCUMENT_EXTRACT_TEXT, "enqueue_extract_text_job"),
    ],
)
def test_document_routes_queue_file_jobs(
    fake_redis,
    sample_txt: Path,
    monkeypatch,
    endpoint: str,
    job_type: JobType,
    enqueue_attr: str,
):
    enqueued = {}

    def fake_enqueue(**kwargs):
        enqueued.update(kwargs)

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr(f"docintel.jobs.queue.{enqueue_attr}", fake_enqueue)

    app = create_app()
    with app.test_client() as client:
        with sample_txt.open("rb") as handle:
            response = client.post(
                f"{endpoint}?async=true",
                data={"file": (handle, "contract.txt")},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == job_type.value
    assert enqueued["filename"] == "contract.txt"


def test_classify_text_async_queues_job(fake_redis, monkeypatch):
    enqueued = {}

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr(
        "docintel.jobs.queue.enqueue_classify_job",
        lambda **kwargs: enqueued.update(kwargs),
    )

    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/v1/documents/classify?async=true",
            json={"text": "Quarterly earnings report for investors."},
        )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.TEXT_CLASSIFY.value
    assert "earnings" in enqueued["text"]


def test_text_summarize_async_queues_job(fake_redis, monkeypatch):
    enqueued = {}

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr(
        "docintel.jobs.queue.enqueue_summarize_job",
        lambda **kwargs: enqueued.update(kwargs),
    )

    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/v1/text/summarize?async=true",
            json={"text": "One sentence. Another sentence. Third sentence.", "sentences": 2},
        )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.TEXT_SUMMARIZE.value
    assert enqueued["sentences"] == 2
