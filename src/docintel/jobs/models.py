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


@dataclass
class JobRecord:
    job_id: str
    job_type: JobType
    status: JobStatus
    progress: int = 0
    download_url: str | None = None
    error: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "job_status": self.status.value,
            "progress": self.progress,
        }
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
            download_url=payload.get("download_url"),
            error=payload.get("error"),
            result=dict(payload.get("result") or {}),
        )
