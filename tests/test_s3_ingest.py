"""Tests for S3 document ingest (M12)."""

from pathlib import Path

import pytest

from docintel.app import create_app
from docintel.jobs.models import JobType
from docintel.jobs.tasks import run_s3_document_process_job
from docintel.storage.s3_ingest import parse_s3_uri, resolve_s3_location


def test_parse_s3_uri():
    bucket, key = parse_s3_uri("s3://contracts/inbox/policy.docx")
    assert bucket == "contracts"
    assert key == "inbox/policy.docx"


def test_resolve_s3_location_from_bucket_and_key():
    bucket, key = resolve_s3_location(
        {"bucket": "contracts", "key": "inbox/policy.docx", "operation": "process"}
    )
    assert bucket == "contracts"
    assert key == "inbox/policy.docx"


@pytest.fixture
def fake_redis(monkeypatch):
    from docintel.jobs.store import reset_redis_client_cache

    import fakeredis

    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()


def test_ingest_route_queues_s3_process_job(fake_redis, monkeypatch):
    enqueued = {}

    def fake_enqueue(**kwargs):
        enqueued.update(kwargs)

    monkeypatch.setattr("docintel.jobs.store.ping_redis", lambda: True)
    monkeypatch.setattr("docintel.jobs.queue.enqueue_s3_document_process_job", fake_enqueue)

    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/v1/documents/ingest",
            json={
                "s3_uri": "s3://contracts/inbox/policy.docx",
                "operation": "process",
                "include_pii": False,
            },
        )

    payload = response.get_json()
    assert response.status_code == 202
    assert payload["job_type"] == JobType.DOCUMENT_S3_PROCESS.value
    assert enqueued["bucket"] == "contracts"
    assert enqueued["key"] == "inbox/policy.docx"


def test_run_s3_document_process_job(fake_redis, tmp_path: Path, monkeypatch):
    from docintel.jobs.models import JobRecord, JobStatus
    from docintel.jobs.store import save_job

    sample = tmp_path / "policy.txt"
    sample.write_text(
        "Master service agreement between the parties with liability clauses.",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "docintel.storage.s3_ingest.download_s3_object_to_job_dir",
        lambda job_id, bucket, key: (sample, "policy.txt"),
    )
    monkeypatch.setattr(
        "docintel.capabilities.pipeline.process.detect_pii_in_text",
        lambda *args, **kwargs: [],
    )

    job_id = "s3job01"
    save_job(
        JobRecord(
            job_id=job_id,
            job_type=JobType.DOCUMENT_S3_PROCESS,
            status=JobStatus.QUEUED,
        )
    )

    result = run_s3_document_process_job(
        job_id=job_id,
        bucket="contracts",
        key="inbox/policy.txt",
        options={"include_pii": False, "sentences": 2},
    )
    assert result["classification"]["category"] == "legal"
