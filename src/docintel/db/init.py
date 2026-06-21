"""Database bootstrap and seed data."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from docintel.db.connection import database_enabled, get_connection
from docintel.services.pdf.presets import DEFAULT_PII_ENTITIES

DEFAULT_TENANTS: tuple[tuple[str, str, bool], ...] = (
    ("admin", "Platform Admin", True),
    ("acme-corp", "Acme Corp", False),
    ("healthcare-one", "Healthcare One", False),
    ("finance-hub", "Finance Hub", False),
)


def _schema_sql() -> str:
    package_path = files("docintel").joinpath("db/schema.sql")
    return package_path.read_text(encoding="utf-8")


def init_database() -> None:
    """Apply schema and seed default tenants when the database is empty."""
    if not database_enabled():
        return

    schema = _schema_sql()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)

            cur.execute("SELECT COUNT(*) FROM tenants")
            count = cur.fetchone()[0]
            if count:
                return

            default_entities = json.dumps(list(DEFAULT_PII_ENTITIES))
            for slug, name, is_admin in DEFAULT_TENANTS:
                cur.execute(
                    """
                    INSERT INTO tenants (slug, name, is_admin)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (slug, name, is_admin),
                )
                tenant_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO tenant_settings (
                        tenant_id, llm_provider, llm_model, llm_base_url, pii_entities
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        tenant_id,
                        "groq",
                        "llama-3.3-70b-versatile",
                        "https://api.groq.com/openai/v1",
                        default_entities,
                    ),
                )


def init_database_from_path(schema_path: Path | None = None) -> None:
    """Test helper: initialize using an explicit schema file path."""
    if not database_enabled():
        return

    schema = schema_path.read_text(encoding="utf-8") if schema_path else _schema_sql()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
