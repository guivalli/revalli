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
from revalli.modules.sources import catalog, fields, keys, service
from revalli.modules.sources.clients import SourceError
from revalli.modules.sources.schemas import (
    AssistChat,
    AssistIn,
    AssistOut,
    DatabaseInfo,
    DatabasesIn,
    DatabasesOut,
    PreviewOut,
    QueryIn,
    SampleRecord,
    SearchIn,
    SnowballIn,
    SnowballInfo,
    SourceFields,
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
    if msg.startswith("semantic_scholar_key_needed"):
        return HTTPException(502, f"semantic_scholar_key_needed: {msg[:600]}")
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


def _rows(body: QueryIn) -> list[fields.Row] | None:
    if body.rows is None:
        return None
    return [fields.Row(term=r.term, field=r.field, op=r.op) for r in body.rows]


def _databases_out(project) -> DatabasesOut:
    return DatabasesOut(
        enabled=catalog.enabled(project.settings),
        saved=bool(((project.settings or {}).get("databases") or {}).get("enabled")),
        catalog=[DatabaseInfo(id=d.id, direct=d.direct) for d in catalog.DATABASES],
        packs={k: list(v) for k, v in catalog.PACKS.items()},
    )


@router.get("/databases", response_model=DatabasesOut)
async def read_databases(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """As bases escolhidas do projeto, o catálogo e os pacotes por área."""
    return _databases_out(await require_lead(db, project_id, user))


@router.put("/databases", response_model=DatabasesOut)
async def write_databases(
    project_id: uuid.UUID,
    body: DatabasesIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await require_lead(db, project_id, user)
    chosen = [d for d in catalog.IDS if d in body.enabled]
    # Troca o objeto inteiro: o JSONB só grava quando a referência muda
    project.settings = {**(project.settings or {}), "databases": {"enabled": chosen}}
    await db.commit()
    return _databases_out(project)


@router.get("/fields", response_model=dict[str, SourceFields])
async def source_fields(
    project_id: uuid.UUID, user: User = Depends(current_user), db=Depends(get_db)
):
    """Os campos que cada base aceita no construtor de busca."""
    await require_lead(db, project_id, user)
    return {
        name: SourceFields(
            fields=fields.available_fields(name), or_across_fields=fields.mixes_fields_with_or(name)
        )
        for name in fields.BY_SOURCE
    }


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
        result = await service.preview(db, body.source, body.query, _rows(body))
    except SourceError as exc:
        raise _source_error(exc) from exc
    return PreviewOut(
        count=result.count,
        max=get_settings().api_search_max,
        translation=result.translation,
        warnings=result.warnings,
        corrections=result.corrections,
        strategy=result.strategy,
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
        "rows": [r.model_dump() for r in body.rows or [] if r.term.strip()],
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
