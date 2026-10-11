import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db, utcnow
from revalli.core.deps import current_user, get_membership
from revalli.core.security import hash_token, new_token
from revalli.models import User
from revalli.modules.tokens.models import ApiToken
from revalli.modules.tokens.schemas import TokenCreated, TokenIn, TokenOut

router = APIRouter(prefix="/tokens", tags=["tokens"])

TOKEN_PREFIX = "rvl_"
MAX_TOKENS = 20


@router.get("", response_model=list[TokenOut])
async def list_tokens(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc())
    )
    return rows.scalars().all()


@router.post("", response_model=TokenCreated, status_code=201)
async def create_token(
    body: TokenIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Cria uma chave de leitura. Só uma sessão da interface cria chaves, nunca outra chave."""
    if body.project_id is not None:
        await get_membership(db, body.project_id, user)
    existing = (
        (await db.execute(select(ApiToken.id).where(ApiToken.user_id == user.id))).scalars().all()
    )
    if len(existing) >= MAX_TOKENS:
        raise HTTPException(409, "too_many_tokens")
    value = TOKEN_PREFIX + new_token()
    row = ApiToken(
        user_id=user.id,
        project_id=body.project_id,
        name=body.name.strip(),
        token_hash=hash_token(value),
        prefix=value[:10],
        expires_at=utcnow() + timedelta(days=body.expires_in_days)
        if body.expires_in_days
        else None,
    )
    db.add(row)
    await db.commit()
    return TokenCreated(**TokenOut.model_validate(row).model_dump(), token=value)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    row = await db.get(ApiToken, token_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "token_not_found")
    await db.delete(row)
    await db.commit()
