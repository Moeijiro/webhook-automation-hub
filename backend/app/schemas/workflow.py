from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    action_type: Literal["discord_webhook", "telegram_message", "http_request"]
    config: dict[str, Any]
    enabled: bool = True
    trigger_type: Literal["incoming_webhook"] = "incoming_webhook"
    require_signature: bool = Field(
        default=False,
        description="Require an X-Hub-Signature-256 HMAC on incoming requests.",
    )


class WorkflowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    config: dict[str, Any] | None = None
    enabled: bool | None = None
    require_signature: bool | None = None


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    trigger_type: str
    action_type: str
    config: dict[str, Any]          # secrets replaced with a redaction marker
    enabled: bool
    created_at: datetime
    updated_at: datetime
    webhook_url: str
    signature_required: bool
    executions: int = 0
    last_execution_at: datetime | None = None


class WorkflowCreated(WorkflowOut):
    """Adds the values that are only ever shown once."""

    signing_secret: str | None = None
    curl_example: str


class ActionCatalogEntry(BaseModel):
    type: str
    label: str
    description: str
    secret_fields: list[str]
    schema_: dict[str, Any] = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True)
