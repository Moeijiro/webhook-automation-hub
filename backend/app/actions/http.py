"""Call an arbitrary HTTP API with a templated body."""

from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from app.actions.base import Action, ActionContext, ActionOutcome
from app.core.net import UnsafeTargetError, validate_target
from app.services.http_client import build_client
from app.services.templating import PLACEHOLDER, render

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
BODYLESS = {"GET", "DELETE"}
# Headers the client controls; letting a workflow set them breaks the request
# or the SSRF guard.
FORBIDDEN_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}


class HttpConfig(BaseModel):
    method: Method = "POST"
    url: str
    headers: dict[str, str] = Field(default_factory=dict, max_length=15)
    body_template: str | None = Field(default=None, max_length=8000)
    json_body: bool = Field(
        default=True, description="Send the rendered body as application/json."
    )

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return value.strip()

    @field_validator("headers")
    @classmethod
    def _check_headers(cls, value: dict[str, str]) -> dict[str, str]:
        for name, header_value in value.items():
            if name.lower() in FORBIDDEN_HEADERS:
                raise ValueError(f"{name} header cannot be set by a workflow")
            if len(name) > 64 or len(header_value) > 1024:
                raise ValueError(f"{name} header is too long")
        return value

    @model_validator(mode="after")
    def _body_matches_method(self) -> "HttpConfig":
        if self.method in BODYLESS and self.body_template:
            raise ValueError(f"{self.method} requests cannot carry a body")
        if self.json_body and self.body_template:
            # Check the shape at save time rather than on every execution. Every
            # placeholder becomes 0, which is valid both bare ({{amount}}) and
            # quoted ("{{id}}"), so only real JSON mistakes are rejected.
            probe = PLACEHOLDER.sub("0", self.body_template)
            try:
                json.loads(probe)
            except json.JSONDecodeError as exc:
                raise ValueError(f"body template is not valid JSON: {exc.msg}") from exc
        return self


class HttpAction(Action):
    type = "http_request"
    label = "HTTP request"
    description = "Call another API, with the payload available in the body template."
    config_model = HttpConfig
    # Header values routinely carry bearer tokens.
    secret_fields = ("headers",)

    async def run(self, config: HttpConfig, context: ActionContext) -> ActionOutcome:
        try:
            url = validate_target(config.url)
        except UnsafeTargetError as exc:
            return ActionOutcome(ok=False, detail=str(exc), retryable=False)

        headers = dict(config.headers)
        content: bytes | None = None
        missing: list[str] = []

        if config.body_template:
            rendered = render(
                config.body_template, context.payload, json_string=config.json_body
            )
            missing = rendered.missing
            content = rendered.text.encode()
            headers.setdefault(
                "Content-Type", "application/json" if config.json_body else "text/plain"
            )

        try:
            async with build_client() as client:
                response = await client.request(
                    config.method, url, headers=headers, content=content
                )
        except httpx.HTTPError as exc:
            return ActionOutcome(
                ok=False, detail=f"Network error: {type(exc).__name__}", retryable=True
            )

        extra = {"missing_placeholders": missing} if missing else {}
        ok = 200 <= response.status_code < 300
        return ActionOutcome(
            ok=ok,
            detail=f"{config.method} {response.status_code}",
            status_code=response.status_code,
            response_excerpt=self.excerpt(response.text),
            retryable=not ok
            and (response.status_code == 429 or response.status_code >= 500),
            extra=extra,
        )
