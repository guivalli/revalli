import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db
from revalli.core.deps import admin_user, current_user, require_lead
from revalli.models import Job, Record, User
from revalli.modules.ai.client import AIError
from revalli.modules.ai.router import _ai_error
from revalli.modules.ai.service import project_ai
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.models import JobStatus
from revalli.modules.records.schemas import JobOut
from revalli.modules.sources import keys, service
from revalli.modules.sources.clients import SourceError
from revalli.modules.sources.schemas import (
    AssistChat,
    AssistIn,
    AssistOut,
    PreviewOut,
    QueryIn,
    SampleRecord,
    SearchIn,
    SnowballIn,
    SnowballInfo,
    SourcesSettingsIn,
    SourcesSettingsOut,
    TranslateIn,
    TranslateOut,
)

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["sources"])
# Configuração da instalação (só administradores)
admin_router = APIRouter(prefix="/sources", tags=["sources"])


async def _settings_out(db: AsyncSession) -> SourcesSettingsOut:
    await keys.load(db)
    value = keys.openalex_key()
    return SourcesSettingsOut(
        openalex_key_set=bool(value),
        openalex_key_hint=keys.hint(value),
        openalex_key_source=keys.source(),
    )


@admin_router.get("/settings", response_model=SourcesSettingsOut)
async def read_settings(_: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    return await _settings_out(db)


@admin_router.put("/settings", response_model=SourcesSettingsOut)
async def write_settings(
    body: SourcesSettingsIn, _: User = Depends(admin_user), db: AsyncSession = Depends(get_db)
):
    value = body.openalex_api_key.strip()
    if value and not value.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(422, "openalex_key_invalid")
    if value or body.clear_openalex_key:
        await keys.save(db, value)
        await db.commit()
    return await _settings_out(db)


def _source_error(exc: SourceError) -> HTTPException:
    msg = str(exc)
    # O OpenAlex sem chave tem um orçamento diário gratuito por rede; a chave é grátis
    if "daily budget" in msg or "Insufficient budget" in msg:
        return HTTPException(502, f"openalex_key_needed: {msg[:600]}")
    return HTTPException(502, f"source_unavailable: {msg[:600]}")


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
        result = await service.preview(db, body.source, body.query)
    except SourceError as exc:
        raise _source_error(exc) from exc
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


@router.post("/assist", response_model=AssistOut)
async def assist(
    project_id: uuid.UUID,
    body: AssistIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conversa para montar a estratégia: a IA diz o que entendeu e propõe uma string por base."""
    project = await require_lead(db, project_id, user)
    if not project_ai(project).enabled:
        raise HTTPException(409, "ai_disabled")
    if body.messages[-1].role != "user":
        raise HTTPException(422, "last_message_must_be_user")
    history = [m.model_dump() for m in body.messages]
    try:
        out = await service.assist_search(db, project, history)
        # A conversa fica salva por pessoa e projeto: sobrevive a fechar a tela
        reply = {
            "role": "assistant",
            "content": out["reply"],
            "strategies": out["strategies"],
            "model": out["model"],
        }
        await service.save_chat(db, project_id, user.id, [*history, reply])
        await db.commit()
        return out
    except AIError as exc:
        raise _ai_error(exc) from exc
    except service.TranslationError as exc:
        raise HTTPException(409 if str(exc) == "budget_exceeded" else 502, f"ai_{exc}") from exc


@router.get("/assist", response_model=AssistChat)
async def assist_chat(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """A conversa salva da pessoa com o assistente neste projeto."""
    await require_lead(db, project_id, user)
    return AssistChat(messages=await service.load_chat(db, project_id, user.id))


@router.delete("/assist", status_code=204)
async def assist_chat_reset(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_lead(db, project_id, user)
    await service.clear_chat(db, project_id, user.id)
    await db.commit()


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
