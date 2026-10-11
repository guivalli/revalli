import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership
from revalli.models import User
from revalli.modules.gaps import service

router = APIRouter(prefix="/projects/{project_id}/gaps", tags=["gaps"])


@router.get("/dimensions")
async def dimensions(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Os códigos com subcódigos e os campos de escolha que podem virar eixo do mapa."""
    project, _ = await get_membership(db, project_id, user)
    return await service.available(db, project)


async def _map(db: AsyncSession, project_id: uuid.UUID, user: User, rows: str, cols: str):
    project, _ = await get_membership(db, project_id, user)
    try:
        return await service.build_map(db, project, rows, cols)
    except service.DimensionError as exc:
        raise HTTPException(422 if str(exc) == "invalid_dimension" else 404, str(exc)) from exc


@router.get("")
async def gap_map(
    project_id: uuid.UUID,
    rows: str = Query(min_length=1, max_length=200),
    cols: str = Query(min_length=1, max_length=200),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _map(db, project_id, user, rows, cols)


def _safe(v: str) -> str:
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


@router.get("/export")
async def export(
    project_id: uuid.UUID,
    rows: str = Query(min_length=1, max_length=200),
    cols: str = Query(min_length=1, max_length=200),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """CSV com uma linha por célula (categoria da linha, da coluna, número e estudos)."""
    data = await _map(db, project_id, user, rows, cols)
    r_label = {c["key"]: c["label"] for c in data["rows"]["categories"]}
    c_label = {c["key"]: c["label"] for c in data["cols"]["categories"]}
    counts = {(c["row"], c["col"]): c["studies"] for c in data["cells"]}
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow([data["rows"]["title"], data["cols"]["title"], "studies", "study_labels"])
    for rk, rl in r_label.items():
        for ck, cl in c_label.items():
            ids = counts.get((rk, ck), [])
            labels = "; ".join(data["studies"][i]["label"] for i in ids)
            w.writerow([_safe(rl), _safe(cl), len(ids), _safe(labels)])
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="evidence-gap-map.csv"'},
    )
