#!/usr/bin/env python3
"""Start the RQ worker that processes async document jobs."""

from __future__ import annotations

import os
import sys

from redis import Redis
from rq import Queue, Worker

from docintel.jobs.queue import QUEUE_NAME
from docintel.jobs.store import redis_url


def main() -> None:
    src_path = os.path.join(os.path.dirname(__file__), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    connection = Redis.from_url(redis_url())
    queue = Queue(QUEUE_NAME, connection=connection)
    worker = Worker([queue], connection=connection)
    print(f"RQ worker listening on queue '{QUEUE_NAME}' ({redis_url()})")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
