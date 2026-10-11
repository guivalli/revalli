"""Relatórios: contagens do fluxograma PRISMA 2020 e exportação das referências."""

import csv
import io
import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import (
    DuplicateGroup,
    ExclusionReason,
    Project,
    Record,
    Search,
    Study,
    StudyReport,
)
from revalli.modules.fulltext.studies import study_keys
from revalli.modules.records.models import DuplicateStatus
from revalli.modules.screening.models import Decision, Phase
from revalli.modules.screening.service import RecordState, State, compute_states

STATE_LABELS = {
    State.pending: "pendente",
    State.included: "incluído",
    State.excluded: "excluído",
    State.conflict: "conflito",
}


def main_reason(st: RecordState) -> str | None:
    """Motivo principal de um registro excluído: o da decisão final ou o primeiro dado
    por um revisor que excluiu."""
    if st.final is not None:
        return st.final.reason_ids[0] if st.final.reason_ids else None
    for ev in sorted(st.votes.values(), key=lambda e: e.created_at):
        if ev.decision == Decision.exclude and ev.reason_ids:
            return ev.reason_ids[0]
    return None


async def reason_labels(db: AsyncSession, project_id: uuid.UUID) -> dict[str, str]:
    rows = await db.execute(
        select(ExclusionReason.id, ExclusionReason.label).where(
            ExclusionReason.project_id == project_id
        )
    )
    return {str(i): label for i, label in rows}


def _count(states: dict[uuid.UUID, RecordState], state: str) -> int:
    return sum(1 for st in states.values() if st.state == state)


async def study_labels(db: AsyncSession, record_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not record_ids:
        return {}
    rows = await db.execute(
        select(StudyReport.record_id, Study.label)
        .join(Study, Study.id == StudyReport.study_id)
        .where(StudyReport.record_id.in_(record_ids))
    )
    return {rid: label for rid, label in rows.all()}


async def prisma_counts(db: AsyncSession, project: Project) -> dict:
    by_source = (
        await db.execute(
            select(Search.source, Search.method, func.count(Record.id))
            .join(Record, Record.search_id == Search.id)
            .where(Search.project_id == project.id)
            .group_by(Search.source, Search.method)
            .order_by(Search.method, Search.source)
        )
    ).all()
    total = (
        await db.execute(select(func.count()).where(Record.project_id == project.id))
    ).scalar_one()
    duplicates = (
        await db.execute(
            select(func.count())
            .select_from(Record)
            .join(DuplicateGroup, DuplicateGroup.id == Record.duplicate_group_id)
            .where(
                Record.project_id == project.id,
                DuplicateGroup.status == DuplicateStatus.confirmed,
                DuplicateGroup.primary_record_id != Record.id,
            )
        )
    ).scalar_one()
    ta = await compute_states(db, project, Phase.title_abstract)
    ft = await compute_states(db, project, Phase.full_text)
    labels = await reason_labels(db, project.id)
    included = [rid for rid, st in ft.items() if st.state == State.included]
    keys = await study_keys(db, included)
    reasons = Counter(main_reason(st) for st in ft.values() if st.state == State.excluded)
    no_reason = reasons.pop(None, 0)
    return {
        "identification": {
            "by_source": [
                {"source": s, "method": m, "records": n} for s, m, n in by_source if m == "database"
            ],
            # Outros métodos (busca de citações), que o PRISMA 2020 mostra à parte
            "other_methods": [
                {"source": s, "method": m, "records": n} for s, m, n in by_source if m != "database"
            ],
            "total": total,
            "duplicates_removed": duplicates,
        },
        "screening": {
            "screened": len(ta),
            "excluded": _count(ta, State.excluded),
            "pending": _count(ta, State.pending) + _count(ta, State.conflict),
        },
        "retrieval": {
            "sought": len(ft),
            # Sem fase de PDFs ainda, nada é marcado como não recuperado
            "not_retrieved": 0,
        },
        "eligibility": {
            "assessed": _count(ft, State.included) + _count(ft, State.excluded),
            "excluded": _count(ft, State.excluded),
            "reasons": [
                {"reason": labels.get(rid, "?"), "count": n} for rid, n in reasons.most_common()
            ]
            + ([{"reason": None, "count": no_reason}] if no_reason else []),
            "pending": _count(ft, State.pending) + _count(ft, State.conflict),
        },
        "included": len(set(keys.values())),
        "included_reports": len(included),
    }


# --- Exportação ----------------------------------------------------------------


def _ris_line(tag: str, value: str) -> str:
    return f"{tag}  - {' '.join(str(value).split())}"


def to_ris(rows: list[dict]) -> str:
    out: list[str] = []
    for row in rows:
        r: Record = row["record"]
        out.append(_ris_line("TY", "JOUR"))
        if r.title:
            out.append(_ris_line("TI", r.title))
        out.extend(_ris_line("AU", a) for a in r.authors)
        if r.year:
            out.append(_ris_line("PY", str(r.year)))
        if r.journal:
            out.append(_ris_line("JO", r.journal))
        if r.volume:
            out.append(_ris_line("VL", r.volume))
        if r.issue:
            out.append(_ris_line("IS", r.issue))
        if r.pages:
            first, _, last = r.pages.partition("-")
            out.append(_ris_line("SP", first))
            if last:
                out.append(_ris_line("EP", last))
        if r.doi:
            out.append(_ris_line("DO", r.doi))
        if r.pmid:
            out.append(_ris_line("AN", r.pmid))
        if r.url:
            out.append(_ris_line("UR", r.url))
        if r.language:
            out.append(_ris_line("LA", r.language))
        out.extend(_ris_line("KW", k) for k in r.keywords)
        if r.abstract:
            out.append(_ris_line("AB", r.abstract))
        out.append(_ris_line("N1", row["summary"]))
        out.append("ER  - ")
        out.append("")
    return "\r\n".join(out)


CSV_FIELDS = [
    "id",
    "title",
    "authors",
    "year",
    "journal",
    "volume",
    "issue",
    "pages",
    "doi",
    "pmid",
    "url",
    "language",
    "keywords",
    "abstract",
    "source",
    "state",
    "exclusion_reasons",
    "labels",
    "decisions",
    "notes",
    "study",
]


def _safe_cell(v: str) -> str:
    # Evita que planilhas interpretem o conteúdo como fórmula
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    w.writeheader()
    for row in rows:
        r: Record = row["record"]
        values = {
            "id": str(r.id),
            "title": r.title,
            "authors": "; ".join(r.authors),
            "year": r.year or "",
            "journal": r.journal,
            "volume": r.volume,
            "issue": r.issue,
            "pages": r.pages,
            "doi": r.doi or "",
            "pmid": r.pmid or "",
            "url": r.url,
            "language": r.language,
            "keywords": "; ".join(r.keywords),
            "abstract": r.abstract,
            "source": row["source"],
            "state": row["state"],
            "exclusion_reasons": "; ".join(row["reasons"]),
            "labels": "; ".join(row["labels"]),
            "decisions": "; ".join(row["decisions"]),
            "notes": " | ".join(row["notes"]),
            "study": row.get("study", ""),
        }
        w.writerow({k: _safe_cell(v) if isinstance(v, str) else v for k, v in values.items()})
    return buf.getvalue()
