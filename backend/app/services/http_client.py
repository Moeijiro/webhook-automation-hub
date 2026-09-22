"""One place that creates outbound HTTP clients.

Tests swap in a mock transport here instead of monkey-patching each adapter.
"""

from __future__ import annotations

import httpx

from app.core.config import settings

_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Install a transport for every future client (test hook)."""
    global _transport
    _transport = transport


def build_client(timeout: float | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout or settings.action_timeout_seconds,
        transport=_transport,
        follow_redirects=False,  # a redirect could escape the SSRF check
        headers={"User-Agent": "WebhookAutomationHub/1.0"},
    )
