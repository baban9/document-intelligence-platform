"""Background worker tasks."""

from __future__ import annotations

from pathlib import Path

from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import get_job, save_job, update_job
from docintel.services.pdf.models import Action, StructureMode
from docintel.services.pdf.annotator import annotate_pdf
from docintel.services.pdf.sensitive import detect_sensitive_pdf
from docintel.services.pdf.structure import structure_pdf
from docintel.services.summary import summarize_text


def _job_progress_callback(job_id: str):
    def _callback(*, stage: str, pages_done: int, pages_total: int, message: str) -> None:
        if pages_total <= 0:
            progress = 10
        elif stage == "rendering":
            progress = 95
        else:
            progress = 10 + int(80 * pages_done / pages_total)
        update_job(
            job_id,
            job_status=JobStatus.RUNNING.value,
            progress=progress,
            progress_message=message,
            pages_done=pages_done,
            pages_total=pages_total,
        )

    return _callback


def run_structure_pdf_job(
    *,
    job_id: str,
    input_path: str,
    output_path: str,
    mode: str,
    force_ocr: bool,
    output_filename: str,
    redact_before_llm: bool = False,
) -> dict:
    """Worker entrypoint: OCR + LLM structure, then update job metadata."""
    record = get_job(job_id)
    callback_url = record.callback_url if record else None

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=5,
        progress_message="Job started",
    )

    try:
        result = structure_pdf(
            input_file=Path(input_path),
            output_file=Path(output_path),
            mode=StructureMode.from_value(mode),
            force_ocr=force_ocr,
            redact_before_llm=redact_before_llm,
            progress_callback=_job_progress_callback(job_id),
        )
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    download_url = f"/v1/pdf/files/{job_id}/{output_filename}"
    result_payload = result.to_dict()
    _sync_artifact(job_id, output_filename)
    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        download_url=download_url,
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def _notify_webhook(callback_url: str | None, record: JobRecord) -> None:
    if not callback_url:
        return
    from docintel.jobs.webhooks import deliver_job_webhook

    deliver_job_webhook(callback_url, record.to_dict())


def _sync_artifact(job_id: str, filename: str) -> None:
    from docintel.storage import get_storage

    get_storage().sync_file(job_id, filename)


def run_detect_sensitive_pdf_job(
    *,
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
) -> dict:
    """Worker entrypoint: OCR + Presidio sensitive PDF detection."""
    record = get_job(job_id)
    callback_url = record.callback_url if record else None

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=5,
        progress_message="Sensitive detection started",
    )

    try:
        result = detect_sensitive_pdf(
            input_file=Path(input_path),
            output_file=Path(output_path),
            entities=entities,
            action=Action.from_value(action),
            force_ocr=force_ocr,
            add_text_layer=add_text_layer,
            pattern=pattern,
            min_score=min_score,
            progress_callback=_job_progress_callback(job_id),
        )
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    download_url = f"/v1/pdf/files/{job_id}/{output_filename}"
    result_payload = result.to_dict()
    _sync_artifact(job_id, output_filename)
    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        download_url=download_url,
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def run_annotate_pdf_job(
    *,
    job_id: str,
    input_path: str,
    output_path: str,
    output_filename: str,
    pattern: str,
    action: str,
    pages: list[int] | None = None,
    requirements: str | None = None,
) -> dict:
    """Worker entrypoint: regex PDF annotation."""
    record = get_job(job_id)
    callback_url = record.callback_url if record else None

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=5,
        progress_message="Annotation started",
    )

    try:
        if requirements and requirements.strip():
            from docintel.capabilities.pdf.pattern_planner import annotate_pdf_from_requirements

            update_job(
                job_id,
                job_status=JobStatus.RUNNING.value,
                progress=15,
                progress_message="Planning search patterns with LLM",
            )
            outcome = annotate_pdf_from_requirements(
                input_file=Path(input_path),
                output_file=Path(output_path),
                requirements=requirements.strip(),
                action=Action.from_value(action),
                pages=pages,
            )
            result_payload = outcome.to_dict()
        else:
            result = annotate_pdf(
                input_file=Path(input_path),
                output_file=Path(output_path),
                pattern=pattern,
                action=Action.from_value(action),
                pages=pages,
            )
            result_payload = result.to_dict()
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    download_url = f"/v1/pdf/files/{job_id}/{output_filename}"
    _sync_artifact(job_id, output_filename)
    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        download_url=download_url,
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def run_summarize_job(
    *,
    job_id: str,
    text: str,
    sentences: int,
) -> dict:
    """Worker entrypoint: extractive summarization."""
    record = get_job(job_id)
    callback_url = record.callback_url if record else None

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=10,
        progress_message="Summarizing text",
    )

    try:
        result = summarize_text(text, sentence_count=sentences)
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    result_payload = result.to_dict()
    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def run_classify_job(*, job_id: str, text: str) -> dict:
    from docintel.capabilities.understanding.classify import classify_text

    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Classifying text",
    )
    try:
        result_payload = classify_text(text).to_dict()
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def run_detect_pii_text_job(
    *,
    job_id: str,
    text: str,
    entities: list[str] | None = None,
    min_score: float = 0.35,
) -> dict:
    from docintel.services.pdf.pii import detect_pii_in_text

    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Detecting PII",
    )
    try:
        hits = detect_pii_in_text(text, entities=entities, min_score=min_score)
        findings = [hit.to_dict() for hit in hits]
        result_payload = {"finding_count": len(findings), "findings": findings}
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def run_document_process_job(
    *,
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    options: dict,
) -> dict:
    from docintel.capabilities.pipeline import ProcessOptions, process_document

    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=10,
        progress_message="Processing document",
    )
    try:
        result = process_document(
            input_path,
            filename=filename,
            content_type=content_type,
            options=ProcessOptions.from_dict(options),
        )
        result_payload = result.to_dict()
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def run_document_process_text_job(*, job_id: str, text: str, options: dict) -> dict:
    from docintel.capabilities.pipeline import ProcessOptions, process_text

    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=10,
        progress_message="Processing text",
    )
    try:
        result = process_text(text, options=ProcessOptions.from_dict(options))
        result_payload = result.to_dict()
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def _extract_upload_text(
    input_path: str,
    *,
    filename: str,
    content_type: str | None,
) -> str:
    from docintel.capabilities.extraction.formats import extract_document_text, identify_document

    path = Path(input_path)
    identification = identify_document(path, filename=filename, content_type=content_type)
    extraction = extract_document_text(
        path,
        filename=filename,
        content_type=content_type,
        identification=identification,
    )
    return extraction.text


def _complete_text_job(
    *,
    job_id: str,
    progress_message: str,
    result_payload: dict,
) -> dict:
    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    completed = update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        progress_message="Job completed",
        result=result_payload,
    )
    _notify_webhook(callback_url, completed)
    return result_payload


def _fail_text_job(*, job_id: str, exc: Exception) -> None:
    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    failed = update_job(
        job_id,
        job_status=JobStatus.FAILED.value,
        progress=100,
        progress_message="Job failed",
        error=str(exc),
    )
    _notify_webhook(callback_url, failed)


def run_classify_document_job(
    *,
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
) -> dict:
    from docintel.capabilities.understanding.classify import classify_text

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Classifying document",
    )
    try:
        text = _extract_upload_text(input_path, filename=filename, content_type=content_type)
        result_payload = classify_text(text).to_dict()
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_summarize_document_job(
    *,
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    sentences: int,
) -> dict:
    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Summarizing document",
    )
    try:
        text = _extract_upload_text(input_path, filename=filename, content_type=content_type)
        result_payload = summarize_text(text, sentence_count=sentences).to_dict()
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_detect_pii_document_job(
    *,
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    entities: list[str] | None = None,
    min_score: float = 0.35,
) -> dict:
    from docintel.services.pdf.pii import detect_pii_in_text

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Detecting PII in document",
    )
    try:
        text = _extract_upload_text(input_path, filename=filename, content_type=content_type)
        hits = detect_pii_in_text(text, entities=entities, min_score=min_score)
        findings = [hit.to_dict() for hit in hits]
        result_payload = {"finding_count": len(findings), "findings": findings}
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_integrity_text_job(
    *,
    job_id: str,
    text: str,
    checks: list[str] | None = None,
) -> dict:
    from docintel.services.integrity import analyze_document_integrity

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Analyzing document integrity",
    )
    try:
        result_payload = analyze_document_integrity(text, checks=checks).to_dict()
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_integrity_document_job(
    *,
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
    checks: list[str] | None = None,
) -> dict:
    from docintel.services.integrity import analyze_document_integrity

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Analyzing document integrity",
    )
    try:
        text = _extract_upload_text(input_path, filename=filename, content_type=content_type)
        result_payload = analyze_document_integrity(text, checks=checks).to_dict()
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_extract_text_job(
    *,
    job_id: str,
    input_path: str,
    filename: str,
    content_type: str | None,
) -> dict:
    from docintel.capabilities.extraction.formats import extract_document_text, identify_document

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Extracting text",
    )
    try:
        path = Path(input_path)
        identification = identify_document(path, filename=filename, content_type=content_type)
        extraction = extract_document_text(
            path,
            filename=filename,
            content_type=content_type,
            identification=identification,
        )
        result_payload = {"filename": filename, **extraction.to_dict()}
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_compare_job(
    *,
    job_id: str,
    text_a: str | None = None,
    text_b: str | None = None,
    path_a: str | None = None,
    path_b: str | None = None,
    filename_a: str | None = None,
    filename_b: str | None = None,
    content_type_a: str | None = None,
    content_type_b: str | None = None,
) -> dict:
    from docintel.capabilities.understanding.compare import compare_texts

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=20,
        progress_message="Comparing documents",
    )
    try:
        resolved_a = text_a
        resolved_b = text_b
        if path_a:
            resolved_a = _extract_upload_text(
                path_a,
                filename=filename_a or Path(path_a).name,
                content_type=content_type_a,
            )
        if path_b:
            resolved_b = _extract_upload_text(
                path_b,
                filename=filename_b or Path(path_b).name,
                content_type=content_type_b,
            )
        if not resolved_a or not resolved_b:
            raise ValueError("Both documents are required for comparison.")
        result_payload = compare_texts(resolved_a, resolved_b).to_dict()
    except Exception as exc:
        _fail_text_job(job_id=job_id, exc=exc)
        raise
    return _complete_text_job(
        job_id=job_id,
        progress_message="Job completed",
        result_payload=result_payload,
    )


def run_s3_document_process_job(
    *,
    job_id: str,
    bucket: str,
    key: str,
    options: dict,
) -> dict:
    from docintel.storage.s3_ingest import download_s3_object_to_job_dir

    record = get_job(job_id)
    callback_url = record.callback_url if record else None
    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=5,
        progress_message="Downloading from S3",
    )
    try:
        input_path, filename = download_s3_object_to_job_dir(job_id, bucket, key)
    except Exception as exc:
        failed = update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            progress_message="Job failed",
            error=str(exc),
        )
        _notify_webhook(callback_url, failed)
        raise

    return run_document_process_job(
        job_id=job_id,
        input_path=str(input_path),
        filename=filename,
        content_type=None,
        options=options,
    )


def create_queued_job(
    job_id: str,
    *,
    job_type: JobType,
    callback_url: str | None = None,
    tenant_slug: str | None = None,
) -> JobRecord:
    record = JobRecord(
        job_id=job_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        progress=0,
        progress_message="Queued",
        callback_url=callback_url,
        tenant_slug=tenant_slug,
    )
    save_job(record)
    return record


def _wrap_worker_jobs() -> None:
    from docintel.tenants.worker import bind_tenant_job

    for name, value in list(globals().items()):
        if name.startswith("run_") and callable(value) and not getattr(value, "__tenant_wrapped__", False):
            wrapped = bind_tenant_job(value)
            wrapped.__tenant_wrapped__ = True  # type: ignore[attr-defined]
            globals()[name] = wrapped


_wrap_worker_jobs()
