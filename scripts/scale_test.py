#!/usr/bin/env python3
"""Run concurrent async document jobs against a live API for scale testing."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "eval" / "corpus" / "generated"
DEFAULT_API = "http://127.0.0.1:5000"


@dataclass
class JobOutcome:
    file_path: str
    job_id: str | None
    ok: bool
    latency_seconds: float
    error: str | None = None


def _load_manifest(corpus_dir: Path) -> list[dict[str, Any]]:
    manifest_path = corpus_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Missing {manifest_path}. Run: python scripts/generate_test_corpus.py"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError(f"No files listed in {manifest_path}")
    return files


def _poll_job(
    session: requests.Session,
    base_url: str,
    poll_url: str,
    *,
    timeout_seconds: float,
    interval_seconds: float,
) -> tuple[bool, str | None]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = session.get(f"{base_url}{poll_url}", timeout=30)
        if not response.ok:
            return False, response.text
        payload = response.json()
        status = payload.get("job_status")
        if status == "completed":
            return True, None
        if status == "failed":
            return False, str(payload.get("error") or "job failed")
        time.sleep(interval_seconds)
    return False, "poll timeout"


def _submit_process_job(
    session: requests.Session,
    base_url: str,
    file_path: Path,
    *,
    timeout_seconds: float,
    poll_interval: float,
    include_pii: bool,
) -> JobOutcome:
    started = time.perf_counter()
    with file_path.open("rb") as handle:
        response = session.post(
            f"{base_url}/v1/documents/process?async=true",
            files={"file": (file_path.name, handle, "application/octet-stream")},
            data={
                "include_summarize": "true",
                "include_pii": str(include_pii).lower(),
                "include_text": "false",
                "sentences": "2",
            },
            timeout=120,
        )
    if response.status_code != 202:
        return JobOutcome(
            file_path=str(file_path),
            job_id=None,
            ok=False,
            latency_seconds=time.perf_counter() - started,
            error=response.text,
        )

    payload = response.json()
    poll_url = payload.get("poll_url")
    job_id = payload.get("job_id")
    if not poll_url:
        return JobOutcome(
            file_path=str(file_path),
            job_id=job_id,
            ok=False,
            latency_seconds=time.perf_counter() - started,
            error="missing poll_url",
        )

    ok, error = _poll_job(
        session,
        base_url,
        poll_url,
        timeout_seconds=timeout_seconds,
        interval_seconds=poll_interval,
    )
    return JobOutcome(
        file_path=str(file_path),
        job_id=job_id,
        ok=ok,
        latency_seconds=time.perf_counter() - started,
        error=error,
    )


def run_scale_test(
    *,
    base_url: str,
    corpus_dir: Path,
    concurrency: int,
    requests_total: int,
    timeout_seconds: float,
    poll_interval: float,
    include_pii: bool,
) -> dict[str, Any]:
    files = _load_manifest(corpus_dir)
    session = requests.Session()
    outcomes: list[JobOutcome] = []

    def pick_file(index: int) -> Path:
        entry = files[index % len(files)]
        return corpus_dir / str(entry["path"])

    with ThreadPoolExecutor(max_workers=max(concurrency, 1)) as pool:
        futures = [
            pool.submit(
                _submit_process_job,
                session,
                base_url.rstrip("/"),
                pick_file(index),
                timeout_seconds=timeout_seconds,
                poll_interval=poll_interval,
                include_pii=include_pii,
            )
            for index in range(requests_total)
        ]
        for future in as_completed(futures):
            outcomes.append(future.result())

    latencies = [item.latency_seconds for item in outcomes if item.ok]
    failures = [item for item in outcomes if not item.ok]
    report: dict[str, Any] = {
        "base_url": base_url,
        "corpus_dir": str(corpus_dir),
        "concurrency": concurrency,
        "requests_total": requests_total,
        "include_pii": include_pii,
        "success_count": sum(1 for item in outcomes if item.ok),
        "failure_count": len(failures),
        "latency_seconds": {},
        "failures": [
            {"file_path": item.file_path, "job_id": item.job_id, "error": item.error}
            for item in failures[:20]
        ],
    }
    if latencies:
        ordered = sorted(latencies)
        report["latency_seconds"] = {
            "min": round(min(latencies), 3),
            "p50": round(statistics.median(ordered), 3),
            "p95": round(ordered[max(int(len(ordered) * 0.95) - 1, 0)], 3),
            "max": round(max(latencies), 3),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="Generated corpus dir")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel in-flight jobs")
    parser.add_argument("--requests", type=int, default=12, help="Total jobs to submit")
    parser.add_argument("--timeout", type=float, default=600.0, help="Per-job poll timeout seconds")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Job poll interval seconds")
    parser.add_argument("--no-pii", action="store_true", help="Disable PII scan (lower memory)")
    parser.add_argument("--report", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()

    report = run_scale_test(
        base_url=args.api,
        corpus_dir=args.corpus.resolve(),
        concurrency=args.concurrency,
        requests_total=args.requests,
        timeout_seconds=args.timeout,
        poll_interval=args.poll_interval,
        include_pii=not args.no_pii,
    )
    text = json.dumps(report, indent=2)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
        print(f"\nReport written to {args.report}")
    return 0 if report["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
