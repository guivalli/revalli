"""Cálculo das meta-análises e da certeza da evidência (GRADE)."""

import math

from revalli.modules.meta import stats
from revalli.modules.meta.models import GradeRow, MetaAnalysis

CERTAINTY = {4: "high", 3: "moderate", 2: "low", 1: "very_low"}
DOWN = ("risk_of_bias", "inconsistency", "indirectness", "imprecision", "publication_bias")
UP = ("large_effect", "dose_response", "confounding")
# Abaixo disso, o tamanho de amostra ótimo dificilmente foi atingido (regra prática do GRADE)
OIS = 400


def _participants(measure: str, row: dict) -> int | None:
    if measure in ("HR", "GENERIC"):
        return None
    n1, n2 = row.get("n1"), row.get("n2")
    return int(n1 + n2) if n1 is not None and n2 is not None else None


def _display(log_scale: bool, v: float) -> float:
    return math.exp(v) if log_scale else v


def _pooled_out(p: stats.Pooled, model: str, log_scale: bool, participants: int | None) -> dict:
    est = p.random if model == "random" else p.fixed
    return {
        "k": p.k,
        "estimate": _display(log_scale, est["estimate"]),
        "lower": _display(log_scale, est["lower"]),
        "upper": _display(log_scale, est["upper"]),
        "p": est["p"],
        "z": est["z"],
        "q": p.q,
        "df": p.df,
        "p_q": None if math.isnan(p.p_q) else p.p_q,
        "i2": p.i2,
        "tau2": p.tau2 if model == "random" else 0.0,
        "prediction": (
            tuple(_display(log_scale, v) for v in p.prediction)
            if p.prediction and model == "random"
            else None
        ),
        "participants": participants,
    }


def result(a: MetaAnalysis) -> dict:
    log_scale = a.measure in stats.RATIO
    rows = a.rows or []
    effects = [stats.effect(a.measure, r) for r in rows]
    used = [(r, e) for r, e in zip(rows, effects, strict=True) if e.skipped is None]
    pooled = stats.pool([e.yi for _, e in used], [e.vi for _, e in used])

    def total(items) -> int | None:
        ns = [_participants(a.measure, r) for r, _ in items]
        return sum(n for n in ns if n) if any(ns) else None

    weights = {}
    if pooled:
        w = pooled.weights_random if a.model == "random" else pooled.weights_fixed
        weights = {r["id"]: w[i] for i, (r, _) in enumerate(used)}
    studies = []
    for r, e in zip(rows, effects, strict=True):
        se = math.sqrt(e.vi) if e.vi is not None else None
        studies.append(
            {
                "id": r["id"],
                "label": r["label"],
                "subgroup": r.get("subgroup") or "",
                "yi": e.yi,
                "se": se,
                "estimate": _display(log_scale, e.yi) if e.yi is not None else None,
                "lower": _display(log_scale, e.yi - stats.Z95 * se) if se else None,
                "upper": _display(log_scale, e.yi + stats.Z95 * se) if se else None,
                "weight": weights.get(r["id"]),
                "skipped": e.skipped,
                "corrected": e.corrected,
                "participants": _participants(a.measure, r),
            }
        )

    groups: dict[str, list] = {}
    for r, e in used:
        if r.get("subgroup"):
            groups.setdefault(r["subgroup"], []).append((r, e))
    sub_pooled = {
        name: stats.pool([e.yi for _, e in items], [e.vi for _, e in items])
        for name, items in sorted(groups.items())
    }
    # Só faz sentido testar subgrupos quando todos os estudos têm um
    all_grouped = len(groups) >= 2 and sum(len(v) for v in groups.values()) == len(used)
    return {
        "measure": a.measure,
        "model": a.model,
        "log_scale": log_scale,
        "studies": studies,
        "pooled": _pooled_out(pooled, a.model, log_scale, total(used)) if pooled else None,
        "subgroups": [
            {
                "name": name,
                "pooled": _pooled_out(p, a.model, log_scale, total(groups[name])) if p else None,
            }
            for name, p in sub_pooled.items()
        ]
        if len(groups) >= 2
        else [],
        "subgroup_test": stats.subgroup_test(sub_pooled, a.model) if all_grouped else None,
        "egger": stats.egger([e.yi for _, e in used], [e.vi for _, e in used])
        if len(used) >= 3
        else None,
    }


def certainty(row: GradeRow) -> str:
    d = row.domains or {}
    score = 4 if row.design == "rct" else 2
    score += sum(min(0, int((d.get(k) or {}).get("rating", 0))) for k in DOWN)
    score += sum(max(0, int((d.get(k) or {}).get("rating", 0))) for k in UP)
    return CERTAINTY[max(1, min(4, score))]


def grade_auto(analysis: MetaAnalysis | None) -> tuple[dict | None, list[str]]:
    """Números da meta-análise ligada e sugestões para os domínios do GRADE."""
    if analysis is None:
        return None, []
    res = result(analysis)
    p = res["pooled"]
    if not p:
        return None, []
    null = 1.0 if res["log_scale"] else 0.0
    crosses = p["lower"] <= null <= p["upper"]
    egg = res["egger"]
    auto = {
        "measure": analysis.measure,
        "k": p["k"],
        "participants": p["participants"],
        "estimate": p["estimate"],
        "lower": p["lower"],
        "upper": p["upper"],
        "i2": p["i2"],
        "crosses_null": crosses,
        "egger_p": egg["p"] if egg and p["k"] >= 10 else None,
    }
    tips = []
    if p["k"] > 1 and p["i2"] >= 75:
        tips.append("inconsistency_high")
    elif p["k"] > 1 and p["i2"] >= 50:
        tips.append("inconsistency_moderate")
    if crosses:
        tips.append("imprecision_crosses_null")
    if p["participants"] is not None and p["participants"] < OIS:
        tips.append("imprecision_small_sample")
    if p["k"] < 10:
        tips.append("publication_bias_few_studies")
    elif egg and egg["p"] < 0.10:
        tips.append("publication_bias_egger")
    return auto, tips


def grade_out(row: GradeRow, analysis: MetaAnalysis | None) -> dict:
    auto, tips = grade_auto(analysis)
    return {
        "id": row.id,
        "outcome": row.outcome,
        "analysis_id": row.analysis_id,
        "design": row.design,
        "studies": row.studies,
        "participants": row.participants,
        "effect": row.effect,
        "domains": row.domains or {},
        "importance": row.importance,
        "comments": row.comments,
        "certainty": certainty(row),
        "auto": auto,
        "suggestions": tips,
    }
