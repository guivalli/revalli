import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import DecisionEvent, ExclusionReason, Project, ProjectMember, Record, User
from revalli.modules.ai.active import order_by_scores, relevance_scores
from revalli.modules.projects.models import Role
from revalli.modules.screening.models import Decision, Phase
from revalli.modules.screening.schemas import (
    Agreement,
    ConflictItem,
    ConflictPage,
    DecisionIn,
    DecisionOut,
    PairAgreement,
    Progress,
    Queue,
    QueueItem,
    ReasonIn,
    ReasonOut,
    ReasonPatch,
    ResolveIn,
    ReviewerProgress,
    ScreenedItem,
    ScreenedPage,
    ScreeningSettings,
)
from revalli.modules.screening.service import (
    UNDO,
    RecordState,
    State,
    agreement_pairs,
    can_see_others,
    compute_states,
    get_settings,
    kappa,
)

router = APIRouter(prefix="/projects/{project_id}/screening", tags=["screening"])

SCREENING_ROLES = {Role.lead, Role.reviewer}
RESOLVER_ROLES = {Role.lead, Role.arbitrator}


async def _names(db: AsyncSession, ids) -> dict[uuid.UUID, str]:
    ids = [i for i in ids if i]
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))
    return dict(rows.all())


def _decision_out(ev: DecisionEvent, names: dict | None = None) -> DecisionOut:
    return DecisionOut(
        user_id=ev.user_id,
        user_name=(names or {}).get(ev.user_id),
        decision=ev.decision,
        reason_ids=ev.reason_ids or [],
        labels=ev.labels or [],
        note=ev.note or "",
        is_final=ev.is_final,
        created_at=ev.created_at,
    )


def _item(r: Record, mine: DecisionEvent | None = None) -> QueueItem:
    return QueueItem(
        id=r.id,
        title=r.title,
        abstract=r.abstract,
        authors=r.authors or [],
        year=r.year,
        journal=r.journal,
        doi=r.doi,
        pmid=r.pmid,
        keywords=r.keywords or [],
        publication_type=r.publication_type,
        language=r.language,
        my_decision=_decision_out(mine) if mine else None,
    )


async def _can_see_others(db, project: Project, user: User, role: Role | None) -> bool:
    return can_see_others(project, role)


# --- Configuração ----------------------------------------------------------------


@router.get("/settings", response_model=ScreeningSettings)
async def read_settings(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    return get_settings(project)


@router.put("/settings", response_model=ScreeningSettings)
async def write_settings(
    project_id: uuid.UUID,
    body: ScreeningSettings,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await require_lead(db, project_id, user)
    project.settings = {**(project.settings or {}), **body.model_dump()}
    await db.commit()
    return get_settings(project)


@router.get("/reasons", response_model=list[ReasonOut])
async def list_reasons(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = await db.execute(
        select(ExclusionReason)
        .where(ExclusionReason.project_id == project_id)
        .order_by(ExclusionReason.position, ExclusionReason.created_at)
    )
    return rows.scalars().all()


@router.post("/reasons", response_model=ReasonOut, status_code=201)
async def add_reason(
    project_id: uuid.UUID,
    body: ReasonIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    pos = (
        await db.execute(
            select(func.coalesce(func.max(ExclusionReason.position), -1)).where(
                ExclusionReason.project_id == project_id
            )
        )
    ).scalar_one()
    reason = ExclusionReason(project_id=project_id, label=body.label.strip(), position=pos + 1)
    db.add(reason)
    await db.commit()
    return reason


@router.patch("/reasons/{reason_id}", response_model=ReasonOut)
async def update_reason(
    project_id: uuid.UUID,
    reason_id: uuid.UUID,
    body: ReasonPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    reason = await db.get(ExclusionReason, reason_id)
    if reason is None or reason.project_id != project_id:
        raise HTTPException(404, "reason_not_found")
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(reason, k, v.strip() if k == "label" else v)
    await db.commit()
    return reason


@router.get("/labels", response_model=list[str])
async def list_labels(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Etiquetas já usadas no projeto, para sugerir ao digitar."""
    project, _ = await get_membership(db, project_id, user)
    rows = await db.execute(
        select(func.jsonb_array_elements_text(DecisionEvent.labels).label("l"))
        .where(DecisionEvent.project_id == project_id)
        .distinct()
        .order_by("l")
        .limit(500)
    )
    used = list(rows.scalars())
    # O vocabulário do projeto também entra nas sugestões, mesmo antes de ser usado
    seen = {u.lower() for u in used}
    vocab = [t.name for t in get_settings(project).tag_vocabulary if t.name.lower() not in seen]
    return sorted(used + vocab, key=str.lower)


# --- Triagem ---------------------------------------------------------------------


async def _screening_context(db, project_id, user):
    project, role = await get_membership(db, project_id, user)
    if role not in SCREENING_ROLES:
        raise HTTPException(403, "not_a_reviewer")
    return project, role


def _needs_me(st: RecordState, user_id: uuid.UUID, required: int) -> bool:
    return st.final is None and user_id not in st.votes and len(st.votes) < required


@router.get("/{phase}/queue", response_model=Queue)
async def queue(
    project_id: uuid.UUID,
    phase: Phase,
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Próximos registros que precisam de uma decisão minha."""
    project, _ = await _screening_context(db, project_id, user)
    required = get_settings(project).reviewers_for(phase)
    states = await compute_states(db, project, phase)
    todo = [rid for rid, st in states.items() if _needs_me(st, user.id, required)]
    if not todo:
        return Queue(items=[], remaining=0)
    # Com aprendizado ativo, os mais prováveis de inclusão vêm primeiro
    scores = await relevance_scores(db, project, todo) if phase == Phase.title_abstract else None
    stmt = select(Record).where(Record.id.in_(todo))
    if scores:
        ranked = order_by_scores(todo, scores)[:limit]
        rows = {r.id: r for r in (await db.execute(stmt.where(Record.id.in_(ranked)))).scalars()}
        records = [rows[rid] for rid in ranked]
    else:
        records = (
            (await db.execute(stmt.order_by(Record.created_at, Record.id).limit(limit)))
            .scalars()
            .all()
        )
    await db.commit()  # a conta técnica da IA pode ter sido criada agora
    return Queue(items=[_item(r) for r in records], remaining=len(todo))


@router.post("/{phase}/decisions", response_model=DecisionOut | None)
async def decide(
    project_id: uuid.UUID,
    phase: Phase,
    body: DecisionIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await _screening_context(db, project_id, user)
    states = await compute_states(db, project, phase)
    st = states.get(body.record_id)
    if st is None:
        raise HTTPException(404, "record_not_in_phase")
    if st.final is not None:
        raise HTTPException(409, "already_resolved")
    required = get_settings(project).reviewers_for(phase)
    if user.id not in st.votes and len(st.votes) >= required:
        raise HTTPException(409, "enough_reviewers")
    if body.decision == Decision.exclude or body.reason_ids:
        await _check_reasons(db, project_id, body.reason_ids)
    ev = DecisionEvent(
        project_id=project_id,
        record_id=body.record_id,
        user_id=user.id,
        phase=phase,
        decision=body.decision or UNDO,
        reason_ids=[str(r) for r in body.reason_ids] if body.decision == Decision.exclude else [],
        labels=body.labels,
        note=body.note,
    )
    db.add(ev)
    await db.commit()
    return _decision_out(ev) if body.decision else None


async def _check_reasons(db, project_id, reason_ids) -> None:
    if not reason_ids:
        return
    found = (
        await db.execute(
            select(func.count())
            .select_from(ExclusionReason)
            .where(ExclusionReason.project_id == project_id, ExclusionReason.id.in_(reason_ids))
        )
    ).scalar_one()
    if found != len(set(reason_ids)):
        raise HTTPException(422, "invalid_reason")


@router.get("/{phase}/progress", response_model=Progress)
async def progress(
    project_id: uuid.UUID,
    phase: Phase,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    settings = get_settings(project)
    required = settings.reviewers_for(phase)
    states = await compute_states(db, project, phase)
    counts = {s: 0 for s in (State.included, State.excluded, State.conflict, State.pending)}
    per_user: dict[uuid.UUID, dict[str, int]] = {}
    for st in states.values():
        counts[st.state] += 1
        for uid, ev in st.votes.items():
            c = per_user.setdefault(uid, {"include": 0, "exclude": 0, "maybe": 0})
            c[ev.decision] += 1
    members = (
        await db.execute(
            select(User.id, User.full_name)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id, ProjectMember.role.in_(SCREENING_ROLES))
            .order_by(User.full_name)
        )
    ).all()
    reviewers = [
        ReviewerProgress(
            user_id=uid,
            full_name=name,
            decided=sum(per_user.get(uid, {}).values()),
            included=per_user.get(uid, {}).get("include", 0),
            excluded=per_user.get(uid, {}).get("exclude", 0),
            maybe=per_user.get(uid, {}).get("maybe", 0),
        )
        for uid, name in members
    ]
    # Quem votou sem ser membro (a IA como revisora, ou alguém que saiu do projeto)
    listed = {uid for uid, _ in members}
    others = await _names(db, set(per_user) - listed)
    reviewers += [
        ReviewerProgress(
            user_id=uid,
            full_name=name,
            decided=sum(per_user[uid].values()),
            included=per_user[uid]["include"],
            excluded=per_user[uid]["exclude"],
            maybe=per_user[uid]["maybe"],
        )
        for uid, name in others.items()
    ]
    return Progress(
        phase=phase,
        eligible=len(states),
        included=counts[State.included],
        excluded=counts[State.excluded],
        conflicts=counts[State.conflict],
        pending=counts[State.pending],
        reviewers_required=required,
        blind=settings.blind,
        remaining_for_me=sum(1 for st in states.values() if _needs_me(st, user.id, required)),
        reviewers=reviewers,
    )


@router.get("/{phase}/conflicts", response_model=ConflictPage)
async def conflicts(
    project_id: uuid.UUID,
    phase: Phase,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, role = await get_membership(db, project_id, user)
    if role not in RESOLVER_ROLES and not user.is_admin:
        raise HTTPException(403, "lead_or_arbitrator_only")
    if not await _can_see_others(db, project, user, role):
        raise HTTPException(409, "blind_on")
    states = await compute_states(db, project, phase)
    ids = [rid for rid, st in states.items() if st.state == State.conflict]
    page_ids = ids[(page - 1) * page_size : page * page_size]
    records = {
        r.id: r for r in (await db.execute(select(Record).where(Record.id.in_(page_ids)))).scalars()
    }
    names = await _names(db, {uid for rid in page_ids for uid in states[rid].votes})
    items = [
        ConflictItem(
            record=_item(records[rid]),
            decisions=[_decision_out(ev, names) for ev in states[rid].votes.values()],
        )
        for rid in page_ids
    ]
    return ConflictPage(items=items, total=len(ids))


@router.post("/{phase}/resolve", response_model=DecisionOut | None)
async def resolve(
    project_id: uuid.UUID,
    phase: Phase,
    body: ResolveIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, role = await get_membership(db, project_id, user)
    if role not in RESOLVER_ROLES and not user.is_admin:
        raise HTTPException(403, "lead_or_arbitrator_only")
    if not await _can_see_others(db, project, user, role):
        raise HTTPException(409, "blind_on")
    if body.decision == Decision.maybe:
        raise HTTPException(422, "final_must_be_include_or_exclude")
    states = await compute_states(db, project, phase)
    if body.record_id not in states:
        raise HTTPException(404, "record_not_in_phase")
    if body.decision == Decision.exclude:
        await _check_reasons(db, project_id, body.reason_ids)
    ev = DecisionEvent(
        project_id=project_id,
        record_id=body.record_id,
        user_id=user.id,
        phase=phase,
        decision=body.decision or UNDO,
        reason_ids=[str(r) for r in body.reason_ids] if body.decision == Decision.exclude else [],
        note=body.note,
        is_final=True,
    )
    db.add(ev)
    await db.commit()
    return _decision_out(ev) if body.decision else None


@router.get("/{phase}/agreement", response_model=Agreement)
async def agreement(
    project_id: uuid.UUID,
    phase: Phase,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    states = await compute_states(db, project, phase)
    pairs = agreement_pairs(states)
    names = await _names(db, {u for pair in pairs for u in pair})
    out = []
    for (ua, ub), decisions in pairs.items():
        k, pct = kappa(decisions)
        out.append(
            PairAgreement(
                user_a=names.get(ua, "?"),
                user_b=names.get(ub, "?"),
                n=len(decisions),
                percent=round(pct * 100, 1) if pct is not None else None,
                kappa=round(k, 3) if k is not None else None,
            )
        )
    return Agreement(pairs=out)


@router.get("/{phase}/screened", response_model=ScreenedPage)
async def screened(
    project_id: uuid.UUID,
    phase: Phase,
    state: str = Query("all", pattern="^(all|included|excluded|conflict|pending|mine)$"),
    decision: Decision | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Registros da fase com o estado atual. Em 'mine', só os que eu já decidi."""
    project, role = await get_membership(db, project_id, user)
    see_others = await _can_see_others(db, project, user, role)
    states = await compute_states(db, project, phase)
    if state == "mine":
        sel = [
            st
            for st in states.values()
            if user.id in st.votes and (decision is None or st.votes[user.id].decision == decision)
        ]
    elif state == "all":
        sel = list(states.values())
    else:
        sel = [st for st in states.values() if st.state == state]
    if not see_others and state != "mine":
        # Com cegamento, o estado consolidado revela decisões alheias; só líderes veem os totais
        sel = [st for st in sel if user.id in st.votes]
    ids = [st.record_id for st in sel]
    records = {
        r.id: r
        for r in (
            await db.execute(
                select(Record).where(Record.id.in_(ids)).order_by(Record.created_at, Record.id)
            )
        ).scalars()
    }
    ordered = [rid for rid in records][(page - 1) * page_size : page * page_size]
    names = await _names(db, {uid for rid in ordered for uid in states[rid].votes} | {user.id})
    items = []
    for rid in ordered:
        st = states[rid]
        visible = [ev for uid, ev in st.votes.items() if see_others or uid == user.id] + (
            [st.final] if st.final and see_others else []
        )
        items.append(
            ScreenedItem(
                record=_item(records[rid], st.votes.get(user.id)),
                state=st.state if see_others else "hidden",
                decisions=[_decision_out(ev, names) for ev in visible],
            )
        )
    return ScreenedPage(items=items, total=len(ids))
