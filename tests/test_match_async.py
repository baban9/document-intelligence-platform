"""Tests for async resume matching jobs."""

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


def test_match_async_returns_202(fake_redis, monkeypatch):
    app = create_app()

    def fake_enqueue(**kwargs):
        fake_enqueue.called_with = kwargs

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_match_job", fake_enqueue)

    with app.test_client() as client:
        response = client.post(
            "/v1/match/resume?async=true",
            json={
                "resume": "Python Flask developer with NLP experience.",
                "job_description": "Looking for a Python engineer with Flask and NLP skills.",
                "top_keywords": 10,
            },
        )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.MATCH_RESUME.value
    assert fake_enqueue.called_with is not None


def test_run_match_job_updates_status(fake_redis):
    from docintel.jobs.store import get_job
    from docintel.jobs.tasks import create_queued_job, run_match_resume_job

    job_id = "match-job"
    create_queued_job(job_id, job_type=JobType.MATCH_RESUME)

    run_match_resume_job(
        job_id=job_id,
        resume="Python Flask developer with NLP experience.",
        job_description="Looking for a Python engineer with Flask and NLP skills.",
        top_keywords=10,
    )

    record = get_job(job_id)
    assert record is not None
    assert record.status.value == "completed"
    assert record.result.get("score") is not None
