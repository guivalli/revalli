import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db, utcnow
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import Project, RecordFile, User
from revalli.modules.extraction.service import unit_for
from revalli.modules.projects.models import Role
from revalli.modules.synthesis import service
from revalli.modules.synthesis.checklists import CHECKLISTS
from revalli.modules.synthesis.models import ChecklistEntry, Code, Excerpt, ExcerptCode
from revalli.modules.synthesis.schemas import (
    ChecklistEntryIn,
    ChecklistEntryOut,
    ChecklistKind,
    ChecklistOut,
    CodeIn,
    CodeOut,
    CodePatch,
    CodingUnit,
    ExcerptIn,
    ExcerptOut,
    ExcerptPatch,
    Matrix,
    MergeIn,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["synthesis"])

CODE_ROLES = {Role.lead, Role.reviewer, Role.extractor}


async def _coder(db: AsyncSession, project_id: uuid.UUID, user: User) -> tuple[Project, bool]:
    """Quem pode codificar; devolve também se é líder (pode apagar e mesclar)."""
    project, role = await get_membership(db, project_id, user)
    if not (user.is_admin or role in CODE_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "coder_only")
    return project, user.is_admin or role == Role.lead


async def _code(db: AsyncSession, project_id: uuid.UUID, code_id: uuid.UUID) -> Code:
    code = await db.get(Code, code_id)
    if code is None or code.project_id != project_id:
        raise HTTPException(404, "code_not_found")
    return code


async def _check_codes(db: AsyncSession, project_id: uuid.UUID, ids: list[uuid.UUID]) -> None:
    found = (
        await db.execute(
            select(func.count()).where(Code.project_id == project_id, Code.id.in_(set(ids)))
        )
    ).scalar_one()
    if found != len(set(ids)):
        raise HTTPException(404, "code_not_found")


async def _labels(db: AsyncSession, project: Project) -> dict[uuid.UUID, str]:
    return {u.record.id: u.label for u in await service.coding_units(db, project)}


# --- Códigos ------------------------------------------------------------------------


@router.get("/coding/codes", response_model=list[CodeOut])
async def list_codes(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    counts = await service.excerpt_counts(db, project_id)
    out = []
    for c in await service.codes_of(db, project_id):
        item = CodeOut.model_validate(c)
        item.excerpts = counts.get(c.id, 0)
        out.append(item)
    return out


@router.post("/coding/codes", response_model=CodeOut, status_code=201)
async def create_code(
    project_id: uuid.UUID,
    body: CodeIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _coder(db, project_id, user)
    if body.parent_id:
        await _code(db, project_id, body.parent_id)
    position = (
        await db.execute(
            select(func.coalesce(func.max(Code.position) + 1, 0)).where(
                Code.project_id == project_id, Code.parent_id == body.parent_id
            )
        )
    ).scalar_one()
    code = Code(
        project_id=project_id,
        parent_id=body.parent_id,
        name=body.name.strip(),
        description=body.description,
        color=body.color,
        position=position,
        created_by_id=user.id,
    )
    db.add(code)
    await db.commit()
    return code


@router.patch("/coding/codes/{code_id}", response_model=CodeOut)
async def update_code(
    project_id: uuid.UUID,
    code_id: uuid.UUID,
    body: CodePatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _coder(db, project_id, user)
    code = await _code(db, project_id, code_id)
    if body.name is not None:
        code.name = body.name.strip()
    if body.description is not None:
        code.description = body.description
    if body.color is not None:
        code.color = body.color
    if body.position is not None:
        code.position = body.position
    if body.move:
        if body.parent_id is not None:
            await _code(db, project_id, body.parent_id)
            codes = await service.codes_of(db, project_id)
            # Um código não pode ir para dentro de si mesmo
            if body.parent_id in service.descendants(codes, code.id):
                raise HTTPException(422, "code_cycle")
        code.parent_id = body.parent_id
    await db.commit()
    counts = await service.excerpt_counts(db, project_id)
    out = CodeOut.model_validate(code)
    out.excerpts = counts.get(code.id, 0)
    return out


@router.delete("/coding/codes/{code_id}", status_code=204)
async def delete_code(
    project_id: uuid.UUID,
    code_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apaga o código e os subcódigos. Trechos que ficarem sem código também somem."""
    await require_lead(db, project_id, user)
    code = await _code(db, project_id, code_id)
    await db.delete(code)
    await db.flush()
    await service.drop_orphans(db, project_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/coding/codes/{code_id}/merge", response_model=CodeOut)
async def merge_code(
    project_id: uuid.UUID,
    code_id: uuid.UUID,
    body: MergeIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Junta um código em outro: os trechos e subcódigos passam para o destino."""
    await require_lead(db, project_id, user)
    source = await _code(db, project_id, code_id)
    target = await _code(db, project_id, body.into)
    codes = await service.codes_of(db, project_id)
    if target.id in service.descendants(codes, source.id):
        raise HTTPException(422, "code_cycle")
    excerpt_ids = list(
        (
            await db.execute(select(ExcerptCode.excerpt_id).where(ExcerptCode.code_id == source.id))
        ).scalars()
    )
    already = set(
        (
            await db.execute(
                select(ExcerptCode.excerpt_id).where(
                    ExcerptCode.code_id == target.id, ExcerptCode.excerpt_id.in_(excerpt_ids)
                )
            )
        ).scalars()
    )
    db.add_all(
        ExcerptCode(excerpt_id=e, code_id=target.id) for e in excerpt_ids if e not in already
    )
    for c in codes:
        if c.parent_id == source.id:
            c.parent_id = target.id
    await db.flush()
    await db.delete(source)
    await db.commit()
    counts = await service.excerpt_counts(db, project_id)
    out = CodeOut.model_validate(target)
    out.excerpts = counts.get(target.id, 0)
    return out


# --- Estudos e trechos ------------------------------------------------------------------


@router.get("/coding/units", response_model=list[CodingUnit])
async def coding_units(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    return await service.unit_stats(db, project, await service.coding_units(db, project))


@router.get("/coding/matrix", response_model=Matrix)
async def matrix(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    us = await service.coding_units(db, project)
    return Matrix(
        units=await service.unit_stats(db, project, us),
        cells=await service.matrix_cells(db, project_id),
    )


@router.get("/coding/excerpts", response_model=list[ExcerptOut])
async def list_excerpts(
    project_id: uuid.UUID,
    record_id: uuid.UUID | None = None,
    code_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trechos de um estudo, ou de um código (incluindo os subcódigos)."""
    project, _ = await get_membership(db, project_id, user)
    stmt = select(Excerpt).where(Excerpt.project_id == project_id)
    if record_id:
        stmt = stmt.where(Excerpt.record_id == record_id)
    if code_id:
        codes = await service.codes_of(db, project_id)
        await _code(db, project_id, code_id)
        ids = service.descendants(codes, code_id)
        stmt = stmt.where(
            select(ExcerptCode.excerpt_id)
            .where(ExcerptCode.excerpt_id == Excerpt.id, ExcerptCode.code_id.in_(ids))
            .exists()
        )
    rows = (await db.execute(stmt.order_by(Excerpt.page, Excerpt.created_at))).scalars().all()
    return await service.excerpts_out(db, list(rows), await _labels(db, project))


@router.post("/coding/excerpts", response_model=ExcerptOut, status_code=201)
async def create_excerpt(
    project_id: uuid.UUID,
    body: ExcerptIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await _coder(db, project_id, user)
    unit = await unit_for(db, project, body.record_id)
    if unit is None:
        raise HTTPException(404, "study_not_found")
    await _check_codes(db, project_id, body.code_ids)
    if body.file_id:
        f = await db.get(RecordFile, body.file_id)
        if f is None or f.record_id not in unit.report_ids:
            raise HTTPException(404, "file_not_found")
    ex = Excerpt(
        project_id=project_id,
        record_id=body.record_id,
        file_id=body.file_id,
        page=body.page,
        text=body.text.strip(),
        note=body.note,
        user_id=user.id,
    )
    db.add(ex)
    await db.flush()
    db.add_all(ExcerptCode(excerpt_id=ex.id, code_id=c) for c in set(body.code_ids))
    await db.commit()
    return (await service.excerpts_out(db, [ex], {unit.record.id: unit.label}))[0]


async def _own_excerpt(
    db: AsyncSession, project_id: uuid.UUID, excerpt_id: uuid.UUID, user: User
) -> Excerpt:
    _, lead = await _coder(db, project_id, user)
    ex = await db.get(Excerpt, excerpt_id)
    if ex is None or ex.project_id != project_id:
        raise HTTPException(404, "excerpt_not_found")
    if ex.user_id != user.id and not lead:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_excerpt")
    return ex


@router.patch("/coding/excerpts/{excerpt_id}", response_model=ExcerptOut)
async def update_excerpt(
    project_id: uuid.UUID,
    excerpt_id: uuid.UUID,
    body: ExcerptPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    ex = await _own_excerpt(db, project_id, excerpt_id, user)
    if body.note is not None:
        ex.note = body.note
    if body.code_ids is not None:
        await _check_codes(db, project_id, body.code_ids)
        await db.execute(delete(ExcerptCode).where(ExcerptCode.excerpt_id == ex.id))
        db.add_all(ExcerptCode(excerpt_id=ex.id, code_id=c) for c in set(body.code_ids))
    await db.commit()
    project = await db.get(Project, project_id)
    return (await service.excerpts_out(db, [ex], await _labels(db, project)))[0]


@router.delete("/coding/excerpts/{excerpt_id}", status_code=204)
async def delete_excerpt(
    project_id: uuid.UUID,
    excerpt_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    ex = await _own_excerpt(db, project_id, excerpt_id, user)
    await db.delete(ex)
    await db.commit()
    return Response(status_code=204)


@router.get("/coding/export")
async def export_excerpts(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    rows = (
        (await db.execute(select(Excerpt).where(Excerpt.project_id == project_id))).scalars().all()
    )
    data = await service.excerpts_out(db, list(rows), await _labels(db, project))
    data.sort(key=lambda r: (r["study"], r["page"] or 0))
    body = service.excerpts_csv(await service.codes_of(db, project_id), data)
    return Response(
        content="﻿" + body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="codificacao.csv"'},
    )


# --- Checklists de relato ---------------------------------------------------------------


@router.get("/checklists/{kind}", response_model=ChecklistOut)
async def get_checklist(
    project_id: uuid.UUID,
    kind: ChecklistKind,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    saved = {
        e.item: e
        for e in (
            await db.execute(
                select(ChecklistEntry).where(
                    ChecklistEntry.project_id == project_id, ChecklistEntry.checklist == kind
                )
            )
        ).scalars()
    }
    entries = []
    for item in CHECKLISTS[kind]:
        e = saved.get(item)
        entries.append(
            ChecklistEntryOut(
                item=item,
                status=e.status if e else "pending",
                location=e.location if e else "",
                note=e.note if e else "",
                updated_at=e.updated_at if e else None,
            )
        )
    return ChecklistOut(
        checklist=kind, entries=entries, facts=await service.checklist_facts(db, project)
    )


@router.put("/checklists/{kind}/{item}", response_model=ChecklistEntryOut)
async def save_entry(
    project_id: uuid.UUID,
    kind: ChecklistKind,
    item: str,
    body: ChecklistEntryIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    if item not in CHECKLISTS[kind]:
        raise HTTPException(404, "item_not_found")
    entry = await db.get(ChecklistEntry, (project_id, kind, item))
    if entry is None:
        entry = ChecklistEntry(project_id=project_id, checklist=kind, item=item)
        db.add(entry)
    entry.status, entry.location, entry.note = body.status, body.location, body.note
    entry.updated_by_id = user.id
    entry.updated_at = utcnow()
    await db.commit()
    return ChecklistEntryOut(
        item=item,
        status=entry.status,
        location=entry.location,
        note=entry.note,
        updated_at=entry.updated_at,
    )


@router.get("/checklists/{kind}/export")
async def export_checklist(
    project_id: uuid.UUID,
    kind: ChecklistKind,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    saved = {
        e.item: e
        for e in (
            await db.execute(
                select(ChecklistEntry).where(
                    ChecklistEntry.project_id == project_id, ChecklistEntry.checklist == kind
                )
            )
        ).scalars()
    }
    lines = ["item,status,location,note"]
    for item in CHECKLISTS[kind]:
        e = saved.get(item)
        cells = [item, e.status if e else "pending", e.location if e else "", e.note if e else ""]
        lines.append(",".join('"' + service.safe_cell(c).replace('"', '""') + '"' for c in cells))
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(
        content="﻿" + "\n".join(lines) + "\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{kind}-{stamp}.csv"'},
    )
