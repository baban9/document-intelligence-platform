"""RQ queue helpers."""

from __future__ import annotations

import os

from docintel.jobs.store import redis_url

QUEUE_NAME = os.getenv("DOCINTEL_QUEUE_NAME", "docintel")
DEFAULT_RESULT_TTL = 60 * 60 * 24
DEFAULT_FAILURE_TTL = 60 * 60 * 24


def get_queue():
    from redis import Redis
    from rq import Queue

    connection = Redis.from_url(redis_url())
    return Queue(QUEUE_NAME, connection=connection)


def enqueue_structure_job(
    job_id: str,
    input_path: str,
    output_path: str,
    mode: str,
    force_ocr: bool,
    output_filename: str,
    redact_before_llm: bool = False,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_structure_pdf_job",
        job_id=job_id,
        input_path=input_path,
        output_path=output_path,
        mode=mode,
        force_ocr=force_ocr,
        output_filename=output_filename,
        redact_before_llm=redact_before_llm,
        job_timeout=1800,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_detect_sensitive_job(
    job_id: str,
    input_path: str,
    output_path: str,
    output_filename: str,
    action: str,
    force_ocr: bool,
    add_text_layer: bool,
    min_score: float,
    entities: list[str] | None = None,
    pattern: str | None = None,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_detect_sensitive_pdf_job",
        job_id=job_id,
        input_path=input_path,
        output_path=output_path,
        output_filename=output_filename,
        action=action,
        force_ocr=force_ocr,
        add_text_layer=add_text_layer,
        min_score=min_score,
        entities=entities,
        pattern=pattern,
        job_timeout=1800,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_annotate_job(
    job_id: str,
    input_path: str,
    output_path: str,
    output_filename: str,
    pattern: str,
    action: str,
    pages: list[int] | None = None,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_annotate_pdf_job",
        job_id=job_id,
        input_path=input_path,
        output_path=output_path,
        output_filename=output_filename,
        pattern=pattern,
        action=action,
        pages=pages,
        job_timeout=600,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_summarize_job(
    job_id: str,
    text: str,
    sentences: int,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_summarize_job",
        job_id=job_id,
        text=text,
        sentences=sentences,
        job_timeout=300,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def queue_depth() -> int | None:
    """Return RQ queue length when Redis is reachable."""
    try:
        return get_queue().count
    except Exception:
        return None
