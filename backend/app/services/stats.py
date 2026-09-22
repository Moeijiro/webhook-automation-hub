"""Dashboard aggregates, computed from the rows that exist.

Nothing here is estimated or seeded: an empty install shows zeros.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Execution, ExecutionStatus, User, Workflow


def overview(db: Session, user: User) -> dict[str, Any]:
    workflow_ids = select(Workflow.id).where(Workflow.user_id == user.id).scalar_subquery()

    total_workflows = db.execute(
        select(func.count()).select_from(Workflow).where(Workflow.user_id == user.id)
    ).scalar_one()
    active_workflows = db.execute(
        select(func.count())
        .select_from(Workflow)
        .where(Workflow.user_id == user.id, Workflow.enabled.is_(True))
    ).scalar_one()

    by_status = dict(
        db.execute(
            select(Execution.status, func.count())
            .where(Execution.workflow_id.in_(workflow_ids))
            .group_by(Execution.status)
        ).all()
    )
    executions = sum(by_status.values())
    succeeded = by_status.get(ExecutionStatus.SUCCESS.value, 0)
    failed = by_status.get(ExecutionStatus.FAILED.value, 0)

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    last_24h = db.execute(
        select(func.count())
        .select_from(Execution)
        .where(Execution.workflow_id.in_(workflow_ids), Execution.started_at >= since)
    ).scalar_one()

    return {
        "workflows": total_workflows,
        "active_workflows": active_workflows,
        "executions": executions,
        "succeeded": succeeded,
        "failed": failed,
        "processing": by_status.get(ExecutionStatus.PROCESSING.value, 0),
        "executions_last_24h": last_24h,
        "success_rate": round(succeeded / executions * 100, 1) if executions else None,
    }
