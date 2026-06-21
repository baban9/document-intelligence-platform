#!/usr/bin/env python3
"""Wait until the local Docker stack is ready for requests."""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request


def _get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(500).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        return exc.code, body


def wait_for_url(name: str, url: str, *, timeout_seconds: float, interval_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "unknown error"
    while time.time() < deadline:
        try:
            status, _body = _get(url)
            if 200 <= status < 300:
                print(f"ready: {name} ({url})")
                return
            last_error = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 - surface last connection error
            last_error = str(exc)
        time.sleep(interval_seconds)
    raise TimeoutError(f"Timed out waiting for {name} at {url}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for docintel stack health checks.")
    parser.add_argument(
        "--api-base",
        default=os.getenv("DOCINTEL_API_URL", "http://127.0.0.1:5000").rstrip("/"),
    )
    parser.add_argument(
        "--ui-base",
        default=os.getenv("DOCINTEL_UI_URL", "http://127.0.0.1:8080").rstrip("/"),
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--skip-ui", action="store_true")
    args = parser.parse_args()

    try:
        wait_for_url("api", f"{args.api_base}/health", timeout_seconds=args.timeout, interval_seconds=args.interval)
        if not args.skip_ui:
            wait_for_url("web-ui", f"{args.ui_base}/health", timeout_seconds=args.timeout, interval_seconds=args.interval)
            wait_for_url("web-ui-shell", args.ui_base, timeout_seconds=args.timeout, interval_seconds=args.interval)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
