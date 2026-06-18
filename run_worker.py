#!/usr/bin/env python3
"""Start the RQ worker that processes async document jobs."""

from __future__ import annotations

import os
import sys

# macOS + PyTorch/EasyOCR: forked RQ work horses crash if Metal/MPS was initialized.
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from docintel.jobs.queue import QUEUE_NAME
from docintel.jobs.store import redis_url


def _worker_class():
    # SimpleWorker runs jobs in-process (no fork). Required for OCR jobs on macOS.
    if sys.platform == "darwin":
        return SimpleWorker
    return Worker


def main() -> None:
    src_path = os.path.join(os.path.dirname(__file__), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    connection = Redis.from_url(redis_url())
    queue = Queue(QUEUE_NAME, connection=connection)
    worker_cls = _worker_class()
    worker = worker_cls([queue], connection=connection)
    mode = "in-process (macOS OCR-safe)" if worker_cls is SimpleWorker else "forked"
    print(f"RQ worker listening on queue '{QUEUE_NAME}' ({redis_url()}), mode={mode}")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
