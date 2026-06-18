"""Tests for configurable job metadata retention."""

import pytest

from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import get_job, job_ttl_seconds, reset_redis_client_cache, save_job


@pytest.fixture
def fake_redis(monkeypatch):
    import fakeredis

    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()


def test_job_ttl_seconds_reads_env(monkeypatch):
    monkeypatch.setenv("DOCINTEL_JOB_TTL_SECONDS", "3600")
    reset_redis_client_cache()
    assert job_ttl_seconds() == 3600


def test_save_job_uses_configured_ttl(fake_redis, monkeypatch):
    monkeypatch.setenv("DOCINTEL_JOB_TTL_SECONDS", "120")
    reset_redis_client_cache()

    save_job(
        JobRecord(
            job_id="ttljob01",
            job_type=JobType.TEXT_CLASSIFY,
            status=JobStatus.QUEUED,
        )
    )

    ttl = fake_redis.ttl("docintel:job:ttljob01")
    assert 0 < ttl <= 120
    assert get_job("ttljob01") is not None
