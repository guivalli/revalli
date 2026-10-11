import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import Project, User
from revalli.modules.ai.client import AIError
from revalli.modules.ai.router import _ai_error
from revalli.modules.ai.service import project_ai, resolve
from revalli.modules.extraction import ai, service
from revalli.modules.extraction.models import Extraction, ExtractionForm, FormVersion
from revalli.modules.extraction.schemas import (
    AIRunIn,
    Comparison,
    ExtractionIn,
    ExtractionOut,
    FormFromTemplate,
    FormIn,
    FormOut,
    RobSummary,
    UnitDetail,
    UnitOut,
)
from revalli.modules.extraction.templates import TEMPLATES
from revalli.modules.fulltext.models import RecordFile
from revalli.modules.projects.models import Role
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.schemas import JobOut
from revalli.modules.reports.router import _slug

router = APIRouter(prefix="/projects/{project_id}/extraction", tags=["extraction"])

EXTRACT_ROLES = {Role.lead, Role.reviewer, Role.extractor}
RESOLVE_ROLES = {Role.lead, Role.arbitrator}


async def _form(db: AsyncSession, project_id: uuid.UUID, form_id: uuid.UUID) -> ExtractionForm:
    form = await db.get(ExtractionForm, form_id)
    if form is None or form.project_id != project_id or form.archived:
        raise HTTPException(404, "form_not_found")
    return form


def _can_extract(user: User, role: Role | None) -> bool:
    return user.is_admin or role in EXTRACT_ROLES


def _can_resolve(user: User, role: Role | None) -> bool:
    return user.is_admin or role in RESOLVE_ROLES


async def _resolver(db: AsyncSession, project_id: uuid.UUID, user: User) -> Project:
    """Resultados consolidados mostram as respostas de todos: só líderes e árbitros."""
    project, role = await get_membership(db, project_id, user)
    if not _can_resolve(user, role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "lead_or_arbitrator_only")
    return project


def _unit_out(form: ExtractionForm, u: service.Unit, user: User) -> dict:
    exts = u.extractions
    mine = next((e for e in exts if e.kind == "reviewer" and e.user_id == user.id), None)
    return {
        "record_id": u.record.id,
        "report_ids": u.report_ids,
        "label": u.label,
        "title": u.record.title,
        "year": u.record.year,
        "done": sum(1 for e in exts if e.kind == "reviewer" and e.status == "done"),
        "mine": mine.status if mine else None,
        "has_ai": any(e.kind == "ai" for e in exts),
        "consensus": any(e.kind == "consensus" for e in exts),
        "state": service.unit_state(form, exts),
    }


async def _new_version(db: AsyncSession, form: ExtractionForm, user: User) -> None:
    db.add(
        FormVersion(
            form_id=form.id, version=form.version, fields=form.fields, created_by_id=user.id
        )
    )


@router.get("/forms", response_model=list[FormOut])
async def list_forms(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = await db.execute(
        select(ExtractionForm)
        .where(ExtractionForm.project_id == project_id, ExtractionForm.archived.is_(False))
        .order_by(ExtractionForm.created_at)
    )
    return rows.scalars().all()


@router.post("/forms", response_model=FormOut, status_code=201)
async def create_form(
    project_id: uuid.UUID,
    body: FormIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    form = ExtractionForm(
        project_id=project_id,
        name=body.name,
        kind=body.kind,
        fields=[f.model_dump() for f in body.fields],
        extractors=body.extractors,
    )
    db.add(form)
    await db.flush()
    await _new_version(db, form, user)
    await db.commit()
    return form


@router.post("/forms/template", response_model=FormOut, status_code=201)
async def create_from_template(
    project_id: uuid.UUID,
    body: FormFromTemplate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    tpl = TEMPLATES[body.template]
    # Passa pela validação dos campos, como um formulário feito à mão
    fields = FormIn(name="x", kind=tpl["kind"], fields=tpl["fields"]()).fields
    form = ExtractionForm(
        project_id=project_id,
        name=body.name or tpl["name"],
        kind=tpl["kind"],
        template=body.template,
        fields=[f.model_dump() for f in fields],
        extractors=body.extractors,
    )
    db.add(form)
    await db.flush()
    await _new_version(db, form, user)
    await db.commit()
    return form


@router.get("/forms/{form_id}", response_model=FormOut)
async def get_form(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    return await _form(db, project_id, form_id)


@router.put("/forms/{form_id}", response_model=FormOut)
async def update_form(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    body: FormIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    form = await _form(db, project_id, form_id)
    fields = [f.model_dump() for f in body.fields]
    if fields != form.fields:
        form.fields = fields
        form.version += 1
        await _new_version(db, form, user)
    form.name, form.kind, form.extractors = body.name, body.kind, body.extractors
    await db.commit()
    return form


@router.delete("/forms/{form_id}", status_code=204)
async def delete_form(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    form = await _form(db, project_id, form_id)
    # Os dados extraídos ficam guardados; o formulário só sai da lista
    form.archived = True
    await db.commit()
    return Response(status_code=204)


@router.get("/forms/{form_id}/units", response_model=list[UnitOut])
async def list_units(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    form = await _form(db, project_id, form_id)
    us = await service.units(db, project)
    exts = await service.load_extractions(db, form, [u.record.id for u in us])
    for u in us:
        u.extractions = exts.get(u.record.id, [])
    return [_unit_out(form, u, user) for u in us]


async def _unit(db, project: Project, form: ExtractionForm, record_id: uuid.UUID):
    u = await service.unit_for(db, project, record_id)
    if u is None:
        raise HTTPException(404, "study_not_found")
    u.extractions = (await service.load_extractions(db, form, [record_id])).get(record_id, [])
    return u


@router.get("/forms/{form_id}/units/{record_id}", response_model=UnitDetail)
async def get_unit(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    record_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, role = await get_membership(db, project_id, user)
    form = await _form(db, project_id, form_id)
    u = await _unit(db, project, form, record_id)
    names = await service.user_names(db, {e.user_id for e in u.extractions})
    mine = next((e for e in u.extractions if e.kind == "reviewer" and e.user_id == user.id), None)
    see = _can_resolve(user, role) or (mine is not None and mine.status == "done")
    others = [e for e in u.extractions if e.kind == "reviewer" and e is not mine]
    ai_ext = next((e for e in u.extractions if e.kind == "ai"), None)
    cons = next((e for e in u.extractions if e.kind == "consensus"), None)
    files = await db.execute(
        select(RecordFile)
        .where(RecordFile.record_id.in_(u.report_ids))
        .order_by(RecordFile.is_main.desc(), RecordFile.created_at)
    )
    return {
        "unit": _unit_out(form, u, user),
        "files": files.scalars().all(),
        "form": form,
        "mine": service.extraction_out(form, mine, names) if mine else None,
        "ai": service.extraction_out(form, ai_ext, names) if ai_ext else None,
        "others": [service.extraction_out(form, e, names) for e in others] if see else [],
        "consensus": service.extraction_out(form, cons, names) if cons and see else None,
        "can_see_others": see,
        "can_resolve": _can_resolve(user, role),
    }


async def _save(
    db: AsyncSession,
    form: ExtractionForm,
    ext: Extraction,
    body: ExtractionIn,
) -> None:
    try:
        values = service.clean_values(form.fields, body.values)
    except service.FieldError as exc:
        raise HTTPException(422, f"invalid_field: {exc.field_id}") from exc
    if body.status == "done" and (missing := service.missing_required(form.fields, values)):
        raise HTTPException(422, f"required_missing: {', '.join(missing)}")
    ext.values = values
    ext.quotes = {k: q.model_dump(mode="json") for k, q in body.quotes.items() if k in values}
    ext.status = body.status
    ext.form_version = form.version


@router.put("/forms/{form_id}/units/{record_id}/mine", response_model=ExtractionOut)
async def save_mine(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    record_id: uuid.UUID,
    body: ExtractionIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, role = await get_membership(db, project_id, user)
    if not _can_extract(user, role):
        raise HTTPException(403, "cannot_extract")
    form = await _form(db, project_id, form_id)
    u = await _unit(db, project, form, record_id)
    ext = next((e for e in u.extractions if e.kind == "reviewer" and e.user_id == user.id), None)
    if ext is None:
        ext = Extraction(
            project_id=project_id, form_id=form.id, record_id=record_id, user_id=user.id
        )
        db.add(ext)
    await _save(db, form, ext, body)
    await db.commit()
    await db.refresh(ext)
    return service.extraction_out(form, ext, {user.id: user.full_name})


@router.get("/forms/{form_id}/units/{record_id}/compare", response_model=Comparison)
async def compare_unit(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    record_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, role = await get_membership(db, project_id, user)
    form = await _form(db, project_id, form_id)
    u = await _unit(db, project, form, record_id)
    mine = next((e for e in u.extractions if e.kind == "reviewer" and e.user_id == user.id), None)
    if not (_can_resolve(user, role) or (mine and mine.status == "done")):
        raise HTTPException(403, "finish_first")
    done = [e for e in u.extractions if e.kind != "consensus" and e.status == "done"]
    rows, agreed = service.compare(form.fields, done)
    names = await service.user_names(db, {e.user_id for e in done})
    return {
        "extractions": [service.extraction_out(form, e, names) for e in done],
        "fields": rows,
        "agreed_values": agreed,
    }


@router.put("/forms/{form_id}/units/{record_id}/consensus", response_model=ExtractionOut)
async def save_consensus(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    record_id: uuid.UUID,
    body: ExtractionIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, role = await get_membership(db, project_id, user)
    if not _can_resolve(user, role):
        raise HTTPException(403, "lead_or_arbitrator_only")
    form = await _form(db, project_id, form_id)
    u = await _unit(db, project, form, record_id)
    ext = next((e for e in u.extractions if e.kind == "consensus"), None)
    if ext is None:
        ext = Extraction(
            project_id=project_id, form_id=form.id, record_id=record_id, kind="consensus"
        )
        db.add(ext)
    ext.user_id = user.id
    await _save(db, form, ext, body.model_copy(update={"status": "done"}))
    await db.commit()
    await db.refresh(ext)
    return service.extraction_out(form, ext, {user.id: user.full_name})


@router.delete("/forms/{form_id}/units/{record_id}/consensus", status_code=204)
async def delete_consensus(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    record_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _, role = await get_membership(db, project_id, user)
    if not _can_resolve(user, role):
        raise HTTPException(403, "lead_or_arbitrator_only")
    form = await _form(db, project_id, form_id)
    ext = (
        await db.execute(
            select(Extraction).where(
                Extraction.form_id == form.id,
                Extraction.record_id == record_id,
                Extraction.kind == "consensus",
            )
        )
    ).scalar_one_or_none()
    if ext is not None:
        await db.delete(ext)
        await db.commit()
    return Response(status_code=204)


@router.get("/forms/{form_id}/export")
async def export(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    layout: Literal["wide", "long"] = Query("wide"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _resolver(db, project_id, user)
    form = await _form(db, project_id, form_id)
    body = await service.export_csv(db, project, form, layout)
    name = f"{_slug(project.title)}-{_slug(form.name)}-{layout}.csv"
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/forms/{form_id}/rob", response_model=RobSummary)
async def rob(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _resolver(db, project_id, user)
    form = await _form(db, project_id, form_id)
    return await service.rob_summary(db, project, form)


@router.post("/forms/{form_id}/ai", response_model=JobOut, status_code=202)
async def run_ai(
    project_id: uuid.UUID,
    form_id: uuid.UUID,
    body: AIRunIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """A IA extrai os campos marcados como "IA pode preencher". O resultado entra como mais uma
    extração, que aparece na comparação ao lado das humanas."""
    project = await require_lead(db, project_id, user)
    form = await _form(db, project_id, form_id)
    ai_settings = project_ai(project)
    if not ai_settings.enabled:
        raise HTTPException(409, "ai_disabled")
    if not ai.ai_fields(form):
        raise HTTPException(409, "no_ai_fields")
    try:
        res = await resolve(db, "extraction", ai_settings.local_only)
    except AIError as exc:
        raise _ai_error(exc) from exc
    params = {
        "form_id": str(form.id),
        "record_ids": [str(r) for r in body.record_ids],
        "overwrite": body.overwrite,
    }
    job = await create_job(db, project_id, "ai_extract", params)
    await dispatch(db, job, queue="gpu" if res.provider.is_local else "remote")
    return job
