"""Tests for tenant slug propagation in async jobs."""

import pytest

from docintel.jobs.models import JobStatus, JobType
from docintel.jobs.store import get_job
from docintel.jobs.tasks import create_queued_job, run_detect_pii_text_job
from docintel.tenants.context import get_tenant_context


def test_create_queued_job_persists_tenant_slug(fake_redis):
    create_queued_job(
        "job-tenant-1",
        job_type=JobType.TEXT_DETECT_PII,
        tenant_slug="finance-hub",
    )
    record = get_job("job-tenant-1")
    assert record is not None
    assert record.tenant_slug == "finance-hub"


@pytest.mark.usefixtures("postgres_env")
def test_worker_job_restores_tenant_context(fake_redis, monkeypatch):
    from docintel.capabilities.compliance import pii as pii_module
    from docintel.db.init import init_database
    from docintel.db.tenants import update_tenant_settings

    init_database()
    update_tenant_settings(
        "finance-hub",
        llm_provider="ollama",
        llm_model="llama3.2",
        llm_base_url="http://ollama:11434/v1",
        llm_api_key=None,
        pii_entities=["EMAIL_ADDRESS"],
    )

    tenant_slugs_during_resolve: list[str | None] = []
    original_resolve = pii_module.resolve_pii_entities

    def tracking_resolve(entities=None):
        ctx = get_tenant_context()
        tenant_slugs_during_resolve.append(ctx.slug if ctx else None)
        return original_resolve(entities)

    class _FakeAnalyzer:
        def analyze(self, **kwargs):
            return []

    monkeypatch.setattr(pii_module, "resolve_pii_entities", tracking_resolve)
    monkeypatch.setattr(pii_module, "_analyzer_engine", lambda: _FakeAnalyzer())

    create_queued_job(
        "job-tenant-2",
        job_type=JobType.TEXT_DETECT_PII,
        tenant_slug="finance-hub",
    )

    result = run_detect_pii_text_job(
        job_id="job-tenant-2",
        text="Contact jane@example.com",
        tenant_slug="finance-hub",
    )

    assert result["finding_count"] == 0
    assert tenant_slugs_during_resolve == ["finance-hub"]
    assert get_tenant_context() is None
