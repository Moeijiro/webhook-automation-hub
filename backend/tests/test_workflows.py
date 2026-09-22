"""Workflow CRUD, configuration validation and ownership."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import DISCORD_CONFIG, PASSWORD


def test_create_returns_the_webhook_url_and_a_working_curl_example(
    auth_client: TestClient, make_workflow
) -> None:
    workflow = make_workflow()
    assert workflow["webhook_url"].startswith("http://localhost:8000/hooks/")
    assert workflow["webhook_url"].rsplit("/", 1)[1] in workflow["curl_example"]
    assert workflow["curl_example"].startswith("curl -X POST")


def test_secrets_are_redacted_in_every_response(
    auth_client: TestClient, make_workflow
) -> None:
    created = make_workflow()
    detail = auth_client.get(f"/api/workflows/{created['id']}").json()
    listed = auth_client.get("/api/workflows").json()[0]

    for view in (created, detail, listed):
        assert view["config"]["webhook_url"] == "••••••••"
        assert DISCORD_CONFIG["webhook_url"] not in str(view)


def test_the_stored_webhook_url_is_encrypted_at_rest(
    auth_client: TestClient, make_workflow
) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Workflow

    make_workflow()
    with SessionLocal() as db:
        stored = db.execute(select(Workflow)).scalar_one()
    assert DISCORD_CONFIG["webhook_url"] not in str(stored.config)
    assert "__enc__" in stored.config["webhook_url"]


def test_an_invalid_discord_url_is_rejected_at_save_time(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/workflows",
        json={
            "name": "Bad",
            "action_type": "discord_webhook",
            "config": {"webhook_url": "https://example.com/hook", "message_template": "hi"},
        },
    )
    assert response.status_code == 422
    assert "Discord webhook URL" in response.json()["detail"]


def test_an_unknown_action_type_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/workflows",
        json={"name": "Bad", "action_type": "carrier_pigeon", "config": {}},
    )
    assert response.status_code == 422


def test_http_action_validates_method_and_body(auth_client: TestClient) -> None:
    bad_method = auth_client.post(
        "/api/workflows",
        json={
            "name": "Bad method",
            "action_type": "http_request",
            "config": {"method": "TRACE", "url": "https://api.example.com/x"},
        },
    )
    assert bad_method.status_code == 422

    bad_body = auth_client.post(
        "/api/workflows",
        json={
            "name": "Bad body",
            "action_type": "http_request",
            "config": {
                "method": "POST",
                "url": "https://api.example.com/x",
                "body_template": '{"id": {{order_id}}',  # missing brace
            },
        },
    )
    assert bad_body.status_code == 422
    assert "JSON" in bad_body.json()["detail"]

    forbidden_header = auth_client.post(
        "/api/workflows",
        json={
            "name": "Bad header",
            "action_type": "http_request",
            "config": {
                "method": "POST",
                "url": "https://api.example.com/x",
                "headers": {"Host": "internal"},
            },
        },
    )
    assert forbidden_header.status_code == 422


def test_patch_updates_only_what_it_is_given(
    auth_client: TestClient, make_workflow
) -> None:
    workflow = make_workflow()
    response = auth_client.patch(
        f"/api/workflows/{workflow['id']}", json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["name"] == workflow["name"]

    assert auth_client.patch(f"/api/workflows/{workflow['id']}", json={}).status_code == 400


def test_delete_removes_the_workflow_and_its_endpoint(
    auth_client: TestClient, make_workflow
) -> None:
    workflow = make_workflow()
    token = workflow["webhook_url"].rsplit("/", 1)[1]

    assert auth_client.delete(f"/api/workflows/{workflow['id']}").status_code == 204
    assert auth_client.get(f"/api/workflows/{workflow['id']}").status_code == 404
    assert auth_client.post(f"/hooks/{token}", json={}).status_code == 404


def test_another_account_cannot_see_or_touch_the_workflow(
    auth_client: TestClient, make_workflow, client: TestClient
) -> None:
    workflow = make_workflow()
    auth_client.post("/api/auth/logout")
    auth_client.cookies.clear()
    auth_client.post(
        "/api/auth/register", json={"email": "other@example.com", "password": PASSWORD}
    )

    # 404, not 403: the API does not confirm that the id exists.
    assert auth_client.get(f"/api/workflows/{workflow['id']}").status_code == 404
    assert auth_client.delete(f"/api/workflows/{workflow['id']}").status_code == 404
    assert auth_client.get("/api/workflows").json() == []


def test_the_action_catalogue_comes_from_the_registry(auth_client: TestClient) -> None:
    catalogue = auth_client.get("/api/actions").json()
    assert {entry["type"] for entry in catalogue} == {
        "discord_webhook",
        "telegram_message",
        "http_request",
    }
    telegram = next(e for e in catalogue if e["type"] == "telegram_message")
    assert telegram["secret_fields"] == ["bot_token"]
    assert "properties" in telegram["schema"]
