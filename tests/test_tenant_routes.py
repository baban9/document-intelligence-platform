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
