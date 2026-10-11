import re
import unicodedata
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership
from revalli.models import Record, Search, User
from revalli.modules.reports.schemas import Prisma
from revalli.modules.reports.service import (
    STATE_LABELS,
    prisma_counts,
    reason_labels,
    study_labels,
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
    format: str = Query("ris", pattern="^(ris|csv)$"),
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
    else:
        body, media = to_ris(rows), "application/x-research-info-systems; charset=utf-8"
    return Response(
        content=body.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}.{format}"'},
    )
