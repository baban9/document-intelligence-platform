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


def enqueue_classify_job(job_id: str, text: str) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_classify_job",
        job_id=job_id,
        text=text,
        job_timeout=300,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_detect_pii_text_job(
    job_id: str,
    text: str,
    *,
    entities: list[str] | None = None,
    min_score: float = 0.35,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_detect_pii_text_job",
        job_id=job_id,
        text=text,
        entities=entities,
        min_score=min_score,
        job_timeout=300,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_document_process_job(
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    options: dict,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_document_process_job",
        job_id=job_id,
        input_path=input_path,
        filename=filename,
        content_type=content_type,
        options=options,
        job_timeout=900,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_document_process_text_job(
    job_id: str,
    text: str,
    options: dict,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_document_process_text_job",
        job_id=job_id,
        text=text,
        options=options,
        job_timeout=900,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_classify_document_job(
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_classify_document_job",
        job_id=job_id,
        input_path=input_path,
        filename=filename,
        content_type=content_type,
        job_timeout=600,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_summarize_document_job(
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    sentences: int,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_summarize_document_job",
        job_id=job_id,
        input_path=input_path,
        filename=filename,
        content_type=content_type,
        sentences=sentences,
        job_timeout=600,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_detect_pii_document_job(
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    *,
    entities: list[str] | None = None,
    min_score: float = 0.35,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_detect_pii_document_job",
        job_id=job_id,
        input_path=input_path,
        filename=filename,
        content_type=content_type,
        entities=entities,
        min_score=min_score,
        job_timeout=600,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_extract_text_job(
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_extract_text_job",
        job_id=job_id,
        input_path=input_path,
        filename=filename,
        content_type=content_type,
        job_timeout=600,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_s3_document_process_job(
    job_id: str,
    bucket: str,
    key: str,
    options: dict,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_s3_document_process_job",
        job_id=job_id,
        bucket=bucket,
        key=key,
        options=options,
        job_timeout=900,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def enqueue_compare_job(
    job_id: str,
    *,
    text_a: str | None = None,
    text_b: str | None = None,
    path_a: str | None = None,
    path_b: str | None = None,
    filename_a: str | None = None,
    filename_b: str | None = None,
    content_type_a: str | None = None,
    content_type_b: str | None = None,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "docintel.jobs.tasks.run_compare_job",
        job_id=job_id,
        text_a=text_a,
        text_b=text_b,
        path_a=path_a,
        path_b=path_b,
        filename_a=filename_a,
        filename_b=filename_b,
        content_type_a=content_type_a,
        content_type_b=content_type_b,
        job_timeout=600,
        result_ttl=DEFAULT_RESULT_TTL,
        failure_ttl=DEFAULT_FAILURE_TTL,
    )


def queue_depth() -> int | None:
    """Return RQ queue length when Redis is reachable."""
    try:
        return get_queue().count
    except Exception:
        return None
