"""Restore tenant context inside background workers."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from typing import Callable, Iterator, TypeVar

from docintel.jobs.store import get_job
from docintel.tenants.context import resolve_tenant_context, set_tenant_context

F = TypeVar("F", bound=Callable)


@contextmanager
def tenant_job_context(tenant_slug: str | None) -> Iterator[None]:
    """Bind Presidio/LLM tenant settings for the duration of a worker job."""
    if not tenant_slug:
        yield
        return

    context = resolve_tenant_context(tenant_slug)
    if context is None:
        yield
        return

    set_tenant_context(context)
    try:
        yield
    finally:
        set_tenant_context(None)


def bind_tenant_job(func: F) -> F:
    """Decorator for RQ worker entrypoints: apply tenant settings from the job record."""

    @wraps(func)
    def wrapper(**kwargs):
        tenant_slug = kwargs.pop("tenant_slug", None)
        job_id = kwargs.get("job_id")
        if tenant_slug is None and job_id:
            record = get_job(job_id)
            tenant_slug = record.tenant_slug if record else None
        with tenant_job_context(tenant_slug):
            return func(**kwargs)

    return wrapper  # type: ignore[return-value]
