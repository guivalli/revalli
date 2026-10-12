import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import admin_user, current_user, get_membership, require_lead
from revalli.models import AIProvider, AIUsage, Record, User
from revalli.modules.ai import client, host
from revalli.modules.ai.active import screening_curve
from revalli.modules.ai.client import AIError, Endpoint
from revalli.modules.ai.crypto import decrypt, encrypt
from revalli.modules.ai.protocol import apply_reason_groups
from revalli.modules.ai.schemas import (
    ApplyReasonsIn,
    Calibration,
    Curve,
    Estimate,
    FlagOut,
    InstanceAISettings,
    OllamaAction,
    OllamaState,
    OrganizeIn,
    ProjectAISettings,
    ProviderIn,
    ProviderOut,
    RunIn,
    SuggestionOut,
    TagSuggestIn,
    UsageOut,
)
from revalli.modules.ai.service import (
    bot_user,
    calibration,
    estimate,
    instance_ai,
    latest_suggestions,
    project_ai,
    resolve,
    save_instance_ai,
)
from revalli.modules.projects.models import Role
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.schemas import JobOut
from revalli.modules.screening.models import Phase
from revalli.modules.screening.router import _item
from revalli.modules.screening.service import State, compute_states, get_settings

router = APIRouter(tags=["ai"])


def _ai_error(exc: AIError) -> HTTPException:
    code = str(exc)
    if code in ("not_configured", "local_only"):
        return HTTPException(409, f"ai_{code}")
    return HTTPException(502, "ai_provider_error")


# --- Provedores (administração da instalação) ------------------------------------


@router.get("/ai/providers", response_model=list[ProviderOut])
async def list_providers(_: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(AIProvider).order_by(AIProvider.name))).scalars().all()


def _apply(p: AIProvider, body: ProviderIn) -> None:
    p.name, p.kind, p.base_url, p.is_local = body.name, body.kind, body.base_url, body.is_local
    if body.clear_api_key:
        p.api_key_enc, p.api_key_hint = "", ""
    elif body.api_key:
        p.api_key_enc = encrypt(body.api_key)
        p.api_key_hint = "…" + body.api_key[-4:]


@router.post("/ai/providers", response_model=ProviderOut, status_code=201)
async def create_provider(
    body: ProviderIn, _: User = Depends(admin_user), db: AsyncSession = Depends(get_db)
):
    p = AIProvider()
    _apply(p, body)
    db.add(p)
    await db.commit()
    return p


async def _provider(db: AsyncSession, provider_id: uuid.UUID) -> AIProvider:
    p = await db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(404, "provider_not_found")
    return p


@router.put("/ai/providers/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: uuid.UUID,
    body: ProviderIn,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    p = await _provider(db, provider_id)
    _apply(p, body)
    await db.commit()
    return p


@router.delete("/ai/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: uuid.UUID, _: User = Depends(admin_user), db: AsyncSession = Depends(get_db)
):
    await _provider(db, provider_id)
    await db.execute(delete(AIProvider).where(AIProvider.id == provider_id))
    settings = await instance_ai(db)
    for task in ("screening", "embeddings"):
        if getattr(settings, task).provider_id == provider_id:
            getattr(settings, task).provider_id = None
    await save_instance_ai(db, settings)
    await db.commit()


@router.post("/ai/providers/{provider_id}/test", response_model=list[str])
async def test_provider(
    provider_id: uuid.UUID, _: User = Depends(admin_user), db: AsyncSession = Depends(get_db)
):
    """Lista os modelos do provedor; serve para conferir endereço e chave."""
    p = await _provider(db, provider_id)
    try:
        return await client.list_models(
            Endpoint(base_url=p.base_url, api_key=decrypt(p.api_key_enc), model="")
        )
    except AIError as exc:
        raise HTTPException(502, f"ai_provider_error: {exc}") from exc


@router.get("/ai/settings", response_model=InstanceAISettings)
async def read_instance_settings(
    _: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    return await instance_ai(db)


@router.put("/ai/settings", response_model=InstanceAISettings)
async def write_instance_settings(
    body: InstanceAISettings, _: User = Depends(admin_user), db: AsyncSession = Depends(get_db)
):
    for task in ("screening", "embeddings"):
        pid = getattr(body, task).provider_id
        if pid is not None:
            await _provider(db, pid)
    await save_instance_ai(db, body)
    await db.commit()
    return body


# --- Ollama do computador ------------------------------------------------------------


async def _ollama_state(method: str, path: str) -> OllamaState:
    if not host.configured():
        return OllamaState(configured=False)
    try:
        data = await host.call(method, path)
    except host.HelperError as exc:
        return OllamaState(configured=True, error=str(exc))
    return OllamaState(
        configured=True,
        reachable=True,
        active=bool(data.get("active")),
        state=str(data.get("state", "")),
        enabled=bool(data.get("enabled")),
        error=data.get("error") if data.get("ok") is False else None,
    )


@router.get("/ai/local/ollama", response_model=OllamaState)
async def ollama_status(_: User = Depends(admin_user)):
    return await _ollama_state("GET", "/status")


@router.post("/ai/local/ollama", response_model=OllamaState)
async def ollama_action(body: OllamaAction, _: User = Depends(admin_user)):
    if not host.configured():
        raise HTTPException(409, "ollama_helper_not_configured")
    return await _ollama_state("POST", f"/{body.action}")


# --- Projeto --------------------------------------------------------------------------

project_router = APIRouter(prefix="/projects/{project_id}/ai", tags=["ai"])


@project_router.get("/settings", response_model=ProjectAISettings)
async def read_project_settings(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    return project_ai(project)


@project_router.put("/settings", response_model=ProjectAISettings)
async def write_project_settings(
    project_id: uuid.UUID,
    body: ProjectAISettings,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await require_lead(db, project_id, user)
    project.settings = {**(project.settings or {}), "ai": body.model_dump()}
    await db.commit()
    return body


async def _enabled_project(db, project_id, user):
    project = await require_lead(db, project_id, user)
    if not project_ai(project).enabled:
        raise HTTPException(409, "ai_disabled")
    return project


def _require_criteria(project) -> None:
    """Sem critérios a IA não tem o que aplicar: a interface leva a pessoa ao protocolo."""
    st = get_settings(project)
    if not (st.inclusion_criteria.strip() or st.exclusion_criteria.strip() or st.criteria_items):
        raise HTTPException(409, "criteria_missing")


@project_router.post("/estimate", response_model=Estimate)
async def estimate_run(
    project_id: uuid.UUID,
    body: RunIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _enabled_project(db, project_id, user)
    _require_criteria(project)
    try:
        out = await estimate(db, project, Phase(body.phase), body.scope, body.limit, body.force)
    except AIError as exc:
        raise _ai_error(exc) from exc
    await db.commit()  # a conta da IA pode ter sido criada agora
    return out


@project_router.post("/run", response_model=JobOut, status_code=202)
async def start_run(
    project_id: uuid.UUID,
    body: RunIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _enabled_project(db, project_id, user)
    _require_criteria(project)
    try:
        res = await resolve(db, "screening", project_ai(project).local_only)
    except AIError as exc:
        raise _ai_error(exc) from exc
    job = await create_job(db, project_id, "ai_screen", body.model_dump())
    await dispatch(db, job, queue="gpu" if res.provider.is_local else "remote")
    return job


@project_router.post("/criteria/organize", response_model=JobOut, status_code=202)
async def organize(
    project_id: uuid.UUID,
    body: OrganizeIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """A IA detalha os critérios escritos pela equipe. O resultado fica no job; nada é salvo
    até a equipe revisar e gravar o protocolo."""
    project = await _enabled_project(db, project_id, user)
    try:
        res = await resolve(db, "screening", project_ai(project).local_only)
    except AIError as exc:
        raise _ai_error(exc) from exc
    job = await create_job(db, project_id, "ai_criteria", body.model_dump())
    await dispatch(db, job, queue="gpu" if res.provider.is_local else "remote")
    return job


@project_router.post("/tags/suggest", response_model=JobOut, status_code=202)
async def suggest_vocabulary(
    project_id: uuid.UUID,
    body: TagSuggestIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _enabled_project(db, project_id, user)
    try:
        res = await resolve(db, "screening", project_ai(project).local_only)
    except AIError as exc:
        raise _ai_error(exc) from exc
    job = await create_job(db, project_id, "ai_tags", body.model_dump())
    await dispatch(db, job, queue="gpu" if res.provider.is_local else "remote")
    return job


@project_router.post("/reasons/organize", response_model=JobOut, status_code=202)
async def organize_exclusion_reasons(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Agrupa os motivos de exclusão propostos pela IA. O resultado fica no job até a equipe
    aplicar."""
    project = await _enabled_project(db, project_id, user)
    try:
        res = await resolve(db, "screening", project_ai(project).local_only)
    except AIError as exc:
        raise _ai_error(exc) from exc
    job = await create_job(db, project_id, "ai_reasons")
    await dispatch(db, job, queue="gpu" if res.provider.is_local else "remote")
    return job


@project_router.post("/reasons/apply", response_model=dict)
async def apply_exclusion_reasons(
    project_id: uuid.UUID,
    body: ApplyReasonsIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await require_lead(db, project_id, user)
    return await apply_reason_groups(db, project, [(g.label, g.members) for g in body.groups])


@project_router.get("/{phase}/suggestions", response_model=list[SuggestionOut])
async def suggestions(
    project_id: uuid.UUID,
    phase: Phase,
    ids: str = Query("", max_length=40_000),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sugestões da IA. Por padrão, revisores só veem a sugestão depois de decidir, para não se
    ancorarem nela; o projeto pode liberar antes. Líderes e árbitros veem todas."""
    project, role = await get_membership(db, project_id, user)
    try:
        wanted = [uuid.UUID(x) for x in ids.split(",") if x.strip()][:500]
    except ValueError as exc:
        raise HTTPException(422, "invalid_ids") from exc
    sugs = await latest_suggestions(db, project_id, phase, wanted or None)
    reveal_first = project_ai(project).reveal_suggestions == "before"
    if role not in (Role.lead, Role.arbitrator) and not user.is_admin and not reveal_first:
        states = await compute_states(db, project, phase, list(sugs))
        sugs = {rid: s for rid, s in sugs.items() if user.id in states[rid].votes}
    return list(sugs.values())


@project_router.get("/{phase}/calibration", response_model=Calibration)
async def read_calibration(
    project_id: uuid.UUID,
    phase: Phase,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    out = await calibration(db, project, phase)
    await db.commit()
    return out


@project_router.get("/{phase}/flags", response_model=list[FlagOut])
async def flags(
    project_id: uuid.UUID,
    phase: Phase,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Registros excluídos pelos humanos que a IA incluiria: vale uma segunda olhada."""
    project, role = await get_membership(db, project_id, user)
    if role not in (Role.lead, Role.arbitrator) and not user.is_admin:
        raise HTTPException(403, "lead_or_arbitrator_only")
    states = await compute_states(db, project, phase)
    excluded = [rid for rid, st in states.items() if st.state == State.excluded]
    sugs = await latest_suggestions(db, project_id, phase, excluded)
    flagged = {rid: s for rid, s in sugs.items() if s.decision != "exclude"}
    records = (await db.execute(select(Record).where(Record.id.in_(list(flagged))))).scalars()
    return [
        FlagOut(record=_item(r), suggestion=SuggestionOut.model_validate(flagged[r.id]))
        for r in records
    ]


@project_router.get("/usage", response_model=UsageOut)
async def usage(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(AIUsage.cost_usd), 0.0),
                func.coalesce(func.sum(AIUsage.input_tokens), 0),
                func.coalesce(func.sum(AIUsage.output_tokens), 0),
                func.count(),
            ).where(AIUsage.project_id == project_id)
        )
    ).one()
    return UsageOut(
        spent_usd=round(float(row[0]), 4), input_tokens=row[1], output_tokens=row[2], calls=row[3]
    )


@project_router.get("/bot", response_model=dict)
async def bot_info(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Identificador da conta da IA, para a interface marcar os votos dela."""
    await get_membership(db, project_id, user)
    bot = await bot_user(db)
    await db.commit()
    return {"user_id": str(bot.id)}


@project_router.post("/embed", response_model=JobOut, status_code=202)
async def start_embed(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project = await _enabled_project(db, project_id, user)
    try:
        res = await resolve(db, "embeddings", project_ai(project).local_only)
    except AIError as exc:
        raise _ai_error(exc) from exc
    job = await create_job(db, project_id, "ai_embed")
    await dispatch(db, job, queue="gpu" if res.provider.is_local else "remote")
    return job


@project_router.get("/curve", response_model=Curve)
async def curve(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    out = await screening_curve(db, project)
    await db.commit()
    return out
