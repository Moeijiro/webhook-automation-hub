"""Send a message to a Discord channel through an incoming webhook URL."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field, field_validator

from app.actions.base import Action, ActionContext, ActionOutcome
from app.core.net import UnsafeTargetError, validate_target
from app.services.http_client import build_client
from app.services.templating import render

DISCORD_HOSTS = {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}


class DiscordConfig(BaseModel):
    webhook_url: str = Field(description="https://discord.com/api/webhooks/...")
    message_template: str = Field(min_length=1, max_length=2000)
    username: str | None = Field(default=None, max_length=80)

    @field_validator("webhook_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        from urllib.parse import urlparse

        host = (urlparse(value).hostname or "").lower()
        if host not in DISCORD_HOSTS or "/api/webhooks/" not in value:
            raise ValueError("must be a Discord webhook URL (discord.com/api/webhooks/…)")
        return value


class DiscordAction(Action):
    type = "discord_webhook"
    label = "Discord message"
    description = "Post the rendered message to a Discord channel webhook."
    config_model = DiscordConfig
    secret_fields = ("webhook_url",)

    async def run(self, config: DiscordConfig, context: ActionContext) -> ActionOutcome:
        rendered = render(config.message_template, context.payload)
        try:
            url = validate_target(config.webhook_url, require_https=True)
        except UnsafeTargetError as exc:
            return ActionOutcome(ok=False, detail=str(exc), retryable=False)

        body: dict[str, object] = {"content": rendered.text or "(empty message)"}
        if config.username:
            body["username"] = config.username

        try:
            async with build_client() as client:
                response = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            return ActionOutcome(
                ok=False, detail=f"Network error: {type(exc).__name__}", retryable=True
            )

        extra = {"missing_placeholders": rendered.missing} if rendered.missing else {}
        if response.status_code in (200, 204):
            return ActionOutcome(
                ok=True,
                detail="Message delivered to Discord",
                status_code=response.status_code,
                extra=extra,
            )
        return ActionOutcome(
            ok=False,
            detail=f"Discord returned {response.status_code}",
            status_code=response.status_code,
            response_excerpt=self.excerpt(response.text),
            retryable=response.status_code == 429 or response.status_code >= 500,
            extra=extra,
        )
