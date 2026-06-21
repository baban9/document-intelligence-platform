"""PostgreSQL connection helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PGConnection


def database_url() -> str:
    return os.getenv("DOCINTEL_DATABASE_URL", "").strip()


def database_enabled() -> bool:
    return bool(database_url())


@contextmanager
def get_connection() -> Iterator[PGConnection]:
    url = database_url()
    if not url:
        raise RuntimeError("DOCINTEL_DATABASE_URL is not configured.")
    conn = psycopg2.connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
