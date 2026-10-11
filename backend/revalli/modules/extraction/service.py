"""Extração de dados: estudos a extrair, validação das respostas, comparação e consenso."""

import csv
import io
import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project, Record, Study, StudyReport, User
from revalli.modules.extraction.models import Extraction, ExtractionForm
from revalli.modules.extraction.templates import effective_values, suggest
from revalli.modules.fulltext.studies import default_label
from revalli.modules.screening.models import Phase
from revalli.modules.screening.service import State, compute_states

MAX_TEXT = 20_000
MAX_ROWS = 50


@dataclass
class Unit:
    """Um estudo a extrair: o relatório principal e os demais relatórios do mesmo estudo."""

    record: Record
    report_ids: list[uuid.UUID]
    label: str
    extractions: list[Extraction] = field(default_factory=list)


async def units(db: AsyncSession, project: Project) -> list[Unit]:
    """Estudos incluídos na fase de texto completo (relatórios agrupados contam uma vez)."""
    states = await compute_states(db, project, Phase.full_text)
    included = [rid for rid, st in states.items() if st.state == State.included]
    if not included:
        return []
    records = {
        r.id: r for r in (await db.execute(select(Record).where(Record.id.in_(included)))).scalars()
    }
    links = (
        await db.execute(
            select(StudyReport, Study)
            .join(Study, Study.id == StudyReport.study_id)
            .where(StudyReport.record_id.in_(included))
        )
    ).all()
    groups: dict[uuid.UUID, list[tuple[StudyReport, Study]]] = {}
    for link, study in links:
        groups.setdefault(study.id, []).append((link, study))
    out: list[Unit] = []
    grouped: set[uuid.UUID] = set()
    for members in groups.values():
        study = members[0][1]
        primary = next(
            (lk.record_id for lk, _ in members if lk.is_primary), members[0][0].record_id
        )
        ids = [lk.record_id for lk, _ in members]
        grouped |= set(ids)
        out.append(
            Unit(records[primary], [primary] + [i for i in ids if i != primary], study.label)
        )
    for rid, r in records.items():
        if rid not in grouped:
            out.append(Unit(r, [rid], default_label(r)))
    out.sort(key=lambda u: (u.label.lower(), u.record.year or 0, u.record.title))
    return out


async def unit_for(db: AsyncSession, project: Project, record_id: uuid.UUID) -> Unit | None:
    return next((u for u in await units(db, project) if u.record.id == record_id), None)


# --- Validação ----------------------------------------------------------------------------


class FieldError(ValueError):
    def __init__(self, field_id: str, code: str):
        super().__init__(f"{field_id}: {code}")
        self.field_id = field_id


def _number(v: Any, integer: bool, fid: str) -> float | int | None:
    if v is None or v == "":
        return None
    if isinstance(v, str):
        v = v.strip().replace(",", ".")
    try:
        n = float(v)
    except (TypeError, ValueError) as exc:
        raise FieldError(fid, "not_a_number") from exc
    if not math.isfinite(n):
        raise FieldError(fid, "not_a_number")
    if integer:
        if n != int(n):
            raise FieldError(fid, "not_an_integer")
        return int(n)
    return n


def _text(v: Any, fid: str) -> str | None:
    if v is None:
        return None
    if not isinstance(v, str | int | float):
        raise FieldError(fid, "invalid_value")
    s = str(v).strip()
    if len(s) > MAX_TEXT:
        raise FieldError(fid, "too_long")
    return s or None


def clean_value(f: dict, v: Any) -> Any:
    fid, t = f["id"], f["type"]
    if t in ("text", "long_text"):
        return _text(v, fid)
    if t in ("number", "integer"):
        return _number(v, t == "integer", fid)
    if t in ("choice", "signal", "judgement"):
        if v in (None, ""):
            return None
        if v not in f["options"]:
            raise FieldError(fid, "invalid_option")
        return v
    if t == "multi":
        if not v:
            return None
        if not isinstance(v, list) or any(x not in f["options"] for x in v):
            raise FieldError(fid, "invalid_option")
        return [o for o in f["options"] if o in v]
    if t == "boolean":
        if v is None or v == "":
            return None
        if not isinstance(v, bool):
            raise FieldError(fid, "invalid_value")
        return v
    if t == "table":
        if not v:
            return None
        if not isinstance(v, list) or len(v) > MAX_ROWS:
            raise FieldError(fid, "invalid_value")
        rows = []
        for row in v:
            if not isinstance(row, dict):
                raise FieldError(fid, "invalid_value")
            clean = {}
            for col in f["columns"]:
                cell = row.get(col["id"])
                if col["type"] == "text":
                    clean[col["id"]] = _text(cell, fid)
                else:
                    clean[col["id"]] = _number(cell, col["type"] == "integer", fid)
            if any(x is not None for x in clean.values()):
                rows.append(clean)
        return rows or None
    return None


def visible(f: dict, values: dict) -> bool:
    return all(values.get(c["field"]) in c["values"] for c in f.get("show_if") or [])


def clean_values(fields: list[dict], values: dict) -> dict:
    """Valida e normaliza. Campos desconhecidos ou ocultos pela lógica condicional saem."""
    out: dict[str, Any] = {}
    for f in fields:
        if f["type"] == "section" or f["id"] not in values:
            continue
        v = clean_value(f, values[f["id"]])
        if v is not None:
            out[f["id"]] = v
    return {k: v for k, v in out.items() if visible(_by_id(fields)[k], out)}


def _by_id(fields: list[dict]) -> dict[str, dict]:
    return {f["id"]: f for f in fields}


def missing_required(fields: list[dict], values: dict) -> list[str]:
    return [
        f["id"]
        for f in fields
        if f.get("required") and visible(f, values) and values.get(f["id"]) in (None, "", [])
    ]


# --- Comparação ---------------------------------------------------------------------------


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return " ".join(v.casefold().split())
    if isinstance(v, float) and v == int(v):
        return int(v)
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in sorted(v.items())}
    return v


def compare(fields: list[dict], extractions: list[Extraction]) -> tuple[list[dict], dict]:
    """Campo a campo: o valor de cada extração e se todos concordam. Também devolve os valores
    em que houve acordo, para começar o consenso."""
    rows, agreed = [], {}
    eff = {e.id: effective_values(fields, e.values) for e in extractions}
    for f in fields:
        if f["type"] == "section":
            continue
        vals = {str(e.id): eff[e.id].get(f["id"]) for e in extractions}
        normed = [_norm(v) for v in vals.values()]
        agree = all(n == normed[0] for n in normed) if normed else True
        if agree and normed and normed[0] is not None:
            agreed[f["id"]] = next(iter(vals.values()))
        if any(v is not None for v in vals.values()):
            rows.append({"field_id": f["id"], "values": vals, "agree": agree})
    return rows, agreed


def unit_state(form: ExtractionForm, exts: list[Extraction]) -> str:
    if any(e.kind == "consensus" for e in exts):
        return "resolved"
    done = [e for e in exts if e.status == "done" and e.kind != "consensus"]
    started = [e for e in exts if e.kind != "consensus"]
    if not started:
        return "pending"
    humans_done = [e for e in done if e.kind == "reviewer"]
    if len(humans_done) < form.extractors:
        return "in_progress"
    if len(done) < 2:
        return "ready"
    rows, _ = compare(form.fields, done)
    return "agreed" if all(r["agree"] for r in rows) else "conflict"


def final_values(form: ExtractionForm, exts: list[Extraction]) -> tuple[dict, str]:
    """Valores que valem para o estudo e de onde vieram."""
    cons = next((e for e in exts if e.kind == "consensus"), None)
    if cons:
        return effective_values(form.fields, cons.values), "consensus"
    done = [e for e in exts if e.status == "done" and e.kind == "reviewer"]
    if not done:
        return {}, "none"
    if len(done) == 1:
        return effective_values(form.fields, done[0].values), "single"
    rows, agreed = compare(form.fields, done)
    return agreed, "agreed" if all(r["agree"] for r in rows) else "conflict"


async def load_extractions(
    db: AsyncSession, form: ExtractionForm, record_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, list[Extraction]]:
    stmt = select(Extraction).where(Extraction.form_id == form.id)
    if record_ids is not None:
        stmt = stmt.where(Extraction.record_id.in_(record_ids))
    out: dict[uuid.UUID, list[Extraction]] = {}
    for e in (await db.execute(stmt.order_by(Extraction.created_at))).scalars():
        out.setdefault(e.record_id, []).append(e)
    return out


async def user_names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))
    return dict(rows.all())


def extraction_out(form: ExtractionForm, e: Extraction, names: dict) -> dict:
    return {
        "id": e.id,
        "kind": e.kind,
        "user_id": e.user_id,
        "user_name": names.get(e.user_id, ""),
        "values": e.values,
        "quotes": e.quotes,
        "status": e.status,
        "form_version": e.form_version,
        "updated_at": e.updated_at,
        "suggested": suggest(form.fields, e.values) if form.kind == "rob" else {},
    }


# --- Exportação ---------------------------------------------------------------------------


def _cell(v: Any) -> Any:
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return "" if v is None else v


async def export_csv(db: AsyncSession, project: Project, form: ExtractionForm, layout: str) -> str:
    """``wide``: uma linha por estudo e uma coluna por campo. ``long``: uma linha por valor,
    com as tabelas desdobradas (bom para R e planilhas de meta-análise)."""
    us = await units(db, project)
    exts = await load_extractions(db, form, [u.record.id for u in us])
    fields = [f for f in form.fields if f["type"] != "section"]
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, lineterminator="\r\n")
    base = ["study", "record_id", "title", "year", "doi", "status"]
    if layout == "long":
        w.writerow([*base, "field", "label", "row", "column", "value"])
    else:
        cols = []
        for f in fields:
            if f["type"] == "table":
                cols += [f"{f['id']}.{c['id']}" for c in f["columns"]]
            else:
                cols.append(f["id"])
        w.writerow(base + cols)
    for u in us:
        vals, source = final_values(form, exts.get(u.record.id, []))
        head = [u.label, str(u.record.id), u.record.title, u.record.year or "", u.record.doi or ""]
        head = [_cell(x) for x in head] + [source]
        if layout == "long":
            for f in fields:
                v = vals.get(f["id"])
                if v is None:
                    continue
                if f["type"] == "table":
                    for i, row in enumerate(v, 1):
                        for c in f["columns"]:
                            if row.get(c["id"]) is not None:
                                w.writerow(
                                    [*head, f["id"], f["label"], i, c["id"], _cell(row[c["id"]])]
                                )
                else:
                    w.writerow([*head, f["id"], f["label"], "", "", _cell(v)])
        else:
            row = list(head)
            for f in fields:
                v = vals.get(f["id"])
                if f["type"] == "table":
                    for c in f["columns"]:
                        row.append("; ".join(str(_cell(r.get(c["id"]))) for r in v or []))
                else:
                    row.append(_cell(v))
            w.writerow(row)
    return buf.getvalue()


async def rob_summary(db: AsyncSession, project: Project, form: ExtractionForm) -> dict:
    """Julgamentos por domínio de cada estudo, para os gráficos de semáforo e de resumo."""
    judgements = [f for f in form.fields if f["type"] == "judgement"]
    sections = {f.get("domain"): f["label"] for f in form.fields if f["type"] == "section"}
    domains = [
        {
            "id": f["id"],
            "domain": f.get("domain", ""),
            "label": sections.get(f.get("domain"), f["label"]),
        }
        for f in judgements
    ]
    scale = judgements[0]["options"] if judgements else []
    us = await units(db, project)
    exts = await load_extractions(db, form, [u.record.id for u in us])
    rows = []
    for u in us:
        vals, source = final_values(form, exts.get(u.record.id, []))
        if source == "none":
            continue
        rows.append(
            {
                "record_id": u.record.id,
                "label": u.label,
                "judgements": {f["id"]: vals.get(f["id"]) for f in judgements},
            }
        )
    return {"domains": domains, "scale": scale, "rows": rows}
