from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    status: str
    attempts: int
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    trigger_payload: dict[str, Any] | None
    action_result: dict[str, Any] | None
    error: str | None

    @field_serializer("started_at", "finished_at")
    def _as_utc(self, value: datetime | None) -> str | None:
        """SQLite returns naive datetimes; they are UTC, so say so."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class ExecutionPage(BaseModel):
    items: list[ExecutionOut]
    total: int
    limit: int
    offset: int


class WebhookAccepted(BaseModel):
    """What a caller gets back from POST /hooks/{token}."""

    accepted: bool = True
    execution_id: int
    workflow: str
    status: str = "processing"
