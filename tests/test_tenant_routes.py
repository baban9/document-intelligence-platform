"""Integration tests for tenant settings routes (requires PostgreSQL)."""

from docintel.auth.api_keys import AuthContext


def _reset_acme_api_key_state() -> None:
    from docintel.db.connection import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenant_settings s
                SET llm_api_key = '', llm_api_key_owner = ''
                FROM tenants t
                WHERE s.tenant_id = t.id AND t.slug = %s
                """,
                ("acme-corp",),
            )

def test_list_tenants_as_admin(seeded_postgres_app):
    with seeded_postgres_app.test_client() as client:
        response = client.get("/v1/tenants", headers={"X-Tenant-Slug": "admin"})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["is_admin"] is True
    assert len(payload["tenants"]) >= 4


def test_regular_tenant_cannot_read_other_settings(seeded_postgres_app):
    with seeded_postgres_app.test_client() as client:
        response = client.get(
            "/v1/tenants/finance-hub/settings",
            headers={"X-Tenant-Slug": "acme-corp"},
        )

    assert response.status_code == 403


def test_admin_can_update_tenant_settings(seeded_postgres_app):
    with seeded_postgres_app.test_client() as client:
        response = client.put(
            "/v1/tenants/acme-corp/settings",
            headers={"X-Tenant-Slug": "admin"},
            json={
                "llm_provider": "groq",
                "llm_model": "llama-3.3-70b-versatile",
                "llm_base_url": "https://api.groq.com/openai/v1",
                "pii_entities": ["EMAIL_ADDRESS", "PHONE_NUMBER"],
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["llm_model"] == "llama-3.3-70b-versatile"
    assert "EMAIL_ADDRESS" in payload["pii_entities"]


def test_settings_api_key_encrypted_at_rest(seeded_postgres_app, monkeypatch):
    monkeypatch.setenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "integration-test-key")
    _reset_acme_api_key_state()
    owner_id = "settings-owner-test-user"
    headers = {"X-Tenant-Slug": "admin", "X-Settings-User-Id": owner_id}
    with seeded_postgres_app.test_client() as client:
        response = client.put(
            "/v1/tenants/acme-corp/settings",
            headers=headers,
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "llm_base_url": "https://api.openai.com/v1",
                "llm_api_key": "sk-test-secret-value",
                "pii_entities": ["EMAIL_ADDRESS"],
            },
        )
        assert response.status_code == 200

        from docintel.db.connection import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.llm_api_key, s.llm_api_key_owner
                    FROM tenant_settings s
                    JOIN tenants t ON t.id = s.tenant_id
                    WHERE t.slug = %s
                    """,
                    ("acme-corp",),
                )
                stored, stored_owner = cur.fetchone()
        assert stored.startswith("enc:u1:")
        assert stored_owner == owner_id
        assert "sk-test-secret-value" not in stored

        read_back = client.get("/v1/tenants/acme-corp/settings", headers=headers)
        payload = read_back.get_json()
        assert payload["llm_api_key_set"] is True
        assert payload["llm_api_key_owner_match"] is True
        assert "llm_api_key" not in payload

        reveal = client.get("/v1/tenants/acme-corp/settings/api-key", headers=headers)
        assert reveal.status_code == 200
        assert reveal.get_json()["llm_api_key"] == "sk-test-secret-value"

        blocked = client.get(
            "/v1/tenants/acme-corp/settings/api-key",
            headers={"X-Tenant-Slug": "admin", "X-Settings-User-Id": "someone-else"},
        )
        assert blocked.status_code == 403


def test_settings_api_key_owner_uses_oidc_subject(seeded_postgres_app, monkeypatch):
    monkeypatch.setenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "integration-test-key")
    _reset_acme_api_key_state()
    owner_id = "oidc-user-999"
    headers = {
        "X-Tenant-Slug": "admin",
        "Authorization": "Bearer dev-oidc-token",
        "X-Settings-User-Id": "browser-fallback-id",
    }
    monkeypatch.setattr(
        "docintel.auth.middleware.validate_credentials",
        lambda token: AuthContext(
            method="oidc",
            subject=owner_id,
            email="user@example.com",
        )
        if token == "dev-oidc-token"
        else None,
    )

    with seeded_postgres_app.test_client() as client:
        response = client.put(
            "/v1/tenants/acme-corp/settings",
            headers=headers,
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "llm_base_url": "https://api.openai.com/v1",
                "llm_api_key": "sk-oidc-owner-key",
                "pii_entities": ["EMAIL_ADDRESS"],
            },
        )
        assert response.status_code == 200

        reveal = client.get("/v1/tenants/acme-corp/settings/api-key", headers=headers)
        assert reveal.status_code == 200
        assert reveal.get_json()["llm_api_key"] == "sk-oidc-owner-key"

        from docintel.db.connection import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.llm_api_key_owner
                    FROM tenant_settings s
                    JOIN tenants t ON t.id = s.tenant_id
                    WHERE t.slug = %s
                    """,
                    ("acme-corp",),
                )
                assert cur.fetchone()[0] == owner_id

        blocked = client.get(
            "/v1/tenants/acme-corp/settings/api-key",
            headers={
                "X-Tenant-Slug": "admin",
                "X-Settings-User-Id": "browser-fallback-id",
            },
        )
        assert blocked.status_code == 403


def test_settings_update_writes_audit_log(seeded_postgres_app):
    with seeded_postgres_app.test_client() as client:
        response = client.put(
            "/v1/tenants/finance-hub/settings",
            headers={"X-Tenant-Slug": "admin"},
            json={
                "llm_provider": "groq",
                "llm_model": "llama-3.3-70b-versatile",
                "llm_base_url": "https://api.groq.com/openai/v1",
                "pii_entities": ["CREDIT_CARD"],
            },
        )
        assert response.status_code == 200

        from docintel.db.connection import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT action, actor, tenant_slug
                    FROM audit_log
                    WHERE tenant_slug = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    ("finance-hub",),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] == "tenant_settings.update"
        assert row[1] == "admin"
        assert row[2] == "finance-hub"
