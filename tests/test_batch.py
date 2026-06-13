"""Tests for batch job API."""

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


def test_batch_queues_summarize_jobs(fake_redis, monkeypatch):
    app = create_app()
    enqueued = 0

    def fake_summarize(**kwargs):
        nonlocal enqueued
        enqueued += 1

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_summarize_job", fake_summarize)

    with app.test_client() as client:
        response = client.post(
            "/v1/batch",
            json={
                "items": [
                    {
                        "operation": "summarize",
                        "text": "One sentence. Another sentence. Third sentence here.",
                        "sentences": 2,
                    },
                ]
            },
        )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["batch_id"]
    assert len(payload["items"]) == 1
    assert enqueued == 1

    from docintel.jobs.store import get_job

    batch_record = get_job(payload["batch_id"])
    assert batch_record is not None
    assert batch_record.job_type == JobType.BATCH
