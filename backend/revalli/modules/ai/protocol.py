"""Ajuda da IA com o protocolo: detalhar critérios de elegibilidade e sugerir etiquetas."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import AISuggestion, AIUsage, Project, Record
from revalli.modules.ai import client
from revalli.modules.ai.client import AIError
from revalli.modules.ai.prompts import (
    build_criteria_messages,
    build_reasons_messages,
    build_tags_messages,
)
from revalli.modules.ai.service import (
    _records,
    _sample,
    latest_suggestions,
    project_ai,
    resolve,
)
from revalli.modules.screening.models import ExclusionReason, Phase
from revalli.modules.screening.schemas import CriterionItem, TagItem
from revalli.modules.screening.service import compute_states, get_settings

MAX_ITEMS = 40
MAX_QUESTIONS = 6
MAX_PROPOSED_TAGS = 20


def parse_criteria(data: dict) -> dict:
    """Valida a resposta; descarta itens malformados em vez de falhar a rodada inteira."""
    items = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        examples = raw.get("examples")
        try:
            item = CriterionItem(
                kind=str(raw.get("kind", "")).strip().lower(),
                name=str(raw.get("name") or "")[:150],
                definition=str(raw.get("definition") or "")[:2000],
                examples=[str(e) for e in examples] if isinstance(examples, list) else [],
            )
        except ValueError:
            continue
        items.append(item.model_dump())
    if not items:
        raise AIError("no_criteria_in_response")
    questions = [str(q).strip()[:400] for q in data.get("questions") or [] if str(q).strip()]
    return {
        "summary": str(data.get("summary") or "")[:1000],
        "items": items[:MAX_ITEMS],
        "questions": questions[:MAX_QUESTIONS],
    }


def parse_tags(data: dict) -> list[dict]:
    out, seen = [], set()
    for raw in data.get("tags") or []:
        if isinstance(raw, str):
            raw = {"name": raw}
        if not isinstance(raw, dict):
            continue
        try:
            tag = TagItem(
                name=" ".join(str(raw.get("name") or "").split())[:60],
                description=str(raw.get("description") or "")[:300],
            )
        except ValueError:
            continue
        if tag.name.lower() not in seen:
            seen.add(tag.name.lower())
            out.append(tag.model_dump())
    if not out:
        raise AIError("no_tags_in_response")
    return out[:MAX_PROPOSED_TAGS]


async def _chat(db: AsyncSession, project: Project, task: str, messages: list[dict]) -> dict:
    ai = project_ai(project)
    res = await resolve(db, "screening", ai.local_only)
    result = await client.chat(res.endpoint, messages)
    db.add(
        AIUsage(
            project_id=project.id,
            provider_id=res.provider.id,
            model=res.choice.model,
            task=task,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=res.cost(result.input_tokens, result.output_tokens),
        )
    )
    await db.commit()
    return client.parse_json(result.content)


async def organize_criteria(
    db: AsyncSession, project: Project, inclusion: str, exclusion: str, answers: str
) -> dict:
    messages = build_criteria_messages(project, inclusion, exclusion, answers)
    return parse_criteria(await _chat(db, project, "criteria", messages))


async def suggest_tags(db: AsyncSession, project: Project, sample: int) -> dict:
    settings = get_settings(project)
    states = await compute_states(db, project, Phase.title_abstract)
    records: list[Record] = await _records(db, _sample(list(states), sample))
    records = [r for r in records if (r.title or r.abstract)]
    if not records:
        raise AIError("no_records_to_sample")
    existing = [(t.name, t.description) for t in settings.tag_vocabulary]
    messages = build_tags_messages(project, existing, records)
    tags = parse_tags(await _chat(db, project, "tags", messages))
    return {"tags": tags, "sampled": len(records)}


MAX_RAW_REASONS = 150


async def raw_reason_counts(db: AsyncSession, project: Project) -> list[tuple[str, int]]:
    """Motivos propostos pela IA (última sugestão de cada registro) e quantos registros têm cada um."""
    counts: dict[str, int] = {}
    for phase in Phase:
        for sug in (await latest_suggestions(db, project.id, phase)).values():
            if sug.decision == "exclude" and sug.exclusion_reason.strip():
                counts[sug.exclusion_reason] = counts.get(sug.exclusion_reason, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return ranked[:MAX_RAW_REASONS]


async def active_reason_labels(db: AsyncSession, project_id) -> list[str]:
    rows = await db.execute(
        select(ExclusionReason.label)
        .where(ExclusionReason.project_id == project_id, ExclusionReason.archived.is_(False))
        .order_by(ExclusionReason.position, ExclusionReason.created_at)
    )
    return list(rows.scalars())


def parse_reason_groups(data: dict, raw: list[tuple[str, int]], existing: list[str]) -> list[dict]:
    """Cada motivo bruto cai em exatamente um grupo; o que a IA esqueceu vira grupo próprio."""
    by_lower = {label.lower(): (label, n) for label, n in raw}
    canon = {e.lower(): e for e in existing}
    assigned: set[str] = set()
    groups: list[dict] = []
    for g in data.get("groups") or []:
        if not isinstance(g, dict):
            continue
        members = []
        for m in g.get("members") or []:
            hit = by_lower.get(str(m).strip().lower())
            if hit and hit[0] not in assigned:
                assigned.add(hit[0])
                members.append(hit[0])
        if not members:
            continue
        label = " ".join(str(g.get("label") or "").split())[:200] or members[0]
        link = str(g.get("existing") or "").strip().lower()
        label = canon.get(link) or canon.get(label.lower()) or label
        groups.append({"label": label, "existing": label.lower() in canon, "members": members})
    for label, _ in raw:
        if label not in assigned:
            groups.append({"label": label, "existing": label.lower() in canon, "members": [label]})
    counts = dict(raw)
    for g in groups:
        g["count"] = sum(counts[m] for m in g["members"])
    return sorted(groups, key=lambda g: -g["count"])


async def organize_reasons(db: AsyncSession, project: Project) -> dict:
    raw = await raw_reason_counts(db, project)
    if not raw:
        raise AIError("no_reasons_to_group")
    existing = await active_reason_labels(db, project.id)
    messages = build_reasons_messages(project, raw, existing)
    data = await _chat(db, project, "reasons", messages)
    return {"groups": parse_reason_groups(data, raw, existing), "total": sum(n for _, n in raw)}


async def apply_reason_groups(
    db: AsyncSession, project: Project, groups: list[tuple[str, list[str]]]
) -> dict:
    """Cria (ou reaproveita) os motivos do protocolo e aponta as sugestões da IA para eles."""
    reasons = (
        (await db.execute(select(ExclusionReason).where(ExclusionReason.project_id == project.id)))
        .scalars()
        .all()
    )
    by_label = {r.label.lower(): r for r in reasons}
    position = (
        await db.execute(
            select(func.coalesce(func.max(ExclusionReason.position), -1)).where(
                ExclusionReason.project_id == project.id
            )
        )
    ).scalar_one()
    created = updated = 0
    for label, members in groups:
        label = label.strip()
        if not label:
            continue
        reason = by_label.get(label.lower())
        if reason is None:
            position += 1
            reason = ExclusionReason(project_id=project.id, label=label, position=position)
            db.add(reason)
            by_label[label.lower()] = reason
            created += 1
        elif reason.archived:
            reason.archived = False
        if members:
            res = await db.execute(
                update(AISuggestion)
                .where(
                    AISuggestion.project_id == project.id,
                    AISuggestion.exclusion_reason.in_(members),
                )
                .values(exclusion_reason=reason.label)
            )
            updated += res.rowcount or 0
    await db.commit()
    return {"created": created, "updated": updated}
