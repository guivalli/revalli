"""Triagem por IA: escolha do modelo, execução em lote, cache, custo e calibração."""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import utcnow
from revalli.models import (
    AIProvider,
    AISuggestion,
    AIUsage,
    DecisionEvent,
    InstanceSetting,
    Project,
    Record,
    User,
)
from revalli.modules.ai import client
from revalli.modules.ai.client import AIError, Endpoint
from revalli.modules.ai.crypto import decrypt
from revalli.modules.ai.prompts import build_messages, estimate_tokens, prompt_hash
from revalli.modules.ai.schemas import InstanceAISettings, ProjectAISettings, TaskModel
from revalli.modules.screening.models import Decision, Phase
from revalli.modules.screening.service import (
    RecordState,
    State,
    compute_states,
    get_settings,
    kappa,
)

BOT_EMAIL = "ia@revalli.invalid"
OUTPUT_TOKENS_GUESS = 180
DECISIONS = {"include", "exclude", "maybe"}


async def instance_ai(db: AsyncSession) -> InstanceAISettings:
    row = await db.get(InstanceSetting, "ai")
    return InstanceAISettings.model_validate(row.value if row else {})


async def save_instance_ai(db: AsyncSession, value: InstanceAISettings) -> None:
    row = await db.get(InstanceSetting, "ai")
    data = value.model_dump(mode="json")
    if row is None:
        db.add(InstanceSetting(key="ai", value=data))
    else:
        row.value = data


def project_ai(project: Project) -> ProjectAISettings:
    return ProjectAISettings.model_validate((project.settings or {}).get("ai") or {})


@dataclass
class Resolved:
    endpoint: Endpoint
    provider: AIProvider
    choice: TaskModel

    @property
    def model_key(self) -> str:
        return f"{self.provider.id}:{self.choice.model}"

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.choice.price_input + output_tokens * self.choice.price_output
        ) / 1_000_000


async def resolve(db: AsyncSession, task: str, local_only: bool) -> Resolved:
    choice: TaskModel = getattr(await instance_ai(db), task)
    if choice.provider_id is None or not choice.model:
        raise AIError("not_configured")
    provider = await db.get(AIProvider, choice.provider_id)
    if provider is None:
        raise AIError("not_configured")
    if local_only and not provider.is_local:
        raise AIError("local_only")
    ep = Endpoint(
        base_url=provider.base_url,
        api_key=decrypt(provider.api_key_enc),
        model=choice.model,
        rpm=provider.rpm_limit,
    )
    return Resolved(ep, provider, choice)


async def bot_user(db: AsyncSession) -> User:
    user = (await db.execute(select(User).where(User.email == BOT_EMAIL))).scalar_one_or_none()
    if user is None:
        user = User(email=BOT_EMAIL, full_name="IA", password_hash="", is_bot=True, is_active=False)
        db.add(user)
        await db.flush()
    return user


async def spent(db: AsyncSession, project_id: uuid.UUID) -> float:
    return float(
        (
            await db.execute(
                select(func.coalesce(func.sum(AIUsage.cost_usd), 0.0)).where(
                    AIUsage.project_id == project_id
                )
            )
        ).scalar_one()
    )


# --- Seleção dos registros -------------------------------------------------------


def _human_votes(st: RecordState, bot_id: uuid.UUID) -> dict:
    return {u: v for u, v in st.votes.items() if u != bot_id}


def _human_state(st: RecordState, bot_id: uuid.UUID) -> str | None:
    """Estado decidido só pelos humanos (para calibrar sem contar o voto da própria IA)."""
    if st.final is not None:
        return st.final.decision
    votes = _human_votes(st, bot_id)
    kinds = {v.decision for v in votes.values()}
    if votes and len(kinds) == 1 and kinds <= {"include", "exclude"}:
        return kinds.pop()
    return None


def _sample(ids: list[uuid.UUID], limit: int) -> list[uuid.UUID]:
    # Amostra estável: a mesma amostra sai em execuções repetidas
    return sorted(ids, key=lambda i: hashlib.sha256(i.bytes).digest())[:limit]


async def target_ids(
    db: AsyncSession, project: Project, phase: Phase, scope: str, limit: int | None
) -> list[uuid.UUID]:
    bot = await bot_user(db)
    states = await compute_states(db, project, phase)
    required = get_settings(project).reviewers_for(phase)
    ai = project_ai(project)
    if scope == "pending":
        ids = [
            rid
            for rid, st in states.items()
            if st.state == State.pending
            and bot.id not in st.votes
            and (ai.mode == "suggest" or len(st.votes) < required)
        ]
    elif scope == "excluded":
        ids = [rid for rid, st in states.items() if st.state == State.excluded]
    else:
        ids = _sample(
            [rid for rid, st in states.items() if _human_state(st, bot.id)],
            limit or 100,
        )
    return ids[:limit] if limit else ids


async def _records(db: AsyncSession, ids: list[uuid.UUID]) -> list[Record]:
    if not ids:
        return []
    rows = (await db.execute(select(Record).where(Record.id.in_(ids)))).scalars().all()
    order = {rid: i for i, rid in enumerate(ids)}
    return sorted(rows, key=lambda r: order[r.id])


async def _cached(
    db: AsyncSession, phase: Phase, model_key: str, hashes: dict[uuid.UUID, str]
) -> dict[uuid.UUID, AISuggestion]:
    if not hashes:
        return {}
    rows = (
        await db.execute(
            select(AISuggestion).where(
                AISuggestion.record_id.in_(list(hashes)),
                AISuggestion.phase == phase,
                AISuggestion.model_key == model_key,
                AISuggestion.prompt_hash.in_(list(set(hashes.values()))),
            )
        )
    ).scalars()
    return {s.record_id: s for s in rows if hashes.get(s.record_id) == s.prompt_hash}


async def estimate(
    db: AsyncSession,
    project: Project,
    phase: Phase,
    scope: str,
    limit: int | None,
    force: bool = False,
):
    ai = project_ai(project)
    res = await resolve(db, "screening", ai.local_only)
    settings = get_settings(project)
    records = await _records(db, await target_ids(db, project, phase, scope, limit))
    msgs = {
        r.id: build_messages(
            project,
            settings,
            r,
            ai.extra_instructions,
            suggest_tags=ai.suggest_tags,
            suggest_reasons=ai.suggest_reasons,
        )
        for r in records
    }
    cache = {}
    if not force:
        cache = await _cached(
            db, phase, res.model_key, {k: prompt_hash(m) for k, m in msgs.items()}
        )
    todo = [m for k, m in msgs.items() if k not in cache]
    tin = sum(estimate_tokens(m) for m in todo)
    tout = OUTPUT_TOKENS_GUESS * len(todo)
    return {
        "records": len(records),
        "cached": len(cache),
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": round(res.cost(tin, tout), 4),
        "local": res.provider.is_local,
        "budget_usd": ai.budget_usd,
        "spent_usd": round(await spent(db, project.id), 4),
    }


# --- Execução ----------------------------------------------------------------------


def normalize_answer(data: dict) -> dict:
    decision = str(data.get("decision", "")).strip().lower()
    if decision not in DECISIONS:
        raise AIError("invalid_decision")
    try:
        confidence = float(data.get("confidence"))
        confidence = min(max(confidence, 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = None
    criteria = []
    for c in data.get("criteria") or []:
        if isinstance(c, dict) and c.get("criterion"):
            status = str(c.get("status", "unclear")).lower()
            criteria.append(
                {
                    "criterion": str(c["criterion"])[:300],
                    "status": status if status in ("met", "violated", "unclear") else "unclear",
                }
            )
    return {
        "decision": decision,
        "confidence": confidence,
        "justification": str(data.get("justification") or "")[:2000],
        "criteria": criteria[:30],
        "tags": clean_tags(data.get("tags")),
        "exclusion_reason": (
            " ".join(str(data.get("exclusion_reason") or "").split())[:200]
            if decision == "exclude"
            else ""
        ),
    }


MAX_TAGS = 4


def clean_tags(raw, vocabulary: list[str] | None = None) -> list[str]:
    """Até 4 etiquetas únicas; as que existem no vocabulário voltam com a grafia dele."""
    canon = {v.lower(): v for v in vocabulary or []}
    if isinstance(raw, str):
        raw = [t for t in raw.split(",")]
    out: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        name = item.get("name") if isinstance(item, dict) else item
        name = " ".join(str(name or "").split())[:60]
        key = name.lower()
        if name and key not in {o.lower() for o in out}:
            out.append(canon.get(key, name))
    return out[:MAX_TAGS]


async def screen_one(
    db: AsyncSession,
    project: Project,
    res: Resolved,
    phase: Phase,
    record: Record,
    msgs,
    h,
    existing: AISuggestion | None = None,
) -> AISuggestion:
    result = await client.chat(res.endpoint, msgs)
    db.add(
        AIUsage(
            project_id=project.id,
            provider_id=res.provider.id,
            model=res.choice.model,
            task="screening",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=res.cost(result.input_tokens, result.output_tokens),
        )
    )
    answer = normalize_answer(client.parse_json(result.content))
    vocabulary = [t.name for t in get_settings(project).tag_vocabulary]
    ai = project_ai(project)
    answer["tags"] = clean_tags(answer["tags"], vocabulary) if ai.suggest_tags else []
    if not ai.suggest_reasons:
        answer["exclusion_reason"] = ""
    if existing is not None:
        # Refazer: a resposta nova substitui a antiga e passa a ser a mais recente
        for key, value in answer.items():
            setattr(existing, key, value)
        existing.created_at = utcnow()
        return existing
    sug = AISuggestion(
        project_id=project.id,
        record_id=record.id,
        phase=phase,
        model_key=res.model_key,
        prompt_hash=h,
        **answer,
    )
    db.add(sug)
    return sug


async def run_screening(
    db: AsyncSession,
    project: Project,
    phase: Phase,
    scope: str,
    limit: int | None,
    progress: Callable[[int, int], None] | None = None,
    force: bool = False,
    should_stop: Callable[[], Awaitable[bool]] | None = None,
) -> dict:
    ai = project_ai(project)
    res = await resolve(db, "screening", ai.local_only)
    settings = get_settings(project)
    bot = await bot_user(db)
    ids = await target_ids(db, project, phase, scope, limit)
    records = await _records(db, ids)
    as_reviewer = scope == "pending" and ai.mode == "second_reviewer"
    stats = {
        "total": len(records),
        "done": 0,
        "cached": 0,
        "errors": 0,
        "stopped": None,
        "phase": str(phase),
    }
    used = await spent(db, project.id)
    consecutive_failures = 0
    for i, record in enumerate(records):
        if should_stop is not None and await should_stop():
            stats["stopped"] = "user"
            break
        msgs = build_messages(
            project,
            settings,
            record,
            ai.extra_instructions,
            suggest_tags=ai.suggest_tags,
            suggest_reasons=ai.suggest_reasons,
        )
        h = prompt_hash(msgs)
        old = (await _cached(db, phase, res.model_key, {record.id: h})).get(record.id)
        sug = None if force else old
        if sug is not None:
            stats["cached"] += 1
        else:
            guess = res.cost(estimate_tokens(msgs), OUTPUT_TOKENS_GUESS)
            if ai.budget_usd is not None and used + guess > ai.budget_usd:
                stats["stopped"] = "budget"
                break
            try:
                sug = await screen_one(db, project, res, phase, record, msgs, h, existing=old)
                consecutive_failures = 0
            except AIError as exc:
                stats["errors"] += 1
                stats["last_error"] = str(exc)[:300]
                consecutive_failures += 1
                await db.commit()  # guarda o registro de uso mesmo quando a resposta falha
                if str(exc) == "quota_exhausted":
                    # Acabou a cota do dia na faixa gratuita: insistir só gasta pedidos.
                    # O que já foi feito fica em cache e "continuar" retoma amanhã.
                    stats["stopped"] = "quota"
                    break
                if consecutive_failures >= 3 and str(exc).startswith(
                    ("connection", "http", "rate_limited")
                ):
                    raise
                continue
            used = await spent(db, project.id) if res.choice.price_input else used
        if as_reviewer:
            db.add(
                DecisionEvent(
                    project_id=project.id,
                    record_id=record.id,
                    user_id=bot.id,
                    phase=phase,
                    decision=Decision(sug.decision),
                    reason_ids=[],
                    labels=[],
                    note=sug.justification[:2000],
                )
            )
        stats["done"] += 1
        await db.commit()
        if progress:
            progress(i + 1, len(records))
    stats["spent_usd"] = round(await spent(db, project.id), 4)
    return stats


# --- Calibração ----------------------------------------------------------------------


async def latest_suggestions(
    db: AsyncSession, project_id: uuid.UUID, phase: Phase, record_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, AISuggestion]:
    stmt = select(AISuggestion).where(
        AISuggestion.project_id == project_id, AISuggestion.phase == phase
    )
    if record_ids is not None:
        stmt = stmt.where(AISuggestion.record_id.in_(record_ids))
    out: dict[uuid.UUID, AISuggestion] = {}
    for s in (await db.execute(stmt.order_by(AISuggestion.created_at))).scalars():
        out[s.record_id] = s
    return out


async def calibration(db: AsyncSession, project: Project, phase: Phase) -> dict:
    """Compara a IA com a decisão humana. "Talvez" conta como inclusão (não perde estudo)."""
    bot = await bot_user(db)
    states = await compute_states(db, project, phase)
    human = {rid: hs for rid, st in states.items() if (hs := _human_state(st, bot.id))}
    sugs = await latest_suggestions(db, project.id, phase, list(human))
    tp = fp = tn = fn = maybe = 0
    pairs = []
    for rid, s in sugs.items():
        truth = human[rid]
        ai_inc = s.decision != Decision.exclude
        maybe += s.decision == Decision.maybe
        if truth == Decision.include:
            tp += ai_inc
            fn += not ai_inc
        else:
            fp += ai_inc
            tn += not ai_inc
        pairs.append(("include" if ai_inc else "exclude", truth))
    k, _ = kappa(pairs)
    return {
        "n": len(sugs),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "maybe": maybe,
        "sensitivity": round(tp / (tp + fn), 3) if tp + fn else None,
        "specificity": round(tn / (tn + fp), 3) if tn + fp else None,
        "kappa": round(k, 3) if k is not None else None,
    }
