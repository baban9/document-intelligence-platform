"""Background worker tasks."""

from __future__ import annotations

from pathlib import Path

from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import save_job, update_job
from docintel.services.pdf.models import StructureMode
from docintel.services.pdf.structure import structure_pdf


def run_structure_pdf_job(
    *,
    job_id: str,
    input_path: str,
    output_path: str,
    mode: str,
    force_ocr: bool,
    output_filename: str,
) -> dict:
    """Worker entrypoint: OCR + LLM structure, then update job metadata."""
    update_job(job_id, job_status=JobStatus.RUNNING.value, progress=10)

    try:
        result = structure_pdf(
            input_file=Path(input_path),
            output_file=Path(output_path),
            mode=StructureMode.from_value(mode),
            force_ocr=force_ocr,
        )
    except Exception as exc:
        update_job(
            job_id,
            job_status=JobStatus.FAILED.value,
            progress=100,
            error=str(exc),
        )
        raise

    download_url = f"/v1/pdf/files/{job_id}/{output_filename}"
    result_payload = result.to_dict()
    update_job(
        job_id,
        job_status=JobStatus.COMPLETED.value,
        progress=100,
        download_url=download_url,
        result=result_payload,
    )
    return result_payload


def create_queued_job(job_id: str) -> JobRecord:
    record = JobRecord(
        job_id=job_id,
        job_type=JobType.PDF_STRUCTURE,
        status=JobStatus.QUEUED,
        progress=0,
    )
    save_job(record)
    return record
