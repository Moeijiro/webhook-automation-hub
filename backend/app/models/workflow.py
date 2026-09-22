"""A workflow: one trigger, one action, one configuration blob."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.execution import Execution
    from app.models.user import User


class TriggerType(StrEnum):
    INCOMING_WEBHOOK = "incoming_webhook"


class ActionType(StrEnum):
    DISCORD_WEBHOOK = "discord_webhook"
    TELEGRAM_MESSAGE = "telegram_message"
    HTTP_REQUEST = "http_request"


class Workflow(Base, TimestampMixin):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(80))
    trigger_type: Mapped[str] = mapped_column(
        String(32), default=TriggerType.INCOMING_WEBHOOK
    )
    action_type: Mapped[str] = mapped_column(String(32))

    # Adapter-specific settings. Fields the adapter marks as secret are stored
    # encrypted and never serialised back out.
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # 32 bytes of entropy: the webhook URL is the credential for this endpoint.
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Optional HMAC secret; when set, callers must sign the request body.
    signing_secret: Mapped[Optional[str]] = mapped_column(String(128), default=None)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship(back_populates="workflows")
    executions: Mapped[list["Execution"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
