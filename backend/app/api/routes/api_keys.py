"""API key management. The raw key is returned exactly once."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import generate_api_key
from app.db.session import get_db
from app.models import APIKey, User
from app.schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyOut

router = APIRouter(prefix="/api/api-keys", tags=["api keys"])

MAX_KEYS_PER_USER = 10


@router.get("", response_model=list[APIKeyOut], summary="List API keys")
def list_keys(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[APIKey]:
    return list(
        db.execute(
            select(APIKey)
            .where(APIKey.user_id == user.id)
            .order_by(APIKey.created_at.desc())
        ).scalars().all()
    )


@router.post(
    "",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key",
)
def create_key(
    payload: APIKeyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIKeyCreated:
    active = [key for key in user.api_keys if key.active]
    if len(active) >= MAX_KEYS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You already have {MAX_KEYS_PER_USER} active keys. Revoke one first.",
        )

    raw, prefix, digest = generate_api_key()
    api_key = APIKey(user_id=user.id, name=payload.name, prefix=prefix, hashed_key=digest)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    # `raw` is not stored anywhere; this response is the only place it exists.
    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        active=api_key.active,
        created_at=api_key.created_at,
        last_used_at=None,
        key=raw,
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
def revoke_key(
    key_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    api_key = db.get(APIKey, key_id)
    if api_key is None or api_key.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found.")

    # Revoked rather than deleted: last_used_at stays readable as an audit hint.
    api_key.active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
