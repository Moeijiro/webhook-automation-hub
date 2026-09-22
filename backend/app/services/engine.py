"""The workflow engine: receive → validate → execute → log.

A webhook returns as soon as the execution row exists; the action itself runs
in a background task, so a slow Discord or Telegram never holds the caller's
connection open. Retries live here rather than in the adapters, which means
every integration gets the same policy for free.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.actions.base import ActionContext, ActionOutcome
from app.actions.registry import ConfigError, decrypt_config, get_action
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Execution, ExecutionStatus, Workflow

logger = logging.getLogger("engine")

BASE_BACKOFF_SECONDS = 0.5


def start_execution(db: Session, workflow: Workflow, payload: Any) -> Execution:
    """Record the run before anything is attempted, so nothing is lost."""
    execution = Execution(
        workflow_id=workflow.id,
        status=ExecutionStatus.PROCESSING,
        trigger_payload=payload if isinstance(payload, (dict, list)) else {"body": payload},
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


async def run_execution(execution_id: int) -> None:
    """Background entry point: own session, own error handling, never raises."""
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if execution is None:
            logger.warning("Execution %s vanished before it ran", execution_id)
            return
        workflow = db.get(Workflow, execution.workflow_id)
        if workflow is None:
            _finish(db, execution, ExecutionStatus.FAILED, error="Workflow was deleted")
            return

        started = time.perf_counter()
        try:
            config = decrypt_config(workflow.action_type, workflow.config)
            action = get_action(workflow.action_type)
        except ConfigError as exc:
            _finish(db, execution, ExecutionStatus.FAILED, error=str(exc))
            return

        context = ActionContext(
            payload=execution.trigger_payload,
            workflow_name=workflow.name,
            execution_id=execution.id,
        )

        outcome: ActionOutcome | None = None
        for attempt in range(1, settings.max_attempts + 1):
            execution.attempts = attempt
            try:
                outcome = await action.run(config, context)
            except Exception as exc:  # noqa: BLE001 - an adapter bug is a failed run
                logger.exception("Action %s raised", workflow.action_type)
                outcome = ActionOutcome(
                    ok=False, detail=f"Action error: {type(exc).__name__}", retryable=False
                )

            if outcome.ok or not outcome.retryable or attempt == settings.max_attempts:
                break
            delay = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.info(
                "Execution %s attempt %s failed (%s); retrying in %.1fs",
                execution.id, attempt, outcome.detail, delay,
            )
            await asyncio.sleep(delay)

        assert outcome is not None
        result = outcome.as_result()
        result["attempts"] = execution.attempts
        execution.action_result = result
        execution.duration_ms = int((time.perf_counter() - started) * 1000)
        _finish(
            db,
            execution,
            ExecutionStatus.SUCCESS if outcome.ok else ExecutionStatus.FAILED,
            error=None if outcome.ok else outcome.detail,
        )


def _finish(
    db: Session, execution: Execution, status: ExecutionStatus, *, error: str | None
) -> None:
    execution.status = status
    execution.error = error
    execution.finished_at = datetime.now(timezone.utc)
    db.commit()
