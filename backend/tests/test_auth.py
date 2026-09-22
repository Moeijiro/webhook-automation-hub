"""Registration, login and the closed door in front of every other route."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD

PROTECTED = [
    ("get", "/api/auth/me"),
    ("get", "/api/workflows"),
    ("get", "/api/api-keys"),
    ("get", "/api/stats"),
    ("get", "/api/executions"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_management_routes_require_authentication(
    client: TestClient, method: str, path: str
) -> None:
    assert getattr(client, method)(path).status_code == 401


def test_register_issues_an_httponly_session(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": "New@Example.com ", "password": PASSWORD}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"  # normalised
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 200


def test_password_is_never_returned_or_stored_in_clear(auth_client: TestClient) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import User

    assert "password" not in auth_client.get("/api/auth/me").json()
    with SessionLocal() as db:
        user = db.execute(select(User)).scalar_one()
    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith("scrypt$")


def test_duplicate_email_is_refused(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/auth/register", json={"email": "dev@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409


def test_short_password_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_login_rejects_a_wrong_password_without_saying_which_part_failed(
    auth_client: TestClient,
) -> None:
    wrong_password = auth_client.post(
        "/api/auth/login", json={"email": "dev@example.com", "password": "not-the-password"}
    )
    unknown_user = auth_client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["detail"] == unknown_user.json()["detail"]


def test_login_then_logout(auth_client: TestClient) -> None:
    assert auth_client.post(
        "/api/auth/login", json={"email": "dev@example.com", "password": PASSWORD}
    ).status_code == 200
    assert auth_client.post("/api/auth/logout").status_code == 204
    auth_client.cookies.clear()
    assert auth_client.get("/api/auth/me").status_code == 401


def test_a_tampered_session_cookie_is_rejected(auth_client: TestClient) -> None:
    auth_client.cookies.set("wah_session", "not.a.jwt")
    assert auth_client.get("/api/auth/me").status_code == 401
