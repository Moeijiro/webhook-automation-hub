"""Send a message through the Telegram Bot API."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field, field_validator

from app.actions.base import Action, ActionContext, ActionOutcome
from app.services.http_client import build_client
from app.services.templating import render

API_BASE = "https://api.telegram.org"


class TelegramConfig(BaseModel):
    bot_token: str = Field(min_length=20, max_length=100)
    chat_id: str = Field(min_length=1, max_length=64, description="@channel or numeric ID")
    message_template: str = Field(min_length=1, max_length=4000)
    parse_mode: str | None = Field(default=None, pattern="^(Markdown|MarkdownV2|HTML)$")

    @field_validator("bot_token")
    @classmethod
    def _shape(cls, value: str) -> str:
        # Tokens look like 123456789:AA... -- catch a pasted URL or username early.
        if ":" not in value or value.startswith("http"):
            raise ValueError("does not look like a Telegram bot token (123456:ABC-…)")
        return value.strip()


class TelegramAction(Action):
    type = "telegram_message"
    label = "Telegram message"
    description = "Send the rendered message to a chat with your bot."
    config_model = TelegramConfig
    secret_fields = ("bot_token",)

    async def run(self, config: TelegramConfig, context: ActionContext) -> ActionOutcome:
        rendered = render(config.message_template, context.payload)
        body: dict[str, object] = {
            "chat_id": config.chat_id,
            "text": rendered.text or "(empty message)",
        }
        if config.parse_mode:
            body["parse_mode"] = config.parse_mode

        # The token is part of the path, so the URL itself is a credential:
        # it is never put in a log line or an error message.
        url = f"{API_BASE}/bot{config.bot_token}/sendMessage"
        try:
            async with build_client() as client:
                response = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            return ActionOutcome(
                ok=False, detail=f"Network error: {type(exc).__name__}", retryable=True
            )

        extra = {"missing_placeholders": rendered.missing} if rendered.missing else {}
        if response.status_code == 200:
            return ActionOutcome(
                ok=True,
                detail=f"Message delivered to {config.chat_id}",
                status_code=200,
                extra=extra,
            )

        description = ""
        try:
            description = str(response.json().get("description", ""))
        except ValueError:
            description = self.excerpt(response.text)
        return ActionOutcome(
            ok=False,
            detail=f"Telegram returned {response.status_code}: {description}"[:200],
            status_code=response.status_code,
            retryable=response.status_code == 429 or response.status_code >= 500,
            extra=extra,
        )
