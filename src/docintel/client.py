"""Python client for the Document Intelligence Platform REST API."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests


class DocintelError(Exception):
    """Raised when the API returns an error response."""


class DocintelClient:
    """HTTP client for ``/v1/*`` document intelligence endpoints."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5000",
        api_key: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.ok:
            return
        try:
            payload = response.json()
            message = payload.get("error", response.text)
        except Exception:
            message = response.text or f"HTTP {response.status_code}"
        raise DocintelError(message)

    def health(self) -> dict[str, Any]:
        response = self._session.get(self._url("/health"), timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def get_job(self, job_id: str) -> dict[str, Any]:
        response = self._session.get(self._url(f"/v1/jobs/{job_id}"), timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def poll_job(
        self,
        job_id: str,
        *,
        interval_seconds: float = 2.0,
        timeout_seconds: float = 600.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            payload = self.get_job(job_id)
            status = payload.get("job_status")
            if status == "completed":
                return payload
            if status == "failed":
                raise DocintelError(payload.get("error", "Job failed"))
            time.sleep(interval_seconds)
        raise DocintelError(f"Job {job_id} timed out after {timeout_seconds}s")

    def download(self, download_url: str) -> bytes:
        response = self._session.get(self._url(download_url), timeout=self.timeout)
        self._raise_for_status(response)
        return response.content

    def structure_pdf(
        self,
        pdf_path: str | Path,
        *,
        mode: str = "curate",
        force_ocr: bool = False,
        redact_before_llm: bool = False,
        async_job: bool = False,
        callback_url: str | None = None,
        poll: bool = True,
    ) -> dict[str, Any] | bytes:
        path = Path(pdf_path)
        params = {"async": "true"} if async_job else {}
        data = {
            "mode": mode,
            "force_ocr": str(force_ocr).lower(),
            "redact_before_llm": str(redact_before_llm).lower(),
        }
        if callback_url:
            data["callback_url"] = callback_url
        with path.open("rb") as handle:
            response = self._session.post(
                self._url("/v1/pdf/structure"),
                params=params,
                files={"file": (path.name, handle, "application/pdf")},
                data=data,
                timeout=self.timeout,
            )
        if response.status_code == 202:
            payload = response.json()
            if not poll:
                return payload
            payload = self.poll_job(payload["job_id"])
            return self.download(payload["download_url"])
        self._raise_for_status(response)
        if "application/pdf" in response.headers.get("Content-Type", ""):
            return response.content
        return response.json()

    def detect_sensitive(
        self,
        pdf_path: str | Path,
        *,
        action: str = "Highlight",
        entities: str | None = None,
        force_ocr: bool = False,
        add_text_layer: bool = True,
        async_job: bool = False,
        callback_url: str | None = None,
        response_format: str = "json",
        poll: bool = True,
    ) -> dict[str, Any] | bytes:
        path = Path(pdf_path)
        params: dict[str, str] = {}
        if async_job:
            params["async"] = "true"
        if response_format == "json":
            params["format"] = "json"
        data: dict[str, str] = {
            "action": action,
            "force_ocr": str(force_ocr).lower(),
            "add_text_layer": str(add_text_layer).lower(),
        }
        if entities:
            data["entities"] = entities
        if callback_url:
            data["callback_url"] = callback_url
        with path.open("rb") as handle:
            response = self._session.post(
                self._url("/v1/pdf/detect-sensitive"),
                params=params,
                files={"file": (path.name, handle, "application/pdf")},
                data=data,
                timeout=self.timeout,
            )
        if response.status_code == 202:
            payload = response.json()
            if not poll:
                return payload
            payload = self.poll_job(payload["job_id"])
            if payload.get("download_url"):
                return self.download(payload["download_url"])
            return payload
        self._raise_for_status(response)
        if "application/pdf" in response.headers.get("Content-Type", ""):
            return response.content
        return response.json()

    def summarize(self, text: str, *, sentences: int = 3) -> dict[str, Any]:
        response = self._session.post(
            self._url("/v1/text/summarize"),
            json={"text": text, "sentences": sentences},
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.json()

    def list_document_types(self) -> dict[str, Any]:
        response = self._session.get(self._url("/v1/documents/types"), timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def identify_document(self, path: str | Path) -> dict[str, Any]:
        file_path = Path(path)
        with file_path.open("rb") as handle:
            response = self._session.post(
                self._url("/v1/documents/identify"),
                files={"file": (file_path.name, handle, "application/octet-stream")},
                timeout=self.timeout,
            )
        self._raise_for_status(response)
        return response.json()

    def extract_document_text(self, path: str | Path) -> dict[str, Any]:
        file_path = Path(path)
        with file_path.open("rb") as handle:
            response = self._session.post(
                self._url("/v1/documents/extract-text"),
                files={"file": (file_path.name, handle, "application/octet-stream")},
                timeout=self.timeout,
            )
        self._raise_for_status(response)
        return response.json()

    def summarize_document(
        self,
        path: str | Path | None = None,
        *,
        text: str | None = None,
        sentences: int = 3,
    ) -> dict[str, Any]:
        if path is not None:
            file_path = Path(path)
            with file_path.open("rb") as handle:
                response = self._session.post(
                    self._url("/v1/documents/summarize"),
                    files={"file": (file_path.name, handle, "application/octet-stream")},
                    data={"sentences": str(sentences)},
                    timeout=self.timeout,
                )
        else:
            response = self._session.post(
                self._url("/v1/documents/summarize"),
                json={"text": text or "", "sentences": sentences},
                timeout=self.timeout,
            )
        self._raise_for_status(response)
        return response.json()

    def detect_pii_document(
        self,
        path: str | Path | None = None,
        *,
        text: str | None = None,
        entities: str | None = None,
        vertical: str | None = None,
        min_score: float = 0.35,
    ) -> dict[str, Any]:
        data = {"min_score": str(min_score)}
        if entities:
            data["entities"] = entities
        if vertical:
            data["vertical"] = vertical
        if path is not None:
            file_path = Path(path)
            with file_path.open("rb") as handle:
                response = self._session.post(
                    self._url("/v1/documents/detect-pii"),
                    files={"file": (file_path.name, handle, "application/octet-stream")},
                    data=data,
                    timeout=self.timeout,
                )
        else:
            payload = {"text": text or "", "min_score": min_score}
            if entities:
                payload["entities"] = entities
            if vertical:
                payload["vertical"] = vertical
            response = self._session.post(
                self._url("/v1/documents/detect-pii"),
                json=payload,
                timeout=self.timeout,
            )
        self._raise_for_status(response)
        return response.json()

    def compare_documents(
        self,
        *,
        text_a: str | None = None,
        text_b: str | None = None,
        path_a: str | Path | None = None,
        path_b: str | Path | None = None,
    ) -> dict[str, Any]:
        if path_a is not None and path_b is not None:
            file_a = Path(path_a)
            file_b = Path(path_b)
            with file_a.open("rb") as handle_a, file_b.open("rb") as handle_b:
                response = self._session.post(
                    self._url("/v1/documents/compare"),
                    files={
                        "file_a": (file_a.name, handle_a, "application/octet-stream"),
                        "file_b": (file_b.name, handle_b, "application/octet-stream"),
                    },
                    timeout=self.timeout,
                )
        else:
            response = self._session.post(
                self._url("/v1/documents/compare"),
                json={"text_a": text_a or "", "text_b": text_b or ""},
                timeout=self.timeout,
            )
        self._raise_for_status(response)
        return response.json()
