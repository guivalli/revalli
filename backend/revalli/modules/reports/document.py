"""Relatório da revisão (métodos, resultados e apêndices) montado a partir dos dados do projeto.

O conteúdo vira uma lista de blocos simples, que `render.py` transforma em DOCX ou PDF.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import AIUsage, ExtractionForm, Project, Search
from revalli.modules.ai.service import calibration, project_ai
from revalli.modules.extraction.service import rob_summary, units
from revalli.modules.meta.models import GradeRow, MetaAnalysis
from revalli.modules.meta.service import DOWN, UP, certainty, result
from revalli.modules.reports.service import prisma_counts
from revalli.modules.reports.texts import TEXTS
from revalli.modules.screening.models import Phase
from revalli.modules.screening.service import agreement_pairs, compute_states, get_settings, kappa
from revalli.modules.synthesis.checklists import CHECKLISTS
from revalli.modules.synthesis.models import ChecklistEntry, Excerpt
from revalli.modules.synthesis.service import codes_of, descendants, matrix_cells, path

SECTIONS = ("methods", "results", "appendix_search", "appendix_ai", "appendix_checklist")
SYMBOLS = {"high": "⊕⊕⊕⊕", "moderate": "⊕⊕⊕◯", "low": "⊕⊕◯◯", "very_low": "⊕◯◯◯"}


@dataclass
class Heading:
    text: str
    level: int = 1


@dataclass
class Para:
    text: str
    style: str = "normal"  # normal | note | mono | label


@dataclass
class Table:
    head: list[str]
    rows: list[list[str]]
    caption: str = ""


@dataclass
class Figure:
    png: bytes
    caption: str = ""


@dataclass
class PageBreak:
    pass


Block = Heading | Para | Table | Figure | PageBreak


@dataclass
class Report:
    title: str
    subtitle: str
    blocks: list[Block] = field(default_factory=list)


class Writer:
    def __init__(self, lang: str):
        self.lang = lang if lang in TEXTS else "pt-BR"
        self.texts = TEXTS[self.lang]
        self.blocks: list[Block] = []
        self.tables = 0
        self.figures = 0

    def t(self, key: str, **kw) -> str:
        return self.texts[key].format(**kw) if kw else self.texts[key]

    def num(self, v: float | None, digits: int = 2) -> str:
        if v is None:
            return "–"
        s = f"{v:,.{digits}f}"
        if self.lang == "pt-BR":
            s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
        return s

    def p_value(self, p: float | None) -> str:
        if p is None:
            return "–"
        return f"< {self.num(0.001, 3)}" if p < 0.001 else f"= {self.num(p, 3)}"

    def h(self, text: str, level: int = 1) -> None:
        self.blocks.append(Heading(text, level))

    def p(self, text: str, style: str = "normal") -> None:
        if text.strip():
            self.blocks.append(Para(text, style))

    def table(self, head: list[str], rows: list[list], caption: str) -> None:
        self.tables += 1
        cap = f"{self.t('table')} {self.tables}. {caption}"
        cells = [["" if c is None else str(c) for c in r] for r in rows]
        self.blocks.append(Table(head, cells, cap))

    def figure(self, png: bytes | None, caption: str) -> None:
        if not png:
            return
        self.figures += 1
        self.blocks.append(Figure(png, f"{self.t('figure')} {self.figures}. {caption}"))


def _join(items: list[str], lang: str) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    last = " e " if lang == "pt-BR" else " and "
    return ", ".join(items[:-1]) + last + items[-1]


async def _searches(db: AsyncSession, project: Project) -> list[Search]:
    rows = await db.execute(
        select(Search).where(Search.project_id == project.id).order_by(Search.created_at)
    )
    return list(rows.scalars())


async def _usage(db: AsyncSession, project: Project) -> list[tuple]:
    rows = await db.execute(
        select(
            AIUsage.task,
            AIUsage.model,
            func.count(),
            func.coalesce(func.sum(AIUsage.input_tokens), 0),
            func.coalesce(func.sum(AIUsage.output_tokens), 0),
            func.coalesce(func.sum(AIUsage.cost_usd), 0.0),
        )
        .where(AIUsage.project_id == project.id)
        .group_by(AIUsage.task, AIUsage.model)
        .order_by(AIUsage.task, AIUsage.model)
    )
    return list(rows.all())


async def _forms(db: AsyncSession, project: Project) -> list[ExtractionForm]:
    rows = await db.execute(
        select(ExtractionForm)
        .where(ExtractionForm.project_id == project.id, ExtractionForm.archived.is_(False))
        .order_by(ExtractionForm.created_at)
    )
    return list(rows.scalars())


async def _methods(w: Writer, db: AsyncSession, project: Project, ctx: dict) -> None:
    lang = w.lang
    s = get_settings(project)
    w.h(w.t("methods"))

    w.h(w.t("eligibility"), 2)
    if s.inclusion_criteria.strip() or s.exclusion_criteria.strip():
        for key, text in (("inclusion", s.inclusion_criteria), ("exclusion", s.exclusion_criteria)):
            if text.strip():
                w.p(w.t(key), "label")
                for line in text.strip().splitlines():
                    w.p(line.strip())
    else:
        w.p(w.t("no_criteria"), "note")

    w.h(w.t("sources"), 2)
    searches = ctx["searches"]
    db_searches = [x for x in searches if x.method == "database"]
    if db_searches:
        listed = []
        for x in db_searches:
            when = f" ({x.searched_on.strftime('%d/%m/%Y')})" if x.searched_on else ""
            listed.append(x.source + when)
        w.p(w.t("sources_text", n=len({x.source for x in db_searches}), list=_join(listed, lang)))
        api = sorted({x.source for x in db_searches if x.file_format == "api"})
        if api:
            w.p(w.t("sources_api", list=_join(api, lang)))
    else:
        w.p(w.t("sources_none"), "note")
    methods = sorted({x.method for x in searches if x.method != "database"})
    if methods:
        w.p(w.t("citation_text", list=_join([w.t(f"method_{m}") for m in methods], lang)))
    if searches:
        w.p(w.t("strategies_appendix"))

    w.h(w.t("selection"), 2)
    w.p(
        w.t(
            "selection_text",
            ta=s.reviewers_title_abstract,
            ft=s.reviewers_full_text,
            blind=w.t("blind") if s.blind else w.t("not_blind"),
        )
    )
    for phase, states in ctx["states"].items():
        pairs = agreement_pairs(states)
        ks = [(k, len(d)) for d in pairs.values() if (k := kappa(d)[0]) is not None]
        if ks:
            n = sum(m for _, m in ks)
            mean = sum(k * m for k, m in ks) / n
            w.p(
                w.t(
                    "agreement",
                    phase=w.t(f"phase_{phase}"),
                    kappa=w.num(mean),
                    pairs=len(ks),
                    n=n,
                )
            )

    usage = ctx["usage"]
    ai = project_ai(project)
    by_task: dict[str, list[str]] = {}
    for task, model, *_ in usage:
        by_task.setdefault(task, []).append(model)
    if by_task:
        w.h(w.t("ai_use"), 2)
        if "screening" in by_task:
            models = _join(by_task["screening"], lang)
            key = "ai_second" if ai.mode == "second_reviewer" else "ai_suggest"
            w.p(w.t(key, models=models))
        if "extraction" in by_task:
            w.p(w.t("ai_extraction", models=_join(by_task["extraction"], lang)))
        if "query_translation" in by_task:
            w.p(w.t("ai_translation"))
        if ai.local_only:
            w.p(w.t("ai_local"))
        w.p(w.t("ai_appendix_ref"))

    forms = ctx["forms"]
    ext = [f for f in forms if f.kind == "extraction"]
    rob = [f for f in forms if f.kind == "rob"]
    if ext:
        w.h(w.t("extraction"), 2)
        for f in ext:
            w.p(w.t("extraction_form", name=f.name, n=f.extractors))
    if rob:
        w.h(w.t("rob"), 2)
        for f in rob:
            w.p(w.t("rob_form", name=f.name, n=f.extractors))

    analyses = ctx["analyses"]
    grade = ctx["grade"]
    codes = ctx["codes"]
    if analyses or grade or codes:
        w.h(w.t("synthesis"), 2)
        if analyses:
            models = sorted({a.model for a in analyses})
            measures = sorted({a.measure for a in analyses})
            w.p(
                w.t(
                    "meta_methods",
                    models=_join([w.t(f"model_{m}") for m in models], lang),
                    measures=", ".join(measures),
                )
            )
        if grade:
            w.p(w.t("grade_methods"))
        if codes:
            w.p(w.t("coding_methods", excerpts=ctx["excerpts"], codes=len(codes)))


async def _results(
    w: Writer, db: AsyncSession, project: Project, ctx: dict, figures: dict[str, bytes]
) -> None:
    w.h(w.t("results"))
    pr = ctx["prisma"]
    w.h(w.t("study_selection"), 2)
    w.p(
        w.t(
            "selection_results",
            total=pr["identification"]["total"],
            dups=pr["identification"]["duplicates_removed"],
            screened=pr["screening"]["screened"],
            ta_excluded=pr["screening"]["excluded"],
            assessed=pr["eligibility"]["assessed"],
            ft_excluded=pr["eligibility"]["excluded"],
            included=pr["included"],
            reports=pr["included_reports"],
        )
    )
    pending = pr["screening"]["pending"] + pr["eligibility"]["pending"]
    if pending:
        w.p(w.t("pending_note", n=pending), "note")
    w.figure(figures.get("prisma"), w.t("fig_prisma"))
    reasons = pr["eligibility"]["reasons"]
    if reasons:
        w.table(
            [w.t("reason"), w.t("count")],
            [[r["reason"] or w.t("no_reason"), r["count"]] for r in reasons],
            w.t("reasons_table"),
        )

    us = ctx["units"]
    w.h(w.t("included_studies"), 2)
    if us:
        w.table(
            [w.t("study"), w.t("title"), w.t("year"), w.t("journal"), w.t("reports")],
            [
                [u.label, u.record.title, u.record.year or "", u.record.journal, len(u.report_ids)]
                for u in us
            ],
            w.t("included_table"),
        )
    else:
        w.p(w.t("no_included"), "note")

    rob_forms = [f for f in ctx["forms"] if f.kind == "rob"]
    if rob_forms and us:
        w.h(w.t("rob_results"), 2)
        for f in rob_forms:
            summary = await rob_summary(db, project, f)
            if not summary["rows"]:
                w.p(w.t("rob_none", name=f.name), "note")
                continue
            doms = summary["domains"]

            def judge(v: str | None) -> str:
                return w.t(f"rob_{v}") if v and f"rob_{v}" in w.texts else (v or "–")

            w.table(
                [w.t("study")] + [d["label"] for d in doms],
                [
                    [r["label"]] + [judge(r["judgements"].get(d["id"])) for d in doms]
                    for r in summary["rows"]
                ],
                w.t("rob_table", name=f.name),
            )

    analyses = ctx["analyses"]
    if analyses:
        w.h(w.t("meta_results"), 2)
        for a in analyses:
            w.h(a.name + (f" ({a.outcome})" if a.outcome and a.outcome != a.name else ""), 3)
            res = result(a)
            pooled = res["pooled"]
            w.figure(figures.get(f"meta:{a.id}"), w.t("fig_forest", name=a.name))
            if not pooled:
                w.p(w.t("meta_no_data"), "note")
                continue
            w.p(
                w.t(
                    "meta_summary",
                    k=pooled["k"],
                    measure=a.measure,
                    est=w.num(pooled["estimate"]),
                    lower=w.num(pooled["lower"]),
                    upper=w.num(pooled["upper"]),
                    p=w.p_value(pooled["p"]),
                    i2=w.num(pooled["i2"], 0),
                    tau2=w.num(pooled["tau2"], 3),
                )
            )
            if pooled.get("prediction"):
                lo, hi = pooled["prediction"]
                w.p(w.t("meta_prediction", lower=w.num(lo), upper=w.num(hi)))
            if res.get("subgroup_test"):
                st = res["subgroup_test"]
                w.p(w.t("meta_subgroups", q=w.num(st["q"]), df=st["df"], p=w.p_value(st["p"])))
            if res.get("egger") and pooled["k"] >= 10:
                eg = res["egger"]
                w.p(w.t("meta_egger", intercept=w.num(eg["intercept"]), p=w.p_value(eg["p"])))

    grade = ctx["grade"]
    if grade:
        w.h(w.t("grade_results"), 2)
        rows = []
        for g in grade:
            c = certainty(g)
            doms = g.domains or {}
            reasons = []
            for k in DOWN + UP:
                d = doms.get(k) or {}
                if d.get("rating"):
                    sign = "+" if d["rating"] > 0 else ""
                    why = f": {d['reason']}" if d.get("reason") else ""
                    reasons.append(f"{w.t(f'domain_{k}')} ({sign}{d['rating']}){why}")
            rows.append(
                [
                    g.outcome,
                    f"{g.studies if g.studies is not None else '–'} "
                    f"({w.num(g.participants, 0) if g.participants is not None else '–'})",
                    g.effect or "–",
                    f"{SYMBOLS[c]} {w.t(f'certainty_{c}')}",
                    "; ".join(reasons),
                    w.t(f"importance_{g.importance}"),
                ]
            )
        w.table(
            [
                w.t("outcome"),
                w.t("studies_participants"),
                w.t("effect"),
                w.t("certainty"),
                w.t("reasons"),
                w.t("importance"),
            ],
            rows,
            w.t("grade_table"),
        )

    codes = ctx["codes"]
    if codes:
        w.h(w.t("coding_results"), 2)
        cells = ctx["cells"]
        rows = []
        for c in codes:
            ids = descendants(codes, c.id)
            per_study: dict[str, int] = {}
            for cid in ids:
                for rid, n in cells.get(str(cid), {}).items():
                    per_study[rid] = per_study.get(rid, 0) + n
            rows.append((path(codes, c.id), len(per_study), sum(per_study.values())))
        rows.sort(key=lambda r: r[0].lower())
        w.table(
            [w.t("code"), w.t("studies"), w.t("excerpts")],
            [list(r) for r in rows],
            w.t("codes_table"),
        )


def _appendix_search(w: Writer, ctx: dict) -> None:
    w.blocks.append(PageBreak())
    w.h(w.t("appendix_a"))
    for x in ctx["searches"]:
        method = w.t(f"method_{x.method}")
        w.h(x.source, 3)
        info = [method]
        if x.searched_on:
            info.append(x.searched_on.strftime("%d/%m/%Y"))
        if x.file_format == "api":
            info.append(w.t("via_api"))
        elif x.file_name:
            info.append(w.t("file", name=x.file_name))
        reported = x.reported_count if x.reported_count is not None else "–"
        info.append(f"{w.t('records_reported')}: {reported} / {x.imported_count}")
        w.p(" · ".join(info), "note")
        if x.query.strip():
            w.p(x.query.strip(), "mono")
        else:
            w.p(w.t("query_missing"), "note")
        if x.notes.strip():
            w.p(f"{w.t('notes')}: {x.notes.strip()}")


async def _appendix_ai(w: Writer, db: AsyncSession, project: Project, ctx: dict) -> None:
    w.blocks.append(PageBreak())
    w.h(w.t("appendix_b"))
    ai = project_ai(project)
    usage = ctx["usage"]
    if not usage and not ai.enabled:
        w.p(w.t("ai_disabled"))
        return
    w.p(
        w.t(
            "ai_settings",
            enabled=w.t("enabled") if ai.enabled else w.t("disabled"),
            mode=w.t(f"mode_{ai.mode}"),
            local=w.t("local_only") if ai.local_only else w.t("any_provider"),
            budget=f"US$ {w.num(ai.budget_usd)}" if ai.budget_usd is not None else w.t("no_budget"),
        )
    )
    if usage:

        def task(name: str) -> str:
            return w.t(f"task_{name}") if f"task_{name}" in w.texts else name

        w.table(
            [
                w.t("task"),
                w.t("model"),
                w.t("calls"),
                w.t("tokens_in"),
                w.t("tokens_out"),
                w.t("cost"),
            ],
            [[task(t), m, n, w.num(i, 0), w.num(o, 0), w.num(c, 4)] for t, m, n, i, o, c in usage],
            w.t("usage_table"),
        )
    rows = []
    for phase in (Phase.title_abstract, Phase.full_text):
        cal = await calibration(db, project, phase)
        if cal["n"]:
            rows.append(
                [
                    w.t(f"phase_{phase.value}"),
                    cal["n"],
                    w.num(cal["sensitivity"]),
                    w.num(cal["specificity"]),
                    w.num(cal["kappa"]),
                ]
            )
    if rows:
        w.table(
            [w.t("phase"), w.t("compared"), w.t("sensitivity"), w.t("specificity"), w.t("kappa")],
            rows,
            w.t("calibration_table"),
        )


async def _appendix_checklist(
    w: Writer, db: AsyncSession, project: Project, item_texts: dict[str, str]
) -> None:
    kind = "prisma_scr" if project.review_type == "scoping" else "prisma2020"
    saved = {
        e.item: e
        for e in (
            await db.execute(
                select(ChecklistEntry).where(
                    ChecklistEntry.project_id == project.id, ChecklistEntry.checklist == kind
                )
            )
        ).scalars()
    }
    w.blocks.append(PageBreak())
    w.h(w.t("appendix_c", name=w.t(f"checklist_{kind}")))
    rows = []
    for item in CHECKLISTS[kind]:
        e = saved.get(item)
        status = e.status if e else "pending"
        location = e.location if e else ""
        if e and e.note:
            location = f"{location} ({e.note})" if location else e.note
        rows.append([item, item_texts.get(item, ""), w.t(f"status_{status}"), location])
    head = [w.t("item"), w.t("description"), w.t("status"), w.t("location")]
    if not item_texts:
        head.pop(1)
        rows = [[r[0], r[2], r[3]] for r in rows]
    w.table(head, rows, w.t(f"checklist_{kind}"))


async def build_report(
    db: AsyncSession,
    project: Project,
    *,
    lang: str = "pt-BR",
    sections: list[str] | None = None,
    figures: dict[str, bytes] | None = None,
    checklist_items: dict[str, str] | None = None,
) -> Report:
    w = Writer(lang)
    wanted = set(sections or SECTIONS)
    figures = figures or {}
    pid = project.id
    analyses = list(
        (
            await db.execute(
                select(MetaAnalysis)
                .where(MetaAnalysis.project_id == pid)
                .order_by(MetaAnalysis.position, MetaAnalysis.created_at)
            )
        ).scalars()
    )
    grade = list(
        (
            await db.execute(
                select(GradeRow)
                .where(GradeRow.project_id == pid)
                .order_by(GradeRow.position, GradeRow.created_at)
            )
        ).scalars()
    )
    codes = await codes_of(db, pid)
    cells = await matrix_cells(db, pid) if codes else {}
    ctx = {
        "searches": await _searches(db, project),
        "usage": await _usage(db, project),
        "forms": await _forms(db, project),
        "states": {
            phase.value: await compute_states(db, project, phase)
            for phase in (Phase.title_abstract, Phase.full_text)
        },
        "analyses": analyses,
        "grade": grade,
        "codes": codes,
        "cells": cells,
        "excerpts": await _excerpt_total(db, pid) if codes else 0,
        "prisma": await prisma_counts(db, project),
        "units": await units(db, project),
    }
    if "methods" in wanted:
        await _methods(w, db, project, ctx)
    if "results" in wanted:
        await _results(w, db, project, ctx, figures)
    if "appendix_search" in wanted and ctx["searches"]:
        _appendix_search(w, ctx)
    if "appendix_ai" in wanted:
        await _appendix_ai(w, db, project, ctx)
    if "appendix_checklist" in wanted:
        await _appendix_checklist(w, db, project, checklist_items or {})

    subtitle = w.t(f"review_type_{project.review_type}")
    if project.description.strip():
        subtitle = f"{subtitle}. {project.description.strip()}"
    w.blocks.insert(0, Para(w.t("draft_note", date=_today(w.lang)), "note"))
    return Report(title=project.title, subtitle=subtitle, blocks=w.blocks)


async def _excerpt_total(db: AsyncSession, project_id: uuid.UUID) -> int:
    return (
        await db.execute(select(func.count()).where(Excerpt.project_id == project_id))
    ).scalar_one()


def _today(lang: str) -> str:
    d = date.today()
    return d.strftime("%d/%m/%Y") if lang == "pt-BR" else d.isoformat()
