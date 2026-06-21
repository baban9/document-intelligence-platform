"""Local user accounts and login activity persistence."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from docintel.db.connection import database_enabled, get_connection


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    first_name: str
    last_name: str
    is_active: bool
    is_admin: bool
    must_change_password: bool
    created_at: datetime | None
    updated_at: datetime | None
    last_login_at: datetime | None

    def to_dict(self, *, include_email: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}".strip(),
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "must_change_password": self.must_change_password,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_email:
            payload["email"] = self.email
        return payload


@dataclass(frozen=True)
class LoginEventRecord:
    id: str
    user_id: str
    email: str
    method: str
    ip_address: str
    user_agent: str
    success: bool
    failure_reason: str
    created_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "method": self.method,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def local_auth_enabled() -> bool:
    return database_enabled()


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _row_to_user(row) -> UserRecord:
    return UserRecord(
        id=str(row[0]),
        email=str(row[1]),
        first_name=str(row[2] or ""),
        last_name=str(row[3] or ""),
        is_active=bool(row[4]),
        is_admin=bool(row[5]),
        must_change_password=bool(row[6]),
        created_at=row[7],
        updated_at=row[8],
        last_login_at=row[9],
    )


def _row_to_login_event(row) -> LoginEventRecord:
    return LoginEventRecord(
        id=str(row[0]),
        user_id=str(row[1] or ""),
        email=str(row[2] or ""),
        method=str(row[3] or "local"),
        ip_address=str(row[4] or ""),
        user_agent=str(row[5] or ""),
        success=bool(row[6]),
        failure_reason=str(row[7] or ""),
        created_at=row[8],
    )


_USER_SELECT = """
SELECT id, email, first_name, last_name, is_active, is_admin,
       must_change_password, created_at, updated_at, last_login_at
FROM users
"""


def count_users() -> int:
    if not local_auth_enabled():
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            return int(cur.fetchone()[0])


def get_user_by_id(user_id: str) -> UserRecord | None:
    if not local_auth_enabled():
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"{_USER_SELECT} WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> UserRecord | None:
    if not local_auth_enabled():
        return None
    normalized = email.strip().lower()
    if not normalized:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"{_USER_SELECT} WHERE LOWER(email) = %s", (normalized,))
            row = cur.fetchone()
            return _row_to_user(row) if row else None


def get_user_password_hash(email: str) -> tuple[UserRecord, str] | None:
    if not local_auth_enabled():
        return None
    normalized = email.strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, first_name, last_name, is_active, is_admin,
                       must_change_password, created_at, updated_at, last_login_at,
                       password_hash
                FROM users
                WHERE LOWER(email) = %s
                """,
                (normalized,),
            )
            row = cur.fetchone()
            if not row:
                return None
            user = _row_to_user(row[:10])
            return user, str(row[10] or "")


def verify_user_password(email: str, password: str) -> UserRecord | None:
    match = get_user_password_hash(email)
    if match is None:
        return None
    user, password_hash = match
    if not user.is_active:
        return None
    if not check_password_hash(password_hash, password):
        return None
    return user


def create_user(
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    must_change_password: bool = True,
    is_admin: bool = False,
) -> UserRecord:
    if not local_auth_enabled():
        raise RuntimeError("Local auth requires PostgreSQL.")

    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Email is required.")
    if not password:
        raise ValueError("Password is required.")

    password_hash = generate_password_hash(password)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    email, password_hash, first_name, last_name,
                    must_change_password, is_admin
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, email, first_name, last_name, is_active, is_admin,
                          must_change_password, created_at, updated_at, last_login_at
                """,
                (
                    normalized_email,
                    password_hash,
                    first_name.strip(),
                    last_name.strip(),
                    must_change_password,
                    is_admin,
                ),
            )
            row = cur.fetchone()
            return _row_to_user(row)


def update_user_password(user_id: str, new_password: str, *, clear_must_change: bool = True) -> bool:
    if not local_auth_enabled():
        return False
    if not new_password:
        raise ValueError("New password is required.")

    password_hash = generate_password_hash(new_password)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    must_change_password = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (password_hash, not clear_must_change, user_id),
            )
            return cur.rowcount > 0


def touch_user_login(user_id: str) -> None:
    if not local_auth_enabled():
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s",
                (user_id,),
            )


def record_login_event(
    *,
    user_id: str = "",
    email: str = "",
    method: str = "local",
    ip_address: str = "",
    user_agent: str = "",
    success: bool,
    failure_reason: str = "",
) -> None:
    if not local_auth_enabled():
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO login_events (
                    user_id, email, method, ip_address, user_agent, success, failure_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id or None,
                    email.strip().lower(),
                    method,
                    ip_address[:64],
                    user_agent[:512],
                    success,
                    failure_reason[:255],
                ),
            )


def list_login_events(*, user_id: str | None = None, limit: int = 50) -> list[LoginEventRecord]:
    if not local_auth_enabled():
        return []
    capped = max(1, min(limit, 200))
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    """
                    SELECT id, user_id, email, method, ip_address, user_agent,
                           success, failure_reason, created_at
                    FROM login_events
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, capped),
                )
            else:
                cur.execute(
                    """
                    SELECT id, user_id, email, method, ip_address, user_agent,
                           success, failure_reason, created_at
                    FROM login_events
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (capped,),
                )
            return [_row_to_login_event(row) for row in cur.fetchall()]


def list_users(limit: int = 100) -> list[UserRecord]:
    if not local_auth_enabled():
        return []
    capped = max(1, min(limit, 200))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"{_USER_SELECT} ORDER BY created_at DESC LIMIT %s", (capped,))
            return [_row_to_user(row) for row in cur.fetchall()]
