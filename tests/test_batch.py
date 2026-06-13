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


def test_batch_queues_match_and_summarize(fake_redis, monkeypatch):
    app = create_app()
    enqueued = {"match": 0, "summarize": 0}

    def fake_match(**kwargs):
        enqueued["match"] += 1

    def fake_summarize(**kwargs):
        enqueued["summarize"] += 1

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_match_job", fake_match)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_summarize_job", fake_summarize)

    with app.test_client() as client:
        response = client.post(
            "/v1/batch",
            json={
                "items": [
                    {
                        "operation": "match_resume",
                        "resume": "Python Flask developer",
                        "job_description": "Python engineer with Flask",
                    },
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
    assert len(payload["items"]) == 2
    assert enqueued["match"] == 1
    assert enqueued["summarize"] == 1

    from docintel.jobs.store import get_job

    batch_record = get_job(payload["batch_id"])
    assert batch_record is not None
    assert batch_record.job_type == JobType.BATCH
