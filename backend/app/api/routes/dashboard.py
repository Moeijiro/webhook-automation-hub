"""Dashboard aggregates and the cross-workflow execution feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Execution, User, Workflow
from app.schemas.execution import ExecutionOut, ExecutionPage
from app.services import stats

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/stats", summary="Counts for the dashboard tiles")
def get_stats(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Every number is a COUNT over this account's own rows."""
    return stats.overview(db, user)


@router.get("/executions", response_model=ExecutionPage, summary="Recent executions")
def recent_executions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status", max_length=16),
    workflow_id: int | None = Query(default=None, ge=1),
) -> ExecutionPage:
    owned = select(Workflow.id).where(Workflow.user_id == user.id).scalar_subquery()
    where = [Execution.workflow_id.in_(owned)]
    if status_filter:
        where.append(Execution.status == status_filter)
    if workflow_id:
        where.append(Execution.workflow_id == workflow_id)

    items = db.execute(
        select(Execution)
        .where(*where)
        .order_by(Execution.started_at.desc(), Execution.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Execution).where(*where)).scalar_one()

    return ExecutionPage(
        items=[ExecutionOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
