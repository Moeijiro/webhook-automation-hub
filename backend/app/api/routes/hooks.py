"""The public webhook endpoint: ``POST /hooks/{token}``.

The token is the credential, so this route is deliberately thin and strict:
size limit, JSON parse, workflow lookup, optional HMAC, then hand off to a
background task and answer 202 with the execution id. The caller is never held
open while Discord or Telegram is contacted.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import RateLimiter
from app.core.security import verify_body_signature
from app.db.session import get_db
from app.models import Workflow
from app.schemas.execution import WebhookAccepted
from app.services.engine import run_execution, start_execution

logger = logging.getLogger("hooks")
router = APIRouter(prefix="/hooks", tags=["webhook trigger"])

# Per token, not per IP: one noisy integration must not throttle the others.
hook_limit = RateLimiter(times=120, seconds=60, scope="hook")


@router.post(
    "/{token}",
    response_model=WebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a workflow",
    responses={
        401: {"description": "Signature required or invalid"},
        404: {"description": "No workflow for this token"},
        409: {"description": "Workflow is disabled"},
        413: {"description": "Payload too large"},
        422: {"description": "Body is not valid JSON"},
    },
)
async def trigger(
    request: Request,
    background: BackgroundTasks,
    token: str = Path(min_length=16, max_length=64),
    signature: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
) -> WebhookAccepted:
    hook_limit.check(f"hook:{token[:16]}")

    raw = await request.body()
    if len(raw) > settings.max_payload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Payload exceeds {settings.max_payload_bytes} bytes.",
        )

    workflow = db.execute(
        select(Workflow).where(Workflow.token == token)
    ).scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No workflow for this token.")
    if not workflow.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "This workflow is disabled.")

    # Signature is checked over the exact bytes received, before parsing.
    if workflow.signing_secret and not verify_body_signature(
        raw, workflow.signing_secret, signature
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing or invalid X-Hub-Signature-256 header.",
        )

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"Body must be JSON: {exc.msg}") from exc
    if not isinstance(payload, (dict, list)):
        raise HTTPException(422, "Body must be a JSON object or array.")

    execution = start_execution(db, workflow, payload)
    background.add_task(run_execution, execution.id)
    logger.info("Queued execution %s for workflow %s", execution.id, workflow.id)

    return WebhookAccepted(execution_id=execution.id, workflow=workflow.name)
