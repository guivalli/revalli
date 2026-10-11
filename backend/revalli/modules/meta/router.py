import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import User
from revalli.modules.meta import service
from revalli.modules.meta.models import GradeRow, MetaAnalysis
from revalli.modules.meta.schemas import AnalysisIn, AnalysisOut, GradeIn, GradeOut, ResultOut

router = APIRouter(prefix="/projects/{project_id}", tags=["meta"])


async def _analysis(db: AsyncSession, project_id: uuid.UUID, aid: uuid.UUID) -> MetaAnalysis:
    a = await db.get(MetaAnalysis, aid)
    if a is None or a.project_id != project_id:
        raise HTTPException(404, "analysis_not_found")
    return a


def _rows(body: AnalysisIn) -> list[dict]:
    ids = [r.id for r in body.rows]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "duplicate_row_id")
    return [r.model_dump(mode="json") for r in body.rows]


@router.get("/meta", response_model=list[AnalysisOut])
async def list_analyses(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = await db.execute(
        select(MetaAnalysis)
        .where(MetaAnalysis.project_id == project_id)
        .order_by(MetaAnalysis.position, MetaAnalysis.created_at)
    )
    return rows.scalars().all()


@router.post("/meta", response_model=AnalysisOut, status_code=201)
async def create_analysis(
    project_id: uuid.UUID,
    body: AnalysisIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    position = (
        await db.execute(select(func.count()).where(MetaAnalysis.project_id == project_id))
    ).scalar_one()
    a = MetaAnalysis(
        project_id=project_id,
        **body.model_dump(exclude={"rows"}),
        rows=_rows(body),
        position=position,
    )
    db.add(a)
    await db.commit()
    return a


@router.put("/meta/{analysis_id}", response_model=AnalysisOut)
async def update_analysis(
    project_id: uuid.UUID,
    analysis_id: uuid.UUID,
    body: AnalysisIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    a = await _analysis(db, project_id, analysis_id)
    for k, v in body.model_dump(exclude={"rows"}).items():
        setattr(a, k, v)
    a.rows = _rows(body)
    await db.commit()
    return a


@router.delete("/meta/{analysis_id}", status_code=204)
async def delete_analysis(
    project_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    await db.delete(await _analysis(db, project_id, analysis_id))
    await db.commit()
    return Response(status_code=204)


@router.get("/meta/{analysis_id}/result", response_model=ResultOut)
async def analysis_result(
    project_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    return service.result(await _analysis(db, project_id, analysis_id))


@router.get("/meta/{analysis_id}/export")
async def export_analysis(
    project_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dados e resultado de cada estudo em CSV (para conferir em outro software)."""
    await get_membership(db, project_id, user)
    a = await _analysis(db, project_id, analysis_id)
    res = service.result(a)
    cols = ["n1", "mean1", "sd1", "e1", "n2", "mean2", "sd2", "e2", "hr", "hr_lower", "hr_upper"]
    cols += ["yi", "sei"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "study",
            "subgroup",
            *cols,
            "effect_yi",
            "effect_se",
            "estimate",
            "lower",
            "upper",
            "weight",
        ]
    )
    by_id = {s["id"]: s for s in res["studies"]}
    for r in a.rows or []:
        s = by_id[r["id"]]
        w.writerow(
            [r["label"], r.get("subgroup", "")]
            + [r.get(c) if r.get(c) is not None else "" for c in cols]
            + [
                s[k] if s[k] is not None else ""
                for k in ("yi", "se", "estimate", "lower", "upper", "weight")
            ]
        )
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="meta-analise.csv"'},
    )


# --- GRADE ------------------------------------------------------------------------------


async def _grade_out(db: AsyncSession, row: GradeRow) -> dict:
    analysis = await db.get(MetaAnalysis, row.analysis_id) if row.analysis_id else None
    return service.grade_out(row, analysis)


async def _check_link(db: AsyncSession, project_id: uuid.UUID, aid: uuid.UUID | None) -> None:
    if aid:
        await _analysis(db, project_id, aid)


@router.get("/grade", response_model=list[GradeOut])
async def list_grade(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = (
        await db.execute(
            select(GradeRow)
            .where(GradeRow.project_id == project_id)
            .order_by(GradeRow.position, GradeRow.created_at)
        )
    ).scalars()
    return [await _grade_out(db, r) for r in rows]


@router.post("/grade", response_model=GradeOut, status_code=201)
async def create_grade(
    project_id: uuid.UUID,
    body: GradeIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    await _check_link(db, project_id, body.analysis_id)
    position = (
        await db.execute(select(func.count()).where(GradeRow.project_id == project_id))
    ).scalar_one()
    row = GradeRow(project_id=project_id, **body.model_dump(mode="json"), position=position)
    row.analysis_id = body.analysis_id
    db.add(row)
    await db.commit()
    return await _grade_out(db, row)


@router.put("/grade/{row_id}", response_model=GradeOut)
async def update_grade(
    project_id: uuid.UUID,
    row_id: uuid.UUID,
    body: GradeIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    row = await db.get(GradeRow, row_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(404, "grade_not_found")
    await _check_link(db, project_id, body.analysis_id)
    for k, v in body.model_dump(mode="json").items():
        setattr(row, k, v)
    row.analysis_id = body.analysis_id
    await db.commit()
    return await _grade_out(db, row)


@router.delete("/grade/{row_id}", status_code=204)
async def delete_grade(
    project_id: uuid.UUID,
    row_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    row = await db.get(GradeRow, row_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(404, "grade_not_found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
