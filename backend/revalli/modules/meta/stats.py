"""Meta-análise por variância inversa (efeito fixo e aleatório de DerSimonian-Laird).

Implementação própria e pequena, sem dependências além do numpy, conferida nos testes contra
resultados publicados. Medidas de razão (RR, OR) são combinadas na escala logarítmica.
"""

import math
from dataclasses import dataclass, field

import numpy as np

RATIO = {"RR", "OR", "HR"}
Z95 = 1.959963984540054


# --- Distribuições ------------------------------------------------------------------


def norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def _gammainc_upper(a: float, x: float) -> float:
    """Função gama incompleta superior regularizada Q(a, x)."""
    if x <= 0:
        return 1.0
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return 1.0 - total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x: float, df: int) -> float:
    return _gammainc_upper(df / 2, x / 2) if df > 0 else float("nan")


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (1e-300 if abs(d) < 1e-300 else d)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (1e-300 if abs(d) < 1e-300 else d)
        c = 1 + aa / c
        c = 1e-300 if abs(c) < 1e-300 else c
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (1e-300 if abs(d) < 1e-300 else d)
        c = 1 + aa / c
        c = 1e-300 if abs(c) < 1e-300 else c
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    )
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_sf(t: float, df: float) -> float:
    """P(T > t) para a distribuição t de Student."""
    p = 0.5 * betainc(df / 2, 0.5, df / (df + t * t))
    return p if t > 0 else 1 - p


def t_ppf(q: float, df: float) -> float:
    """Quantil da distribuição t (por bissecção)."""
    lo, hi = -1e3, 1e3
    for _ in range(200):
        mid = (lo + hi) / 2
        if 1 - t_sf(mid, df) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# --- Tamanho de efeito de cada estudo -----------------------------------------------------


@dataclass
class StudyEffect:
    yi: float | None
    vi: float | None
    # Motivo para o estudo não entrar no cálculo (dados faltando, dois braços sem eventos)
    skipped: str | None = None
    corrected: bool = False


def _num(row: dict, key: str) -> float | None:
    v = row.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def effect(measure: str, row: dict) -> StudyEffect:
    if measure in ("MD", "SMD"):
        n1, m1, s1 = _num(row, "n1"), _num(row, "mean1"), _num(row, "sd1")
        n2, m2, s2 = _num(row, "n2"), _num(row, "mean2"), _num(row, "sd2")
        if None in (n1, m1, s1, n2, m2, s2) or n1 < 2 or n2 < 2 or s1 <= 0 or s2 <= 0:
            return StudyEffect(None, None, "missing")
        if measure == "MD":
            return StudyEffect(m1 - m2, s1**2 / n1 + s2**2 / n2)
        sp = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
        j = 1 - 3 / (4 * (n1 + n2) - 9)
        g = j * (m1 - m2) / sp
        return StudyEffect(g, (n1 + n2) / (n1 * n2) + g**2 / (2 * (n1 + n2)))
    if measure in ("RR", "OR", "RD"):
        e1, n1, e2, n2 = (_num(row, k) for k in ("e1", "n1", "e2", "n2"))
        if None in (e1, n1, e2, n2) or n1 <= 0 or n2 <= 0 or e1 > n1 or e2 > n2 or e1 < 0 or e2 < 0:
            return StudyEffect(None, None, "missing")
        if measure == "RD":
            p1, p2 = e1 / n1, e2 / n2
            return StudyEffect(p1 - p2, max(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2, 1e-12))
        if (e1 == 0 and e2 == 0) or (e1 == n1 and e2 == n2):
            return StudyEffect(None, None, "double_zero")
        corrected = 0 in (e1, e2, n1 - e1, n2 - e2)
        if corrected:
            e1, e2, n1, n2 = e1 + 0.5, e2 + 0.5, n1 + 1, n2 + 1
        if measure == "RR":
            return StudyEffect(
                math.log((e1 / n1) / (e2 / n2)), 1 / e1 - 1 / n1 + 1 / e2 - 1 / n2, None, corrected
            )
        f1, f2 = n1 - e1, n2 - e2
        return StudyEffect(
            math.log((e1 * f2) / (f1 * e2)), 1 / e1 + 1 / f1 + 1 / e2 + 1 / f2, None, corrected
        )
    if measure == "HR":
        hr, lo, hi = _num(row, "hr"), _num(row, "hr_lower"), _num(row, "hr_upper")
        if None in (hr, lo, hi) or min(hr, lo, hi) <= 0 or not lo < hr < hi:
            return StudyEffect(None, None, "missing")
        se = (math.log(hi) - math.log(lo)) / (2 * Z95)
        return StudyEffect(math.log(hr), se**2)
    # Genérico: estimativa e erro padrão já calculados
    yi, se = _num(row, "yi"), _num(row, "sei")
    if yi is None or se is None or se <= 0:
        return StudyEffect(None, None, "missing")
    return StudyEffect(yi, se**2)


# --- Combinação -------------------------------------------------------------------------


@dataclass
class Pooled:
    k: int
    fixed: dict
    random: dict
    q: float
    df: int
    p_q: float
    i2: float
    tau2: float
    prediction: tuple[float, float] | None
    weights_fixed: list[float] = field(default_factory=list)
    weights_random: list[float] = field(default_factory=list)


def _estimate(y: np.ndarray, w: np.ndarray) -> dict:
    est = float(np.sum(w * y) / np.sum(w))
    se = float(math.sqrt(1 / np.sum(w)))
    z = est / se
    return {
        "estimate": est,
        "se": se,
        "lower": est - Z95 * se,
        "upper": est + Z95 * se,
        "z": z,
        "p": 2 * norm_sf(abs(z)),
    }


def pool(yi: list[float], vi: list[float]) -> Pooled | None:
    k = len(yi)
    if k == 0:
        return None
    y, v = np.asarray(yi, float), np.asarray(vi, float)
    w = 1 / v
    fixed = _estimate(y, w)
    q = float(np.sum(w * (y - fixed["estimate"]) ** 2))
    df = k - 1
    c = float(np.sum(w) - np.sum(w**2) / np.sum(w))
    tau2 = max(0.0, (q - df) / c) if df > 0 and c > 0 else 0.0
    wr = 1 / (v + tau2)
    random = _estimate(y, wr)
    i2 = max(0.0, (q - df) / q) * 100 if q > 0 and df > 0 else 0.0
    prediction = None
    if k >= 3:
        t = t_ppf(0.975, k - 2)
        half = t * math.sqrt(tau2 + random["se"] ** 2)
        prediction = (random["estimate"] - half, random["estimate"] + half)
    return Pooled(
        k=k,
        fixed=fixed,
        random=random,
        q=q,
        df=df,
        p_q=chi2_sf(q, df) if df > 0 else float("nan"),
        i2=i2,
        tau2=tau2,
        prediction=prediction,
        weights_fixed=list(w / np.sum(w) * 100),
        weights_random=list(wr / np.sum(wr) * 100),
    )


def egger(yi: list[float], vi: list[float]) -> dict | None:
    """Teste de Egger para assimetria do funil (regressão de y/se em 1/se)."""
    k = len(yi)
    if k < 3:
        return None
    y, se = np.asarray(yi, float), np.sqrt(np.asarray(vi, float))
    x = np.column_stack([np.ones(k), 1 / se])
    target = y / se
    coef, *_ = np.linalg.lstsq(x, target, rcond=None)
    resid = target - x @ coef
    s2 = float(resid @ resid) / (k - 2)
    cov = s2 * np.linalg.inv(x.T @ x)
    se_int = math.sqrt(cov[0, 0])
    t = float(coef[0]) / se_int if se_int > 0 else 0.0
    return {"intercept": float(coef[0]), "se": se_int, "t": t, "p": 2 * t_sf(abs(t), k - 2)}


def subgroup_test(groups: dict[str, Pooled], model: str) -> dict | None:
    """Teste de diferença entre subgrupos (Q entre grupos)."""
    est = [(g.random if model == "random" else g.fixed) for g in groups.values() if g]
    if len(est) < 2:
        return None
    y = np.array([e["estimate"] for e in est])
    w = 1 / np.array([e["se"] ** 2 for e in est])
    mean = np.sum(w * y) / np.sum(w)
    q = float(np.sum(w * (y - mean) ** 2))
    df = len(est) - 1
    return {"q": q, "df": df, "p": chi2_sf(q, df)}
