"""Síntese qualitativa (códigos e trechos) e checklists de relato."""

import csv
import io
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import AIUsage, ExtractionForm, Project, RecordFile, Search, User
from revalli.modules.ai.service import project_ai
from revalli.modules.extraction.service import Unit, units
from revalli.modules.reports.service import prisma_counts
from revalli.modules.screening.service import get_settings
from revalli.modules.synthesis.models import Code, Excerpt, ExcerptCode


async def codes_of(db: AsyncSession, project_id: uuid.UUID) -> list[Code]:
    rows = await db.execute(
        select(Code).where(Code.project_id == project_id).order_by(Code.position, Code.name)
    )
    return list(rows.scalars())


def descendants(codes: list[Code], root: uuid.UUID) -> set[uuid.UUID]:
    children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
    for c in codes:
        children.setdefault(c.parent_id, []).append(c.id)
    out, stack = set(), [root]
    while stack:
        cid = stack.pop()
        out.add(cid)
        stack.extend(children.get(cid, []))
    return out


def path(codes: list[Code], code_id: uuid.UUID) -> str:
    by_id = {c.id: c for c in codes}
    names, cur = [], by_id.get(code_id)
    while cur is not None:
        names.append(cur.name)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return " > ".join(reversed(names))


async def excerpt_counts(db: AsyncSession, project_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(ExcerptCode.code_id, func.count())
        .join(Excerpt, Excerpt.id == ExcerptCode.excerpt_id)
        .where(Excerpt.project_id == project_id)
        .group_by(ExcerptCode.code_id)
    )
    return dict(rows.all())


async def drop_orphans(db: AsyncSession, project_id: uuid.UUID) -> None:
    """Trechos que ficaram sem nenhum código (o código foi apagado) deixam de existir."""
    await db.execute(
        delete(Excerpt).where(
            Excerpt.project_id == project_id,
            ~select(ExcerptCode.excerpt_id).where(ExcerptCode.excerpt_id == Excerpt.id).exists(),
        )
    )


async def excerpts_out(
    db: AsyncSession, excerpts: list[Excerpt], labels: dict[uuid.UUID, str]
) -> list[dict]:
    if not excerpts:
        return []
    ids = [e.id for e in excerpts]
    links: dict[uuid.UUID, list[uuid.UUID]] = {}
    for eid, cid in (
        await db.execute(
            select(ExcerptCode.excerpt_id, ExcerptCode.code_id).where(
                ExcerptCode.excerpt_id.in_(ids)
            )
        )
    ).all():
        links.setdefault(eid, []).append(cid)
    user_ids = {e.user_id for e in excerpts if e.user_id}
    names = dict(
        (await db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))).all()
    )
    file_ids = {e.file_id for e in excerpts if e.file_id}
    file_records = dict(
        (
            await db.execute(
                select(RecordFile.id, RecordFile.record_id).where(RecordFile.id.in_(file_ids))
            )
        ).all()
    )
    return [
        {
            "id": e.id,
            "file_record_id": file_records.get(e.file_id),
            "record_id": e.record_id,
            "study": labels.get(e.record_id, ""),
            "file_id": e.file_id,
            "page": e.page,
            "text": e.text,
            "note": e.note,
            "code_ids": links.get(e.id, []),
            "user_id": e.user_id,
            "user_name": names.get(e.user_id, ""),
            "created_at": e.created_at,
        }
        for e in excerpts
    ]


async def coding_units(db: AsyncSession, project: Project) -> list[Unit]:
    return await units(db, project)


async def unit_stats(db: AsyncSession, project: Project, us: list[Unit]) -> list[dict]:
    ids = [u.record.id for u in us]
    counts = dict(
        (
            await db.execute(
                select(Excerpt.record_id, func.count())
                .where(Excerpt.project_id == project.id, Excerpt.record_id.in_(ids))
                .group_by(Excerpt.record_id)
            )
        ).all()
    )
    all_reports = [r for u in us for r in u.report_ids]
    with_pdf = set(
        (
            await db.execute(
                select(RecordFile.record_id).where(RecordFile.record_id.in_(all_reports))
            )
        ).scalars()
    )
    return [
        {
            "record_id": u.record.id,
            "label": u.label,
            "report_ids": u.report_ids,
            "title": u.record.title,
            "year": u.record.year,
            "excerpts": counts.get(u.record.id, 0),
            "has_pdf": any(r in with_pdf for r in u.report_ids),
        }
        for u in us
    ]


async def matrix_cells(db: AsyncSession, project_id: uuid.UUID) -> dict[str, dict[str, int]]:
    rows = await db.execute(
        select(ExcerptCode.code_id, Excerpt.record_id, func.count())
        .join(Excerpt, Excerpt.id == ExcerptCode.excerpt_id)
        .where(Excerpt.project_id == project_id)
        .group_by(ExcerptCode.code_id, Excerpt.record_id)
    )
    cells: dict[str, dict[str, int]] = {}
    for cid, rid, n in rows.all():
        cells.setdefault(str(cid), {})[str(rid)] = n
    return cells


def safe_cell(v: str) -> str:
    # Evita que planilhas interpretem o conteúdo como fórmula
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v


def excerpts_csv(codes: list[Code], rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["code", "code_path", "study", "page", "excerpt", "note", "coder", "created_at"])
    by_id = {c.id: c for c in codes}
    for r in rows:
        for cid in r["code_ids"]:
            w.writerow(
                [
                    safe_cell(by_id[cid].name),
                    safe_cell(path(codes, cid)),
                    safe_cell(r["study"]),
                    r["page"] or "",
                    safe_cell(r["text"]),
                    safe_cell(r["note"]),
                    safe_cell(r["user_name"]),
                    r["created_at"].isoformat(),
                ]
            )
    return buf.getvalue()


# --- Checklists -------------------------------------------------------------------


async def checklist_facts(db: AsyncSession, project: Project) -> dict:
    """O que o ReValli já sabe sobre o método, para sugerir o que escrever em cada item."""
    searches = (
        (
            await db.execute(
                select(Search).where(Search.project_id == project.id).order_by(Search.created_at)
            )
        )
        .scalars()
        .all()
    )
    s = get_settings(project)
    ai = project_ai(project)
    ai_calls = (
        await db.execute(
            select(AIUsage.task, func.count())
            .where(AIUsage.project_id == project.id)
            .group_by(AIUsage.task)
        )
    ).all()
    forms = (
        (
            await db.execute(
                select(ExtractionForm).where(
                    ExtractionForm.project_id == project.id, ExtractionForm.archived.is_(False)
                )
            )
        )
        .scalars()
        .all()
    )
    codes = (
        await db.execute(select(func.count()).where(Code.project_id == project.id))
    ).scalar_one()
    excerpts = (
        await db.execute(select(func.count()).where(Excerpt.project_id == project.id))
    ).scalar_one()
    return {
        "review_type": project.review_type,
        "searches": [
            {
                "source": x.source,
                "method": x.method,
                "searched_on": x.searched_on.isoformat() if x.searched_on else None,
                "has_query": bool(x.query.strip()),
                "via_api": x.file_format == "api",
                "reported": x.reported_count,
                "imported": x.imported_count,
            }
            for x in searches
        ],
        "screening": {
            "reviewers_title_abstract": s.reviewers_title_abstract,
            "reviewers_full_text": s.reviewers_full_text,
            "blind": s.blind,
            "has_criteria": bool(s.inclusion_criteria.strip() or s.exclusion_criteria.strip()),
        },
        "ai": {
            "enabled": ai.enabled,
            "mode": ai.mode,
            "local_only": ai.local_only,
            "calls": {task: n for task, n in ai_calls},
        },
        "forms": [
            {"name": f.name, "kind": f.kind, "template": f.template, "extractors": f.extractors}
            for f in forms
        ],
        "coding": {"codes": codes, "excerpts": excerpts},
        "prisma": await prisma_counts(db, project),
    }
