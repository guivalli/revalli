import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db, utcnow
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import User
from revalli.modules.ai.crypto import encrypt
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.schemas import JobOut
from revalli.modules.watches.models import Watch
from revalli.modules.watches.schemas import WatchIn, WatchOut

router = APIRouter(prefix="/projects/{project_id}/watches", tags=["watches"])

MAX_WATCHES = 20


def _out(w: Watch) -> WatchOut:
    out = WatchOut.model_validate(w)
    out.has_secret = bool(w.secret_enc)
    return out


async def _get(db: AsyncSession, project_id: uuid.UUID, watch_id: uuid.UUID) -> Watch:
    w = await db.get(Watch, watch_id)
    if w is None or w.project_id != project_id:
        raise HTTPException(404, "watch_not_found")
    return w


def _apply(w: Watch, body: WatchIn) -> None:
    w.kind, w.name, w.source = body.kind, body.name.strip(), body.source
    w.query, w.url, w.every_days, w.enabled = (
        body.query.strip(),
        body.url,
        body.every_days,
        body.enabled,
    )
    if body.clear_secret:
        w.secret_enc = ""
    elif body.secret:
        w.secret_enc = encrypt(body.secret)


@router.get("", response_model=list[WatchOut])
async def list_watches(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = await db.execute(
        select(Watch).where(Watch.project_id == project_id).order_by(Watch.created_at)
    )
    return [_out(w) for w in rows.scalars()]


@router.post("", response_model=WatchOut, status_code=201)
async def create_watch(
    project_id: uuid.UUID,
    body: WatchIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    if not get_settings().search_apis_enabled:
        raise HTTPException(409, "search_apis_disabled")
    n = len((await db.execute(select(Watch.id).where(Watch.project_id == project_id))).all())
    if n >= MAX_WATCHES:
        raise HTTPException(409, "too_many_watches")
    w = Watch(project_id=project_id, created_by_id=user.id)
    _apply(w, body)
    # A primeira execução é na próxima passada do agendador (ou em "Rodar agora")
    w.next_run_at = utcnow() + timedelta(days=w.every_days)
    db.add(w)
    await db.commit()
    return _out(w)


@router.put("/{watch_id}", response_model=WatchOut)
async def update_watch(
    project_id: uuid.UUID,
    watch_id: uuid.UUID,
    body: WatchIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    w = await _get(db, project_id, watch_id)
    _apply(w, body)
    await db.commit()
    return _out(w)


@router.delete("/{watch_id}", status_code=204)
async def delete_watch(
    project_id: uuid.UUID,
    watch_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    await db.delete(await _get(db, project_id, watch_id))
    await db.commit()


@router.post("/{watch_id}/run", response_model=JobOut, status_code=202)
async def run_now(
    project_id: uuid.UUID,
    watch_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    w = await _get(db, project_id, watch_id)
    job = await create_job(db, project_id, "watch_run", {"watch_id": str(w.id)})
    await dispatch(db, job, queue="remote")
    return job
