from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class APIKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)


class APIKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    active: bool
    created_at: datetime
    last_used_at: datetime | None


class APIKeyCreated(APIKeyOut):
    """Returned once, by the create call only."""

    key: str
    warning: str = "Copy this key now — it is hashed on the server and cannot be shown again."
