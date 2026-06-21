"""Integration tests for local user onboarding and login."""

from docintel.auth.local_tokens import issue_local_token
from docintel.db.connection import get_connection


def _reset_user_tables() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_events")
            cur.execute("DELETE FROM users")


def test_auth_config_reports_local_auth(seeded_postgres_app):
    with seeded_postgres_app.test_client() as client:
        response = client.get("/v1/auth/config")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["local_auth_enabled"] is True


def test_onboard_login_change_password_flow(seeded_postgres_app, monkeypatch):
    monkeypatch.setenv("DOCINTEL_JWT_SECRET", "local-auth-test-secret")
    _reset_user_tables()

    with seeded_postgres_app.test_client() as client:
        onboard = client.post(
            "/v1/auth/users/onboard",
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
            },
        )
        assert onboard.status_code == 201
        onboard_payload = onboard.get_json()
        temp_password = onboard_payload["temporary_password"]
        assert onboard_payload["user"]["email"] == "ada@example.com"
        assert onboard_payload["user"]["is_admin"] is True

        bad_login = client.post(
            "/v1/auth/login",
            json={"email": "ada@example.com", "password": "wrong-password"},
        )
        assert bad_login.status_code == 401

        login = client.post(
            "/v1/auth/login",
            json={"email": "ada@example.com", "password": temp_password},
        )
        assert login.status_code == 200
        login_payload = login.get_json()
        assert login_payload["must_change_password"] is True
        token = login_payload["access_token"]

        me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        me_payload = me.get_json()
        assert me.status_code == 200
        assert me_payload["authenticated"] is True
        assert me_payload["first_name"] == "Ada"
        assert me_payload["must_change_password"] is True

        changed = client.post(
            "/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": temp_password,
                "new_password": "new-secure-password",
            },
        )
        assert changed.status_code == 200
        new_token = changed.get_json()["access_token"]

        relogin = client.post(
            "/v1/auth/login",
            json={"email": "ada@example.com", "password": "new-secure-password"},
        )
        assert relogin.status_code == 200
        assert relogin.get_json()["must_change_password"] is False

        events = client.get(
            "/v1/auth/login-events",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        events_payload = events.get_json()
        assert events.status_code == 200
        assert len(events_payload["events"]) >= 2
        assert any(event["success"] for event in events_payload["events"])
        assert any(not event["success"] for event in events_payload["events"])


def test_onboard_requires_admin_after_bootstrap(seeded_postgres_app, monkeypatch):
    monkeypatch.setenv("DOCINTEL_JWT_SECRET", "local-auth-test-secret")
    _reset_user_tables()

    from docintel.db.users import create_user, generate_temporary_password

    password = generate_temporary_password()
    user = create_user(
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        password=password,
        must_change_password=False,
        is_admin=True,
    )
    token = issue_local_token(user)

    with seeded_postgres_app.test_client() as client:
        blocked = client.post(
            "/v1/auth/users/onboard",
            headers={"X-Tenant-Slug": "acme-corp"},
            json={
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob@example.com",
            },
        )
        assert blocked.status_code == 403

        allowed = client.post(
            "/v1/auth/users/onboard",
            headers={
                "X-Tenant-Slug": "admin",
                "Authorization": f"Bearer {token}",
            },
            json={
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob@example.com",
            },
        )
        assert allowed.status_code == 201

        users = client.get(
            "/v1/auth/users",
            headers={
                "X-Tenant-Slug": "admin",
                "Authorization": f"Bearer {token}",
            },
        )
        assert users.status_code == 200
        assert len(users.get_json()["users"]) == 2
