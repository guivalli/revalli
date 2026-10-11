import base64
import binascii
import re
import unicodedata
import uuid
from datetime import datetime

import pymupdf
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership
from revalli.models import Record, Search, User
from revalli.modules.reports.document import build_report
from revalli.modules.reports.render import to_docx, to_pdf
from revalli.modules.reports.schemas import DocumentIn, Prisma
from revalli.modules.reports.service import (
    STATE_LABELS,
    prisma_counts,
    reason_labels,
    study_labels,
    to_csl_json,
    to_csv,
    to_ris,
)
from revalli.modules.screening.models import Decision, Phase
from revalli.modules.screening.router import _names
from revalli.modules.screening.service import State, can_see_others, compute_states

router = APIRouter(prefix="/projects/{project_id}", tags=["reports"])

PHASE_LABELS = {Phase.title_abstract: "título e resumo", Phase.full_text: "texto completo"}
DECISION_LABELS = {
    Decision.include: "incluir",
    Decision.exclude: "excluir",
    Decision.maybe: "talvez",
}


@router.get("/report/prisma", response_model=Prisma)
async def prisma(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    return await prisma_counts(db, project)


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "projeto"


@router.get("/export")
async def export(
    project_id: uuid.UUID,
    format: str = Query("ris", pattern="^(ris|csv|csl)$"),
    phase: Phase = Phase.title_abstract,
    state: str = Query("all", pattern="^(all|included|excluded|conflict|pending)$"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Referências da fase com o estado e as decisões, respeitando o cegamento."""
    project, role = await get_membership(db, project_id, user)
    see_others = can_see_others(project, role)
    states = await compute_states(db, project, phase)
    if state != "all":
        states = {rid: st for rid, st in states.items() if st.state == state}
    records = (
        await db.execute(
            select(Record, Search.source)
            .outerjoin(Search, Search.id == Record.search_id)
            .where(Record.id.in_(list(states)))
            .order_by(Record.year.desc().nulls_last(), Record.title)
        )
    ).all()
    reasons = await reason_labels(db, project_id)
    study_names = await study_labels(db, list(states))
    names = await _names(db, {u for st in states.values() for u in st.votes})
    if see_others:
        names |= await _names(db, {st.final.user_id for st in states.values() if st.final})

    rows = []
    for r, source in records:
        st = states[r.id]
        visible = (
            list(st.votes.values())
            if see_others
            else [v for uid, v in st.votes.items() if uid == user.id]
        )
        events = visible + ([st.final] if st.final and see_others else [])
        # Os motivos de um registro excluído são o resultado da triagem e aparecem sempre
        if st.state == State.excluded:
            sources = list(st.votes.values()) + ([st.final] if st.final else [])
        else:
            sources = events
        reason_ids: list[str] = []
        for ev in sources:
            if ev.decision == Decision.exclude:
                reason_ids += [x for x in ev.reason_ids if x not in reason_ids]
        labels: list[str] = []
        for ev in visible:
            labels += [x for x in ev.labels if x not in labels]
        decisions = [
            f"{'decisão final' if ev.is_final else names.get(ev.user_id, '?')}: "
            f"{DECISION_LABELS.get(ev.decision, ev.decision)}"
            for ev in events
        ]
        notes = [f"{names.get(ev.user_id, '?')}: {ev.note}" for ev in events if ev.note]
        reason_text = [reasons.get(x, "?") for x in reason_ids]
        summary = f"ReValli, {PHASE_LABELS[phase]}: {STATE_LABELS[st.state]}"
        if reason_text:
            summary += f". Motivos: {', '.join(reason_text)}"
        if labels:
            summary += f". Etiquetas: {', '.join(labels)}"
        if r.id in study_names:
            summary += f". Estudo: {study_names[r.id]}"
        rows.append(
            {
                "record": r,
                "source": source or "",
                "state": STATE_LABELS[st.state],
                "reasons": reason_text,
                "labels": labels,
                "decisions": decisions,
                "notes": notes,
                "study": study_names.get(r.id, ""),
                "summary": summary,
            }
        )

    name = f"{_slug(project.title)}-{phase.value}-{state}"
    if format == "csv":
        body, media = to_csv(rows), "text/csv; charset=utf-8"
    elif format == "csl":
        body, media = to_csl_json(rows), "application/vnd.citationstyles.csl+json; charset=utf-8"
    else:
        body, media = to_ris(rows), "application/x-research-info-systems; charset=utf-8"
    return Response(
        content=body.encode("utf-8"),
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{name}.{"json" if format == "csl" else format}"'
        },
    )


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def _png(data: str) -> bytes:
    """Decodifica e confere uma figura enviada pela interface."""
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "invalid_figure") from None
    if not raw.startswith(PNG_MAGIC):
        raise HTTPException(422, "invalid_figure")
    try:
        pix = pymupdf.Pixmap(raw)
    except Exception:
        raise HTTPException(422, "invalid_figure") from None
    if pix.width * pix.height > 25_000_000:
        raise HTTPException(422, "invalid_figure")
    return raw


@router.post("/report/document")
async def report_document(
    project_id: uuid.UUID,
    body: DocumentIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rascunho do relatório da revisão (métodos, resultados e apêndices) em DOCX ou PDF."""
    project, _ = await get_membership(db, project_id, user)
    figures = {k: _png(v) for k, v in body.figures.items()}
    report = await build_report(
        db,
        project,
        lang=body.lang,
        sections=list(body.sections),
        figures=figures,
        checklist_items=body.checklist_items,
    )
    content = to_docx(report) if body.format == "docx" else to_pdf(report)
    stamp = datetime.now().strftime("%Y%m%d")
    name = f"{_slug(project.title)}-relatorio-{stamp}.{body.format}"
    return Response(
        content=content,
        media_type=MEDIA[body.format],
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
