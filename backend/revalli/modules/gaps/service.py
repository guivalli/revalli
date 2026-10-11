"""Mapa de lacunas de evidência: estudos incluídos distribuídos por duas dimensões.

Cada dimensão é uma lista de categorias vinda dos códigos qualitativos (os filhos de um código)
ou de um campo de escolha dos formulários de extração. A célula é o conjunto de estudos que estão
nas duas categorias; células vazias são as lacunas."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import ExtractionForm, Project
from revalli.modules.extraction import service as extraction
from revalli.modules.extraction.service import Unit
from revalli.modules.synthesis import service as synthesis
from revalli.modules.synthesis.models import Excerpt, ExcerptCode

NONE_KEY = "__none__"
CHOICE_TYPES = ("choice", "multi")


class DimensionError(Exception):
    """A dimensão pedida não existe ou não serve (o código vira o detalhe do HTTP)."""


@dataclass
class Category:
    key: str
    label: str


@dataclass
class Dimension:
    source: str
    title: str
    categories: list[Category]
    # id do estudo (registro principal) -> chaves das categorias em que ele está
    members: dict[uuid.UUID, set[str]]


def parse_ref(ref: str) -> tuple[str, list[str]]:
    kind, *rest = ref.split(":")
    if kind == "codes" and len(rest) == 1:
        return kind, rest
    if kind == "field" and len(rest) == 2:
        return kind, rest
    raise DimensionError("invalid_dimension")


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise DimensionError("invalid_dimension") from exc


async def code_dimension(
    db: AsyncSession, project: Project, ref_id: str, us: list[Unit]
) -> Dimension:
    parent_id = _uuid(ref_id)
    codes = await synthesis.codes_of(db, project.id)
    parent = next((c for c in codes if c.id == parent_id), None)
    if parent is None:
        raise DimensionError("dimension_not_found")
    children = [c for c in codes if c.parent_id == parent_id]
    if not children:
        raise DimensionError("code_has_no_children")
    under = {c.id: synthesis.descendants(codes, c.id) for c in children}
    rows = await db.execute(
        select(ExcerptCode.code_id, Excerpt.record_id)
        .join(Excerpt, Excerpt.id == ExcerptCode.excerpt_id)
        .where(Excerpt.project_id == project.id)
    )
    coded: dict[uuid.UUID, set[uuid.UUID]] = {}
    for code_id, record_id in rows.all():
        coded.setdefault(record_id, set()).add(code_id)
    members: dict[uuid.UUID, set[str]] = {}
    for u in us:
        have: set[uuid.UUID] = set()
        for rid in u.report_ids:
            have |= coded.get(rid, set())
        members[u.record.id] = {str(c.id) for c in children if under[c.id] & have}
    return Dimension(
        source=f"codes:{ref_id}",
        title=parent.name,
        categories=[Category(str(c.id), c.name) for c in children],
        members=members,
    )


async def field_dimension(
    db: AsyncSession, project: Project, form_id: str, field_id: str, us: list[Unit]
) -> Dimension:
    form = await db.get(ExtractionForm, _uuid(form_id))
    if form is None or form.project_id != project.id:
        raise DimensionError("dimension_not_found")
    field = next((f for f in form.fields if f.get("id") == field_id), None)
    if field is None or field.get("type") not in CHOICE_TYPES:
        raise DimensionError("dimension_not_found")
    options = [str(o) for o in field.get("options") or []]
    exts = await extraction.load_extractions(db, form, [u.record.id for u in us])
    members: dict[uuid.UUID, set[str]] = {}
    for u in us:
        values, _ = extraction.final_values(form, exts.get(u.record.id, []))
        v = values.get(field_id)
        picked = v if isinstance(v, list) else [v] if v not in (None, "") else []
        members[u.record.id] = {str(x) for x in picked if str(x) in options}
    return Dimension(
        source=f"field:{form_id}:{field_id}",
        title=f"{form.name} › {field.get('label') or field_id}",
        categories=[Category(o, o) for o in options],
        members=members,
    )


async def dimension(db: AsyncSession, project: Project, ref: str, us: list[Unit]) -> Dimension:
    kind, parts = parse_ref(ref)
    if kind == "codes":
        return await code_dimension(db, project, parts[0], us)
    return await field_dimension(db, project, parts[0], parts[1], us)


async def build_map(db: AsyncSession, project: Project, rows_ref: str, cols_ref: str) -> dict:
    us = await extraction.units(db, project)
    rows = await dimension(db, project, rows_ref, us)
    cols = await dimension(db, project, cols_ref, us)
    cells: dict[tuple[str, str], list[str]] = {}
    row_n = {c.key: 0 for c in rows.categories} | {NONE_KEY: 0}
    col_n = {c.key: 0 for c in cols.categories} | {NONE_KEY: 0}
    for u in us:
        rid = u.record.id
        rs = rows.members.get(rid) or {NONE_KEY}
        cs = cols.members.get(rid) or {NONE_KEY}
        for r in rs:
            row_n[r] += 1
        for c in cs:
            col_n[c] += 1
        for r in rs:
            for c in cs:
                cells.setdefault((r, c), []).append(str(rid))

    def axis(dim: Dimension, counts: dict[str, int]) -> list[dict]:
        out = [{"key": c.key, "label": c.label, "n": counts[c.key]} for c in dim.categories]
        if counts[NONE_KEY]:
            out.append({"key": NONE_KEY, "label": "", "n": counts[NONE_KEY]})
        return out

    return {
        "rows": {"source": rows.source, "title": rows.title, "categories": axis(rows, row_n)},
        "cols": {"source": cols.source, "title": cols.title, "categories": axis(cols, col_n)},
        "cells": [{"row": r, "col": c, "studies": ids} for (r, c), ids in cells.items()],
        "studies": {
            str(u.record.id): {"label": u.label, "title": u.record.title, "year": u.record.year}
            for u in us
        },
        "total_studies": len(us),
    }


async def available(db: AsyncSession, project: Project) -> dict:
    codes = await synthesis.codes_of(db, project.id)
    parents = {c.parent_id for c in codes if c.parent_id}
    forms = (
        (
            await db.execute(
                select(ExtractionForm).where(
                    ExtractionForm.project_id == project.id,
                    ExtractionForm.kind == "extraction",
                    ExtractionForm.archived.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    return {
        "codes": [
            {
                "ref": f"codes:{c.id}",
                "label": synthesis.path(codes, c.id),
                "categories": sum(1 for x in codes if x.parent_id == c.id),
            }
            for c in codes
            if c.id in parents
        ],
        "fields": [
            {
                "ref": f"field:{f.id}:{fld['id']}",
                "label": f"{f.name} › {fld.get('label') or fld['id']}",
                "categories": len(fld.get("options") or []),
            }
            for f in forms
            for fld in f.fields
            if fld.get("type") in CHOICE_TYPES
        ],
    }
