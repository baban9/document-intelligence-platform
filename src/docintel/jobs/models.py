"""Job status types for async document processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def from_value(cls, value: str) -> "JobStatus":
        normalized = value.strip().lower()
        for status in cls:
            if status.value == normalized:
                return status
        raise ValueError(f"Unknown job status: {value}")


class JobType(str, Enum):
    PDF_STRUCTURE = "pdf_structure"
    PDF_DETECT_SENSITIVE = "pdf_detect_sensitive"
    PDF_ANNOTATE = "pdf_annotate"
    TEXT_SUMMARIZE = "text_summarize"
    BATCH = "batch"


@dataclass
class JobRecord:
    job_id: str
    job_type: JobType
    status: JobStatus
    progress: int = 0
    progress_message: str = ""
    pages_done: int = 0
    pages_total: int = 0
    callback_url: str | None = None
    download_url: str | None = None
    error: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "job_status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "pages_done": self.pages_done,
            "pages_total": self.pages_total,
        }
        if self.callback_url:
            payload["callback_url"] = self.callback_url
        if self.download_url:
            payload["download_url"] = self.download_url
        if self.error:
            payload["error"] = self.error
        if self.result:
            payload["result"] = self.result
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=str(payload["job_id"]),
            job_type=JobType(payload["job_type"]),
            status=JobStatus(payload.get("job_status", payload.get("status"))),
            progress=int(payload.get("progress", 0)),
            progress_message=str(payload.get("progress_message", "")),
            pages_done=int(payload.get("pages_done", 0)),
            pages_total=int(payload.get("pages_total", 0)),
            callback_url=payload.get("callback_url"),
            download_url=payload.get("download_url"),
            error=payload.get("error"),
            result=dict(payload.get("result") or {}),
        )
