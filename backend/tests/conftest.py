"""Test fixtures.

The environment is set before the app is imported: settings, the engine and
the database URL are all resolved once at import time. Outbound HTTP is
replaced with a mock transport, so no test ever reaches the network.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterator

import pytest

TEST_DB = os.path.join(tempfile.mkdtemp(prefix="wah-tests-"), "test.db")
os.environ.update(
    ENVIRONMENT="development",
    DATABASE_URL=f"sqlite:///{TEST_DB}",
    SECRET_KEY="test-secret-not-used-anywhere-else",
    # The mock transport answers instead of the network; this keeps the SSRF
    # guard from doing DNS lookups during tests.
    ALLOW_PRIVATE_NETWORK_TARGETS="true",
    ALLOW_REGISTRATION="true",
)

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.http_client import set_transport  # noqa: E402

DISCORD_CONFIG = {
    "webhook_url": "https://discord.com/api/webhooks/123456/token",
    "message_template": "New order #{{order_id}} from {{customer}}",
}
PASSWORD = "correct-horse-battery"


class Outbound:
    """Records what the adapters sent and decides what they get back."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.responses: list[httpx.Response] = []
        self.default = httpx.Response(204)

    def queue(self, *responses: httpx.Response) -> None:
        self.responses.extend(responses)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        return self.responses.pop(0) if self.responses else self.default

    @property
    def last_json(self) -> dict:
        import json

        return json.loads(self.requests[-1].content)


@pytest.fixture
def outbound() -> Iterator[Outbound]:
    recorder = Outbound()
    set_transport(httpx.MockTransport(recorder.handle))
    yield recorder
    set_transport(None)


@pytest.fixture(autouse=True)
def fresh_database() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_rate_limits()
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """A client with a registered account and its session cookie."""
    response = client.post(
        "/api/auth/register", json={"email": "dev@example.com", "password": PASSWORD}
    )
    assert response.status_code == 201
    return client


@pytest.fixture
def make_workflow(auth_client: TestClient) -> Callable[..., dict]:
    """Create a workflow and return its API representation."""

    def factory(**overrides) -> dict:
        body = {
            "name": "Order created",
            "action_type": "discord_webhook",
            "config": dict(DISCORD_CONFIG),
            "enabled": True,
        }
        body.update(overrides)
        response = auth_client.post("/api/workflows", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return factory


def token_of(workflow: dict) -> str:
    return workflow["webhook_url"].rsplit("/", 1)[1]
