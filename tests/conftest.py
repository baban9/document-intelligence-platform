"""Shared pytest fixtures."""

import os
import time
from pathlib import Path

import fitz
import pytest


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice Number: ABC123")
    page.insert_text((72, 100), "Customer ID: XYZ789")
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def _postgres_url() -> str:
    return os.getenv("DOCINTEL_DATABASE_URL", "").strip()


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = _postgres_url()
    if not url:
        pytest.skip("Set DOCINTEL_DATABASE_URL to run PostgreSQL integration tests.")
    return url


@pytest.fixture(scope="session")
def postgres_ready(postgres_url: str) -> str:
    """Wait until PostgreSQL accepts connections."""
    import psycopg2

    deadline = time.time() + 30
    last_error = None
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(postgres_url)
            conn.close()
            return postgres_url
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    pytest.skip(f"PostgreSQL not reachable: {last_error}")


@pytest.fixture(scope="session")
def postgres_env(postgres_ready: str):
    previous = {
        "DOCINTEL_DATABASE_URL": os.environ.get("DOCINTEL_DATABASE_URL"),
        "DOCINTEL_MULTI_TENANT": os.environ.get("DOCINTEL_MULTI_TENANT"),
        "DOCINTEL_AUTH_REQUIRED": os.environ.get("DOCINTEL_AUTH_REQUIRED"),
        "DOCINTEL_API_KEYS": os.environ.get("DOCINTEL_API_KEYS"),
    }
    os.environ["DOCINTEL_DATABASE_URL"] = postgres_ready
    os.environ["DOCINTEL_MULTI_TENANT"] = "true"
    os.environ["DOCINTEL_AUTH_REQUIRED"] = "false"
    os.environ["DOCINTEL_API_KEYS"] = ""
    yield postgres_ready
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="session")
def seeded_postgres_app(postgres_env):
    from docintel.app import create_app
    from docintel.db.init import init_database

    init_database()
    return create_app()


@pytest.fixture
def fake_redis(monkeypatch):
    from docintel.jobs.store import reset_redis_client_cache

    import fakeredis

    reset_redis_client_cache()
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("docintel.jobs.store._redis_client", lambda: client)
    yield client
    reset_redis_client_cache()
