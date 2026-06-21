#!/usr/bin/env python3
"""End-to-end smoke test for API + async worker + web UI proxy."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE = ROOT / "eval" / "fixtures" / "integrity" / "sample-wisp-policy.pdf"
FALLBACK_SAMPLE = ROOT / "eval" / "fixtures" / "integrity" / "smoke-sample.txt"


def _request(method: str, url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: float = 60.0):
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, body


def _json_body(body: bytes) -> dict:
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object response.")
    return payload


def pick_sample(path: Path | None) -> Path:
    if path is not None:
        if not path.is_file():
            raise FileNotFoundError(f"Sample file not found: {path}")
        return path
    if DEFAULT_SAMPLE.is_file():
        return DEFAULT_SAMPLE
    if FALLBACK_SAMPLE.is_file():
        return FALLBACK_SAMPLE
    raise FileNotFoundError("No sample document found for e2e test.")


def poll_job(api_base: str, poll_url: str, *, timeout_seconds: float = 600.0, interval_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    url = poll_url if poll_url.startswith("http") else f"{api_base}{poll_url}"
    while time.time() < deadline:
        status, body = _request("GET", url, timeout=30.0)
        if status != 200:
            raise RuntimeError(f"Job poll failed ({status}): {body.decode('utf-8', errors='replace')}")
        payload = _json_body(body)
        job_status = str(payload.get("job_status", ""))
        if job_status == "completed":
            return payload
        if job_status == "failed":
            raise RuntimeError(str(payload.get("error") or "Job failed."))
        time.sleep(interval_seconds)
    raise TimeoutError(f"Job timed out: {poll_url}")


def assert_process_result(result: dict) -> None:
    if "classification" not in result:
        nested = result.get("result")
        if isinstance(nested, dict):
            result = nested
    if "classification" not in result:
        raise AssertionError("Process result missing classification.")
    classification = result["classification"]
    if not isinstance(classification, dict) or not classification.get("category"):
        raise AssertionError("Process result missing classification category.")
    if "summary" not in result:
        raise AssertionError("Process result missing summary.")
    print(f"  classification: {classification.get('category')}")
    summary = result.get("summary")
    if isinstance(summary, dict):
        count = summary.get("sentence_count")
        if count is not None:
            print(f"  summary sentences: {count}")
    pii = result.get("pii")
    if isinstance(pii, dict):
        print(f"  pii findings: {pii.get('finding_count', 0)}")


def run_e2e(*, api_base: str, ui_base: str, sample_path: Path) -> None:
    print(f"API base: {api_base}")
    print(f"UI base:  {ui_base}")
    print(f"Sample:   {sample_path.name}")

    status, body = _request("GET", f"{api_base}/health")
    if status != 200:
        raise RuntimeError(f"API health check failed ({status}).")
    health = _json_body(body)
    print(f"API health: {health.get('status', 'unknown')}")

    status, body = _request("GET", f"{ui_base}/health")
    if status != 200:
        raise RuntimeError(f"UI health proxy failed ({status}).")
    ui_health = _json_body(body)
    print(f"UI health proxy: {ui_health.get('status', 'unknown')}")

    boundary = "----docintel-e2e-boundary"
    fields = {
        "sentences": "2",
        "include_summarize": "true",
        "include_pii": "true",
        "include_text": "false",
    }
    file_bytes = sample_path.read_bytes()
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{sample_path.name}"\r\n'.encode()
    )
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    form_body = b"".join(parts)

    process_url = f"{ui_base}/v1/documents/process?async=true"
    status, body = _request(
        "POST",
        process_url,
        data=form_body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=120.0,
    )
    if status not in (200, 202):
        raise RuntimeError(
            f"Process request via UI proxy failed ({status}): {body.decode('utf-8', errors='replace')}"
        )
    queued = _json_body(body)
    poll_url = queued.get("poll_url")
    if not isinstance(poll_url, str):
        raise RuntimeError("Async process response missing poll_url.")
    print(f"Queued job: {queued.get('job_id')} ({queued.get('job_status')})")

    completed = poll_job(ui_base, poll_url)
    result = completed.get("result")
    if not isinstance(result, dict):
        raise AssertionError("Completed job missing result payload.")
    assert_process_result(result)
    print("E2E process pipeline: passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run docintel end-to-end smoke test.")
    parser.add_argument(
        "--api-base",
        default=os.getenv("DOCINTEL_API_URL", "http://127.0.0.1:5000").rstrip("/"),
    )
    parser.add_argument(
        "--ui-base",
        default=os.getenv("DOCINTEL_UI_URL", "http://127.0.0.1:8080").rstrip("/"),
    )
    parser.add_argument("--sample", type=Path, default=None)
    args = parser.parse_args()

    try:
        sample = pick_sample(args.sample)
        run_e2e(api_base=args.api_base, ui_base=args.ui_base, sample_path=sample)
    except Exception as exc:  # noqa: BLE001 - CLI should print one clear failure
        print(f"E2E failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
