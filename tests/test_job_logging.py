"""Tests for structured job processing logs."""

import json
import logging

from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.ops.job_logging import emit_job_store_log, reset_job_logging_state_for_tests
from docintel.ops.logging import JsonFormatter


def _capture_job_logs():
    handler = logging.Handler()
    records: list[logging.LogRecord] = []
    handler.emit = records.append  # type: ignore[method-assign]
    job_logger = logging.getLogger("docintel.job")
    previous_level = job_logger.level
    job_logger.setLevel(logging.INFO)
    job_logger.addHandler(handler)
    return handler, records, job_logger, previous_level


def _cleanup_logger(handler, job_logger, previous_level):
    job_logger.removeHandler(handler)
    job_logger.setLevel(previous_level)


def test_emit_job_store_log_completed_includes_duration_and_summary():
    reset_job_logging_state_for_tests()
    handler, records, job_logger, previous_level = _capture_job_logs()
    try:
        queued = JobRecord(
            job_id="job-1",
            job_type=JobType.DOCUMENT_PROCESS,
            status=JobStatus.QUEUED,
            progress=0,
            progress_message="Queued",
        )
        running = JobRecord(
            job_id="job-1",
            job_type=JobType.DOCUMENT_PROCESS,
            status=JobStatus.RUNNING,
            progress=10,
            progress_message="Processing document",
        )
        completed = JobRecord(
            job_id="job-1",
            job_type=JobType.DOCUMENT_PROCESS,
            status=JobStatus.COMPLETED,
            progress=100,
            progress_message="Job completed",
            result={
                "filename": "policy.pdf",
                "classification": {"category": "legal"},
                "pii": {"finding_count": 3},
            },
        )

        emit_job_store_log(None, queued, {})
        emit_job_store_log(queued, running, {"job_status": JobStatus.RUNNING.value})
        emit_job_store_log(
            running,
            completed,
            {"job_status": JobStatus.COMPLETED.value, "progress": 100},
        )

        assert len(records) == 3
        payload = json.loads(JsonFormatter().format(records[-1]))
        assert payload["message"] == "job completed"
        assert payload["job_id"] == "job-1"
        assert payload["job_type"] == "document_process"
        assert payload["document_filename"] == "policy.pdf"
        assert payload["classification"] == "legal"
        assert payload["finding_count"] == 3
        assert payload["duration_ms"] is not None
    finally:
        _cleanup_logger(handler, job_logger, previous_level)
        reset_job_logging_state_for_tests()


def test_emit_job_store_log_page_progress():
    reset_job_logging_state_for_tests()
    handler, records, job_logger, previous_level = _capture_job_logs()
    try:
        running = JobRecord(
            job_id="job-2",
            job_type=JobType.PDF_STRUCTURE,
            status=JobStatus.RUNNING,
            progress=40,
            progress_message="OCR page 2",
            pages_done=2,
            pages_total=10,
        )
        updated = JobRecord(
            job_id="job-2",
            job_type=JobType.PDF_STRUCTURE,
            status=JobStatus.RUNNING,
            progress=50,
            progress_message="OCR page 3",
            pages_done=3,
            pages_total=10,
        )

        emit_job_store_log(running, updated, {"pages_done": 3})

        payload = json.loads(JsonFormatter().format(records[-1]))
        assert payload["message"] == "job page progress"
        assert payload["pages_done"] == 3
        assert payload["pages_total"] == 10
    finally:
        _cleanup_logger(handler, job_logger, previous_level)
        reset_job_logging_state_for_tests()
