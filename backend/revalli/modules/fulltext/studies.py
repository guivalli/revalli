"""Agrupamento de relatórios do mesmo estudo e sugestões pelo número de registro do ensaio."""

import re
import uuid
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project, Record
from revalli.modules.fulltext.models import FilePage, RecordFile, Study, StudyReport
from revalli.modules.screening.models import Phase
from revalli.modules.screening.service import compute_states

# Números de registro de ensaios clínicos nos principais registros públicos
TRIAL_ID = re.compile(
    r"\b("
    r"NCT\d{8}"
    r"|ISRCTN\d{8}"
    r"|ACTRN\d{14}"
    r"|ChiCTR-?[A-Z]{0,4}-?\d{6,12}"
    r"|DRKS\d{8}"
    r"|EudraCT[\s:№#]*\d{4}-\d{6}-\d{2}"
    r"|UMIN\d{9}"
    r"|IRCT\d{8,14}N\d{1,3}"
    r"|CTRI/\d{4}/\d{2,3}/\d{6}"
    r"|PACTR\d{15}"
    r"|RBR-[0-9a-z]{6,8}"
    r"|jRCT[0-9a-z]{10}"
    r"|CRD\d{11}"
    r")\b",
    re.IGNORECASE,
)


def trial_ids(text: str) -> set[str]:
    out = set()
    for m in TRIAL_ID.finditer(text or ""):
        value = m.group(1).upper()
        if value.startswith("EUDRACT"):
            value = "EudraCT " + re.sub(r"^EUDRACT[\s:№#]*", "", value)
        out.add(value)
    return out


def default_label(r: Record) -> str:
    first = (r.authors[0] if r.authors else "").split(",")[0].strip()
    return " ".join(x for x in (first, str(r.year or "")) if x) or (r.title or "")[:80]


async def reports_of(db: AsyncSession, record_ids: list[uuid.UUID]) -> dict[uuid.UUID, StudyReport]:
    if not record_ids:
        return {}
    rows = await db.execute(
        select(StudyReport)
        .where(StudyReport.record_id.in_(record_ids))
        .execution_options(populate_existing=True)
    )
    return {r.record_id: r for r in rows.scalars()}


async def study_keys(db: AsyncSession, record_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    """Para cada registro, o id do estudo (ou o próprio id, se não estiver agrupado)."""
    links = await reports_of(db, record_ids)
    return {rid: (links[rid].study_id if rid in links else rid) for rid in record_ids}


async def _cleanup(db: AsyncSession, study_id: uuid.UUID) -> None:
    """Um estudo com um só relatório deixa de ser grupo; garante um relatório principal."""
    reports = list(
        (await db.execute(select(StudyReport).where(StudyReport.study_id == study_id))).scalars()
    )
    if len(reports) < 2:
        await db.execute(delete(Study).where(Study.id == study_id))
        return
    if not any(r.is_primary for r in reports):
        reports[0].is_primary = True


async def group(
    db: AsyncSession,
    project: Project,
    record_ids: list[uuid.UUID],
    label: str = "",
) -> Study:
    """Junta os registros num estudo. Se algum já estiver num estudo, os outros entram nele
    (e estudos diferentes são fundidos)."""
    ids = list(dict.fromkeys(record_ids))
    records = {
        r.id: r
        for r in (
            await db.execute(
                select(Record).where(Record.id.in_(ids), Record.project_id == project.id)
            )
        ).scalars()
    }
    if len(records) != len(ids):
        raise LookupError("record_not_found")
    links = await reports_of(db, ids)
    existing = list(dict.fromkeys(links[r].study_id for r in ids if r in links))
    if existing:
        study = await db.get(Study, existing[0])
        others = existing[1:]
        if others:
            await db.execute(
                StudyReport.__table__.update()
                .where(StudyReport.study_id.in_(others))
                .values(study_id=study.id, is_primary=False)
            )
            await db.execute(delete(Study).where(Study.id.in_(others)))
    else:
        study = Study(project_id=project.id, label=label or default_label(records[ids[0]]))
        db.add(study)
        await db.flush()
    if label:
        study.label = label
    links = await reports_of(db, ids)
    for i, rid in enumerate(ids):
        if rid not in links:
            db.add(
                StudyReport(record_id=rid, study_id=study.id, is_primary=not existing and i == 0)
            )
    await db.flush()
    await _cleanup(db, study.id)
    await db.commit()
    return study


async def ungroup_record(db: AsyncSession, study: Study, record_id: uuid.UUID) -> None:
    await db.execute(
        delete(StudyReport).where(
            StudyReport.study_id == study.id, StudyReport.record_id == record_id
        )
    )
    await db.flush()
    await _cleanup(db, study.id)
    await db.commit()


async def set_primary(db: AsyncSession, study: Study, record_id: uuid.UUID) -> None:
    reports = (
        await db.execute(select(StudyReport).where(StudyReport.study_id == study.id))
    ).scalars()
    found = False
    for r in reports:
        r.is_primary = r.record_id == record_id
        found = found or r.is_primary
    if not found:
        raise LookupError("record_not_in_study")


def _record_out(r: Record, primary: bool, state: str | None) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "authors": r.authors[:3],
        "year": r.year,
        "doi": r.doi,
        "is_primary": primary,
        "state": state,
    }


async def list_studies(db: AsyncSession, project: Project, show_state: bool) -> list[dict]:
    rows = (
        await db.execute(
            select(Study, StudyReport, Record)
            .join(StudyReport, StudyReport.study_id == Study.id)
            .join(Record, Record.id == StudyReport.record_id)
            .where(Study.project_id == project.id)
            .order_by(Study.created_at, StudyReport.is_primary.desc(), Record.year, Record.title)
        )
    ).all()
    states = (
        await compute_states(db, project, Phase.full_text, [rec.id for _, _, rec in rows])
        if show_state and rows
        else {}
    )
    out: dict[uuid.UUID, dict] = {}
    for study, link, rec in rows:
        item = out.setdefault(study.id, {"id": study.id, "label": study.label, "reports": []})
        st = states.get(rec.id)
        item["reports"].append(_record_out(rec, link.is_primary, st.state if st else None))
    return list(out.values())


async def suggestions(db: AsyncSession, project: Project) -> list[dict]:
    """Registros da fase de texto completo que citam o mesmo número de registro de ensaio
    (no título, no resumo ou no PDF) e ainda não estão no mesmo estudo."""
    ids = list(await compute_states(db, project, Phase.full_text))
    if not ids:
        return []
    records = {
        r.id: r for r in (await db.execute(select(Record).where(Record.id.in_(ids)))).scalars()
    }
    found: dict[uuid.UUID, set[str]] = {
        rid: trial_ids(f"{r.title}\n{r.abstract}") for rid, r in records.items()
    }
    pages = await db.execute(
        select(RecordFile.record_id, FilePage.text)
        .join(FilePage, FilePage.file_id == RecordFile.id)
        .where(RecordFile.record_id.in_(ids))
    )
    for rid, text in pages.all():
        found[rid] |= trial_ids(text)
    by_id: dict[str, list[uuid.UUID]] = defaultdict(list)
    for rid, keys in found.items():
        for k in keys:
            by_id[k].append(rid)
    keys = await study_keys(db, ids)
    out, seen = [], set()
    for k, rids in sorted(by_id.items()):
        group_ids = frozenset(rids)
        if len(rids) < 2 or group_ids in seen or len({keys[r] for r in rids}) < 2:
            continue
        seen.add(group_ids)
        recs = sorted((records[r] for r in rids), key=lambda r: (r.year or 0, r.title))
        out.append({"key": k, "records": [_record_out(r, False, None) for r in recs]})
    return out[:100]


async def candidates(db: AsyncSession, project: Project, q: str) -> list[dict]:
    """Registros da fase de texto completo para montar um grupo à mão."""
    ids = list(await compute_states(db, project, Phase.full_text))
    if not ids:
        return []
    stmt = select(Record).where(Record.id.in_(ids))
    for word in q.split()[:6]:
        stmt = stmt.where(Record.title.ilike(f"%{word}%") | Record.doi.ilike(f"%{word}%"))
    records = list((await db.execute(stmt.order_by(Record.title).limit(30))).scalars())
    links = await reports_of(db, [r.id for r in records])
    return [
        {
            "id": r.id,
            "title": r.title,
            "authors": r.authors[:3],
            "year": r.year,
            "study_id": links[r.id].study_id if r.id in links else None,
        }
        for r in records
    ]
