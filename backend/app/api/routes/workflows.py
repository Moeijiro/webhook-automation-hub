"""Workflow CRUD, the action catalogue and per-workflow execution logs."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.actions.registry import (
    ConfigError,
    describe_actions,
    encrypt_config,
    redact_config,
    validate_config,
)
from app.api.deps import get_current_user, get_owned_workflow
from app.core.config import settings
from app.core.security import generate_signing_secret, generate_workflow_token
from app.db.session import get_db
from app.models import Execution, User, Workflow
from app.schemas.execution import ExecutionOut, ExecutionPage
from app.schemas.workflow import (
    ActionCatalogEntry,
    WorkflowCreate,
    WorkflowCreated,
    WorkflowOut,
    WorkflowUpdate,
)

router = APIRouter(prefix="/api", tags=["workflows"])

UNPROCESSABLE = 422


@router.get("/actions", response_model=list[ActionCatalogEntry], summary="Available actions")
def list_actions() -> list[dict]:
    """Served from the adapter registry, so the UI cannot drift from the code."""
    return describe_actions()


def webhook_url(workflow: Workflow) -> str:
    return f"{settings.public_base_url}/hooks/{workflow.token}"


def curl_example(workflow: Workflow) -> str:
    sample = json.dumps({"order_id": 1024, "customer": "Alex", "amount": 49.99})
    return (
        f"curl -X POST {webhook_url(workflow)} \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{sample}'"
    )


def to_out(db: Session, workflow: Workflow, model=WorkflowOut, **extra):
    count, last = db.execute(
        select(func.count(Execution.id), func.max(Execution.started_at)).where(
            Execution.workflow_id == workflow.id
        )
    ).one()
    return model(
        id=workflow.id,
        name=workflow.name,
        trigger_type=workflow.trigger_type,
        action_type=workflow.action_type,
        config=redact_config(workflow.action_type, workflow.config),
        enabled=workflow.enabled,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        webhook_url=webhook_url(workflow),
        signature_required=workflow.signing_secret is not None,
        executions=count or 0,
        last_execution_at=last,
        **extra,
    )


@router.get("/workflows", response_model=list[WorkflowOut], summary="List workflows")
def list_workflows(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WorkflowOut]:
    workflows = db.execute(
        select(Workflow)
        .where(Workflow.user_id == user.id)
        .order_by(Workflow.created_at.desc())
    ).scalars().all()
    return [to_out(db, workflow) for workflow in workflows]


@router.post(
    "/workflows",
    response_model=WorkflowCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workflow",
)
def create_workflow(
    payload: WorkflowCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowCreated:
    try:
        config = validate_config(payload.action_type, payload.config)
    except ConfigError as exc:
        raise HTTPException(UNPROCESSABLE, str(exc)) from exc

    signing_secret = generate_signing_secret() if payload.require_signature else None
    workflow = Workflow(
        user_id=user.id,
        name=payload.name,
        trigger_type=payload.trigger_type,
        action_type=payload.action_type,
        config=encrypt_config(payload.action_type, config),
        token=generate_workflow_token(),
        signing_secret=signing_secret,
        enabled=payload.enabled,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    # The signing secret is shown here and never again.
    return to_out(
        db,
        workflow,
        WorkflowCreated,
        signing_secret=signing_secret,
        curl_example=curl_example(workflow),
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowCreated, summary="Workflow detail")
def get_workflow(
    workflow: Workflow = Depends(get_owned_workflow), db: Session = Depends(get_db)
) -> WorkflowCreated:
    return to_out(
        db, workflow, WorkflowCreated, signing_secret=None, curl_example=curl_example(workflow)
    )


@router.patch("/workflows/{workflow_id}", response_model=WorkflowOut, summary="Update a workflow")
def update_workflow(
    payload: WorkflowUpdate,
    workflow: Workflow = Depends(get_owned_workflow),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update.")

    if "config" in changes:
        try:
            config = validate_config(workflow.action_type, changes["config"])
        except ConfigError as exc:
            raise HTTPException(UNPROCESSABLE, str(exc)) from exc
        workflow.config = encrypt_config(workflow.action_type, config)
    if "name" in changes:
        workflow.name = changes["name"]
    if "enabled" in changes:
        workflow.enabled = changes["enabled"]
    if "require_signature" in changes:
        workflow.signing_secret = (
            workflow.signing_secret or generate_signing_secret()
            if changes["require_signature"]
            else None
        )

    db.commit()
    db.refresh(workflow)
    return to_out(db, workflow)


@router.delete(
    "/workflows/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workflow and its executions",
)
def delete_workflow(
    workflow: Workflow = Depends(get_owned_workflow), db: Session = Depends(get_db)
) -> Response:
    db.delete(workflow)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/workflows/{workflow_id}/logs",
    response_model=ExecutionPage,
    summary="Execution history for one workflow",
)
def workflow_logs(
    workflow: Workflow = Depends(get_owned_workflow),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status", max_length=16),
) -> ExecutionPage:
    where = [Execution.workflow_id == workflow.id]
    if status_filter:
        where.append(Execution.status == status_filter)

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
