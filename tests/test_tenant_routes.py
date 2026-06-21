"""Integration tests for tenant settings routes (requires PostgreSQL)."""


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
                "llm_provider": "ollama",
                "llm_model": "llama3.2",
                "llm_base_url": "http://ollama:11434/v1",
                "pii_entities": ["EMAIL_ADDRESS", "PHONE_NUMBER"],
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["llm_model"] == "llama3.2"
    assert "EMAIL_ADDRESS" in payload["pii_entities"]


def test_settings_api_key_encrypted_at_rest(seeded_postgres_app, monkeypatch):
    monkeypatch.setenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "integration-test-key")
    with seeded_postgres_app.test_client() as client:
        response = client.put(
            "/v1/tenants/acme-corp/settings",
            headers={"X-Tenant-Slug": "admin"},
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
                    SELECT s.llm_api_key
                    FROM tenant_settings s
                    JOIN tenants t ON t.id = s.tenant_id
                    WHERE t.slug = %s
                    """,
                    ("acme-corp",),
                )
                stored = cur.fetchone()[0]
        assert stored.startswith("enc:v1:")
        assert "sk-test-secret-value" not in stored

        read_back = client.get(
            "/v1/tenants/acme-corp/settings",
            headers={"X-Tenant-Slug": "admin"},
        )
        payload = read_back.get_json()
        assert payload["llm_api_key_set"] is True


def test_settings_update_writes_audit_log(seeded_postgres_app):
    with seeded_postgres_app.test_client() as client:
        response = client.put(
            "/v1/tenants/finance-hub/settings",
            headers={"X-Tenant-Slug": "admin"},
            json={
                "llm_provider": "ollama",
                "llm_model": "llama3.2",
                "llm_base_url": "http://ollama:11434/v1",
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
