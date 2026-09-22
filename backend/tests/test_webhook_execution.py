"""The path that matters: webhook in, action out, execution logged."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from tests.conftest import Outbound, token_of

PAYLOAD = {"order_id": 1024, "customer": "Alex", "amount": 49.99}


def test_successful_execution_renders_the_template_and_logs_it(
    auth_client: TestClient, make_workflow, outbound: Outbound
) -> None:
    workflow = make_workflow()

    response = auth_client.post(f"/hooks/{token_of(workflow)}", json=PAYLOAD)
    assert response.status_code == 202
    assert response.json()["execution_id"] > 0

    # The adapter sent exactly what the template describes.
    assert outbound.requests[-1].url.host == "discord.com"
    assert outbound.last_json["content"] == "New order #1024 from Alex"

    log = auth_client.get(f"/api/workflows/{workflow['id']}/logs").json()["items"][0]
    assert log["status"] == "success"
    assert log["attempts"] == 1
    assert log["trigger_payload"] == PAYLOAD
    assert log["action_result"]["status_code"] == 204
    assert log["error"] is None
    assert log["duration_ms"] is not None


def test_failed_action_is_recorded_with_the_error(
    auth_client: TestClient, make_workflow, outbound: Outbound
) -> None:
    workflow = make_workflow()
    outbound.queue(httpx.Response(400, text="Invalid Webhook Token"))

    assert auth_client.post(f"/hooks/{token_of(workflow)}", json=PAYLOAD).status_code == 202

    log = auth_client.get(f"/api/workflows/{workflow['id']}/logs").json()["items"][0]
    assert log["status"] == "failed"
    assert log["attempts"] == 1  # 400 is not retryable
    assert "400" in log["error"]
    assert "Invalid Webhook Token" in log["action_result"]["response"]


def test_a_retryable_failure_is_attempted_three_times(
    auth_client: TestClient, make_workflow, outbound: Outbound, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.engine.BASE_BACKOFF_SECONDS", 0)
    workflow = make_workflow()
    outbound.queue(
        httpx.Response(502, text="bad gateway"),
        httpx.Response(502, text="bad gateway"),
        httpx.Response(502, text="bad gateway"),
    )

    auth_client.post(f"/hooks/{token_of(workflow)}", json=PAYLOAD)

    log = auth_client.get(f"/api/workflows/{workflow['id']}/logs").json()["items"][0]
    assert log["status"] == "failed"
    assert log["attempts"] == 3
    assert len(outbound.requests) == 3


def test_a_retry_that_succeeds_is_reported_as_success(
    auth_client: TestClient, make_workflow, outbound: Outbound, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.engine.BASE_BACKOFF_SECONDS", 0)
    workflow = make_workflow()
    outbound.queue(httpx.Response(500), httpx.Response(204))

    auth_client.post(f"/hooks/{token_of(workflow)}", json=PAYLOAD)

    log = auth_client.get(f"/api/workflows/{workflow['id']}/logs").json()["items"][0]
    assert log["status"] == "success"
    assert log["attempts"] == 2


def test_a_disabled_workflow_refuses_the_trigger(
    auth_client: TestClient, make_workflow, outbound: Outbound
) -> None:
    workflow = make_workflow(enabled=False)

    response = auth_client.post(f"/hooks/{token_of(workflow)}", json=PAYLOAD)
    assert response.status_code == 409
    assert outbound.requests == []
    assert auth_client.get(f"/api/workflows/{workflow['id']}/logs").json()["total"] == 0


def test_an_unknown_token_is_a_404(client: TestClient) -> None:
    assert client.post("/hooks/" + "x" * 32, json=PAYLOAD).status_code == 404


def test_the_webhook_endpoint_needs_no_session(
    client: TestClient, make_workflow, outbound: Outbound
) -> None:
    """The token is the credential; the caller is a third-party system."""
    workflow = make_workflow()
    client.cookies.clear()
    assert client.post(f"/hooks/{token_of(workflow)}", json=PAYLOAD).status_code == 202


def test_a_non_json_body_is_refused(auth_client: TestClient, make_workflow) -> None:
    workflow = make_workflow()
    response = auth_client.post(
        f"/hooks/{token_of(workflow)}",
        content=b"order_id=1024",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_an_oversized_payload_is_refused(auth_client: TestClient, make_workflow) -> None:
    workflow = make_workflow()
    response = auth_client.post(
        f"/hooks/{token_of(workflow)}", json={"blob": "x" * 70_000}
    )
    assert response.status_code == 413


def test_signed_workflows_require_a_valid_signature(
    auth_client: TestClient, make_workflow, outbound: Outbound
) -> None:
    import json

    from app.core.security import sign_body

    workflow = make_workflow(require_signature=True)
    secret = workflow["signing_secret"]
    assert secret  # shown once, at creation
    url = f"/hooks/{token_of(workflow)}"
    body = json.dumps(PAYLOAD).encode()

    unsigned = auth_client.post(url, content=body, headers={"Content-Type": "application/json"})
    assert unsigned.status_code == 401

    wrong = auth_client.post(
        url,
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert wrong.status_code == 401

    signed = auth_client.post(
        url,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sign_body(body, secret),
        },
    )
    assert signed.status_code == 202
    assert len(outbound.requests) == 1
