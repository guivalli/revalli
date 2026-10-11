import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db
from revalli.core.deps import current_user, require_lead
from revalli.models import Job, Record, User
from revalli.modules.ai.client import AIError
from revalli.modules.ai.router import _ai_error
from revalli.modules.ai.service import project_ai
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.models import JobStatus
from revalli.modules.records.schemas import JobOut
from revalli.modules.sources import service
from revalli.modules.sources.clients import SourceError
from revalli.modules.sources.schemas import (
    PreviewOut,
    QueryIn,
    SampleRecord,
    SearchIn,
    SnowballIn,
    SnowballInfo,
    TranslateIn,
    TranslateOut,
)

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["sources"])


def _enabled() -> None:
    if not get_settings().search_apis_enabled:
        raise HTTPException(409, "search_apis_disabled")


async def _no_running(db: AsyncSession, project_id: uuid.UUID, kind: str) -> None:
    running = (
        await db.execute(
            select(Job.id).where(
                Job.project_id == project_id,
                Job.kind == kind,
                Job.status.in_([JobStatus.queued, JobStatus.running]),
            )
        )
    ).first()
    if running:
        raise HTTPException(409, "already_running")


@router.post("/preview", response_model=PreviewOut)
async def preview(
    project_id: uuid.UUID,
    body: QueryIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conta os resultados e mostra os primeiros, para conferir a string antes de importar."""
    await require_lead(db, project_id, user)
    _enabled()
    try:
        result = await service.preview(body.source, body.query)
    except SourceError as exc:
        raise HTTPException(502, "source_unavailable") from exc
    return PreviewOut(
        count=result.count,
        max=get_settings().api_search_max,
        translation=result.translation,
        warnings=result.warnings,
        sample=[
            SampleRecord(
                title=r.title,
                authors=r.authors[:3],
                year=r.year,
                journal=r.journal,
                doi=r.doi,
                pmid=r.pmid,
            )
            for r in result.sample
        ],
    )


@router.post("/search", response_model=JobOut, status_code=202)
async def search(
    project_id: uuid.UUID,
    body: SearchIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    _enabled()
    await _no_running(db, project_id, "api_search")
    params = {
        "source": body.source,
        "query": body.query,
        "limit": min(body.limit, get_settings().api_search_max),
        "user_id": str(user.id),
    }
    job = await create_job(db, project_id, "api_search", params)
    await dispatch(db, job, queue="remote")
    return job


@router.get("/snowball", response_model=SnowballInfo)
async def snowball_info(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project = await require_lead(db, project_id, user)
    return SnowballInfo(
        included=len(await service.included_ids(db, project)),
        enabled=get_settings().search_apis_enabled,
    )


@router.post("/snowball", response_model=JobOut, status_code=202)
async def snowball(
    project_id: uuid.UUID,
    body: SnowballIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Busca as referências (para trás) e os trabalhos que citam (para frente) as sementes."""
    project = await require_lead(db, project_id, user)
    _enabled()
    await _no_running(db, project_id, "snowball")
    if body.record_ids:
        count = (
            await db.execute(
                select(func.count()).where(
                    Record.project_id == project_id, Record.id.in_(body.record_ids)
                )
            )
        ).scalar_one()
        if count != len(set(body.record_ids)):
            raise HTTPException(404, "record_not_found")
    elif not await service.included_ids(db, project):
        raise HTTPException(409, "no_seeds")
    params = {
        "direction": body.direction,
        "record_ids": [str(r) for r in body.record_ids],
        "user_id": str(user.id),
    }
    job = await create_job(db, project_id, "snowball", params)
    await dispatch(db, job, queue="remote")
    return job


@router.post("/translate", response_model=TranslateOut)
async def translate(
    project_id: uuid.UUID,
    body: TranslateIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """A IA adapta a string de busca para a sintaxe de outra base. A pessoa sempre revisa."""
    project = await require_lead(db, project_id, user)
    if not project_ai(project).enabled:
        raise HTTPException(409, "ai_disabled")
    try:
        return await service.translate_query(db, project, body.query, body.target)
    except AIError as exc:
        raise _ai_error(exc) from exc
    except service.TranslationError as exc:
        raise HTTPException(409 if str(exc) == "budget_exceeded" else 502, f"ai_{exc}") from exc
