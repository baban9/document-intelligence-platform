"""Background worker tasks."""

from __future__ import annotations

from pathlib import Path

from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import get_job, save_job, update_job
from docintel.services.pdf.models import Action, StructureMode
from docintel.services.pdf.annotator import annotate_pdf
from docintel.services.pdf.sensitive import detect_sensitive_pdf
from docintel.services.pdf.structure import structure_pdf
from docintel.services.matching import match_resume_to_job


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
        result = annotate_pdf(
            input_file=Path(input_path),
            output_file=Path(output_path),
            pattern=pattern,
            action=Action.from_value(action),
            pages=pages,
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


def run_match_resume_job(
    *,
    job_id: str,
    resume: str,
    job_description: str,
    top_keywords: int,
) -> dict:
    """Worker entrypoint: resume-to-job TF-IDF matching."""
    record = get_job(job_id)
    callback_url = record.callback_url if record else None

    update_job(
        job_id,
        job_status=JobStatus.RUNNING.value,
        progress=10,
        progress_message="Matching resume to job description",
    )

    try:
        result = match_resume_to_job(
            resume=resume,
            job_description=job_description,
            top_keywords=top_keywords,
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


def create_queued_job(
    job_id: str,
    *,
    job_type: JobType,
    callback_url: str | None = None,
) -> JobRecord:
    record = JobRecord(
        job_id=job_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        progress=0,
        progress_message="Queued",
        callback_url=callback_url,
    )
    save_job(record)
    return record
