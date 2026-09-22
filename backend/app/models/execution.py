"""One run of a workflow, from webhook receipt to final action result."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.workflow import Workflow


class ExecutionStatus(StrEnum):
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (Index("ix_executions_workflow_started", "workflow_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(
        String(16), default=ExecutionStatus.PROCESSING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    trigger_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)
    # What the destination answered: status code, trimmed body, attempt count.
    action_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)
    error: Mapped[Optional[str]] = mapped_column(Text, default=None)

    workflow: Mapped["Workflow"] = relationship(back_populates="executions")
