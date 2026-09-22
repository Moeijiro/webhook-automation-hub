"""API keys: shown once, stored hashed, usable instead of the session."""

from __future__ import annotations

from fastapi.testclient import TestClient


def create_key(client: TestClient, name: str = "CI pipeline") -> dict:
    response = client.post("/api/api-keys", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_the_raw_key_is_returned_once_and_never_again(auth_client: TestClient) -> None:
    created = create_key(auth_client)
    assert created["key"].startswith("whk_")
    assert created["prefix"] == created["key"][:12]

    listed = auth_client.get("/api/api-keys").json()[0]
    assert "key" not in listed
    assert listed["prefix"] == created["prefix"]


def test_only_a_digest_reaches_the_database(auth_client: TestClient) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import APIKey

    created = create_key(auth_client)
    with SessionLocal() as db:
        stored = db.execute(select(APIKey)).scalar_one()

    assert stored.hashed_key != created["key"]
    assert len(stored.hashed_key) == 64  # sha256 hex
    assert created["key"] not in stored.hashed_key


def test_a_key_authenticates_the_management_api(
    auth_client: TestClient, make_workflow
) -> None:
    make_workflow()
    created = create_key(auth_client)
    auth_client.cookies.clear()  # no session: the key is the only credential

    response = auth_client.get("/api/workflows", headers={"X-API-Key": created["key"]})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_using_a_key_records_last_used_at(auth_client: TestClient) -> None:
    created = create_key(auth_client)
    assert created["last_used_at"] is None

    auth_client.get("/api/workflows", headers={"X-API-Key": created["key"]})
    assert auth_client.get("/api/api-keys").json()[0]["last_used_at"] is not None


def test_a_revoked_key_stops_working(auth_client: TestClient) -> None:
    created = create_key(auth_client)
    assert auth_client.delete(f"/api/api-keys/{created['id']}").status_code == 204

    auth_client.cookies.clear()
    assert (
        auth_client.get("/api/workflows", headers={"X-API-Key": created["key"]}).status_code
        == 401
    )


def test_an_invalid_key_is_rejected(client: TestClient) -> None:
    assert client.get("/api/workflows", headers={"X-API-Key": "whk_nope"}).status_code == 401


def test_keys_of_another_account_cannot_be_revoked(
    auth_client: TestClient, client: TestClient
) -> None:
    created = create_key(auth_client)
    auth_client.post("/api/auth/logout")
    auth_client.cookies.clear()
    auth_client.post(
        "/api/auth/register", json={"email": "other@example.com", "password": "correct-horse-battery"}
    )
    assert auth_client.delete(f"/api/api-keys/{created['id']}").status_code == 404
