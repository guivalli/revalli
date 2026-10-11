"""Regras da triagem: quem já decidiu, o que está em conflito e o que falta."""

import uuid
from dataclasses import dataclass, field
from itertools import combinations

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import DecisionEvent, DuplicateGroup, Project, Record
from revalli.modules.records.models import DuplicateStatus
from revalli.modules.screening.models import Decision, Phase
from revalli.modules.screening.schemas import ScreeningSettings

UNDO = "undo"


class State:
    pending = "pending"
    included = "included"
    excluded = "excluded"
    conflict = "conflict"


@dataclass
class RecordState:
    record_id: uuid.UUID
    votes: dict[uuid.UUID, DecisionEvent] = field(default_factory=dict)
    final: DecisionEvent | None = None
    state: str = State.pending


def get_settings(project: Project) -> ScreeningSettings:
    return ScreeningSettings.model_validate(project.settings or {})


def eligible_ids_query(project_id: uuid.UUID, phase: Phase):
    """Registros que entram na fase: únicos (sem duplicatas removidas) e, no texto completo,
    só os incluídos na fase de título e resumo."""
    stmt = (
        select(Record.id)
        .outerjoin(DuplicateGroup, DuplicateGroup.id == Record.duplicate_group_id)
        .where(
            Record.project_id == project_id,
            ~func.coalesce(
                and_(
                    DuplicateGroup.status == DuplicateStatus.confirmed,
                    DuplicateGroup.primary_record_id != Record.id,
                ),
                False,
            ),
        )
    )
    return stmt


async def compute_states(
    db: AsyncSession, project: Project, phase: Phase, record_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, RecordState]:
    settings = get_settings(project)
    required = settings.reviewers_for(phase)
    if record_ids is None:
        record_ids = list((await db.execute(eligible_ids_query(project.id, phase))).scalars())
        if phase == Phase.full_text:
            ta = await compute_states(db, project, Phase.title_abstract, record_ids)
            record_ids = [rid for rid, st in ta.items() if st.state == State.included]
    states = {rid: RecordState(rid) for rid in record_ids}
    if not states:
        return states

    # Evento mais recente de cada pessoa em cada registro (e o final mais recente)
    latest = (
        select(DecisionEvent)
        .where(DecisionEvent.project_id == project.id, DecisionEvent.phase == phase)
        .ext(distinct_on(DecisionEvent.record_id, DecisionEvent.is_final, DecisionEvent.user_id))
        .order_by(
            DecisionEvent.record_id,
            DecisionEvent.is_final,
            DecisionEvent.user_id,
            DecisionEvent.created_at.desc(),
        )
    )
    finals: dict[uuid.UUID, DecisionEvent] = {}
    for ev in (await db.execute(latest)).scalars():
        st = states.get(ev.record_id)
        if st is None:
            continue
        if ev.is_final:
            # Pode haver finais de pessoas diferentes; vale o mais recente
            cur = finals.get(ev.record_id)
            if cur is None or ev.created_at > cur.created_at:
                finals[ev.record_id] = ev
        elif ev.decision != UNDO and ev.user_id is not None:
            st.votes[ev.user_id] = ev

    for rid, st in states.items():
        final = finals.get(rid)
        if final is not None and final.decision != UNDO:
            st.final = final
            st.state = (
                State.included
                if final.decision == Decision.include
                else (State.excluded if final.decision == Decision.exclude else State.conflict)
            )
            continue
        if len(st.votes) < required:
            st.state = State.pending
            continue
        kinds = {v.decision for v in st.votes.values()}
        if kinds == {Decision.include}:
            st.state = State.included
        elif kinds == {Decision.exclude}:
            st.state = State.excluded
        else:
            st.state = State.conflict
    return states


def kappa(pairs: list[tuple[str, str]]) -> tuple[float | None, float | None]:
    """Kappa de Cohen e concordância percentual para as decisões de duas pessoas."""
    n = len(pairs)
    if n == 0:
        return None, None
    agree = sum(1 for a, b in pairs if a == b) / n
    cats = {c for p in pairs for c in p}
    pe = sum(
        (sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n)
        for c in cats
    )
    if pe >= 1:
        return (1.0 if agree == 1 else None), agree
    return (agree - pe) / (1 - pe), agree


def agreement_pairs(states: dict[uuid.UUID, RecordState]) -> dict[tuple, list[tuple[str, str]]]:
    by_pair: dict[tuple, list[tuple[str, str]]] = {}
    for st in states.values():
        for (ua, ea), (ub, eb) in combinations(
            sorted(st.votes.items(), key=lambda x: str(x[0])), 2
        ):
            by_pair.setdefault((ua, ub), []).append((ea.decision, eb.decision))
    return by_pair
