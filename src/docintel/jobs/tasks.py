"""Background worker tasks."""

from __future__ import annotations

from pathlib import Path

from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import get_job, save_job, update_job
from docintel.services.pdf.models import StructureMode
from docintel.services.pdf.structure import structure_pdf


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


def create_queued_job(job_id: str, *, callback_url: str | None = None) -> JobRecord:
    record = JobRecord(
        job_id=job_id,
        job_type=JobType.PDF_STRUCTURE,
        status=JobStatus.QUEUED,
        progress=0,
        progress_message="Queued",
        callback_url=callback_url,
    )
    save_job(record)
    return record
