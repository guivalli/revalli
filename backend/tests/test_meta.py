import math

import pytest

from revalli.modules.meta import stats
from tests.conftest import invite_and_join

# Ensaios da vacina BCG (Colditz et al., 1994), conjunto clássico de meta-análise
BCG = [
    ("Aronson 1948", 4, 119, 11, 128),
    ("Ferguson 1949", 6, 300, 29, 274),
    ("Rosenthal 1960", 3, 228, 11, 209),
    ("Hart 1977", 62, 13536, 248, 12619),
    ("Frimodt-Moller 1973", 33, 5036, 47, 5761),
    ("Stein 1953", 180, 1361, 372, 1079),
    ("Vandiviere 1973", 8, 2537, 10, 619),
    ("TPT Madras 1980", 505, 87886, 499, 87892),
    ("Coetzee 1968", 29, 7470, 45, 7232),
    ("Rosenthal 1961", 17, 1699, 65, 1600),
    ("Comstock 1974", 186, 50448, 141, 27197),
    ("Comstock 1969", 5, 2493, 3, 2338),
    ("Comstock 1976", 27, 16886, 29, 17825),
]


def _bcg_rows(subgroups=False):
    return [
        {
            "id": f"r{i}",
            "label": name,
            "subgroup": ("antes de 1960" if int(name[-4:]) < 1960 else "depois")
            if subgroups
            else "",
            "e1": a,
            "n1": a + b,
            "e2": c,
            "n2": c + d,
        }
        for i, (name, a, b, c, d) in enumerate(BCG)
    ]


def test_distributions():
    assert stats.t_ppf(0.975, 11) == pytest.approx(2.200985, abs=1e-5)
    assert stats.chi2_sf(3.841459, 1) == pytest.approx(0.05, abs=1e-6)
    assert stats.t_sf(2.0, 10) == pytest.approx(0.036694, abs=1e-6)
    assert stats.norm_sf(1.959964) == pytest.approx(0.025, abs=1e-7)


def test_effect_sizes():
    # Diferença de médias padronizada (g de Hedges)
    e = stats.effect("SMD", {"n1": 20, "mean1": 10, "sd1": 2, "n2": 20, "mean2": 8, "sd2": 2})
    assert e.yi == pytest.approx(1 - 3 / 151)
    assert stats.effect("MD", {"n1": 10, "mean1": 5, "sd1": 1, "n2": 10, "mean2": 3}).skipped
    # Zero eventos num braço: correção de 0,5; nos dois braços: fica de fora
    z = stats.effect("OR", {"e1": 0, "n1": 10, "e2": 3, "n2": 10})
    assert z.corrected and z.yi == pytest.approx(math.log((0.5 * 7.5) / (10.5 * 3.5)))
    assert stats.effect("RR", {"e1": 0, "n1": 10, "e2": 0, "n2": 10}).skipped == "double_zero"
    hr = stats.effect("HR", {"hr": 0.8, "hr_lower": 0.64, "hr_upper": 1.0})
    assert hr.yi == pytest.approx(math.log(0.8))
    assert math.sqrt(hr.vi) == pytest.approx((math.log(1.0) - math.log(0.64)) / 3.919928, rel=1e-6)


async def test_meta_analysis_matches_reference(admin):
    pid = (await admin.post("/api/projects", json={"title": "BCG"})).json()["id"]
    base = f"/api/projects/{pid}/meta"
    body = {"name": "Tuberculose", "measure": "RR", "rows": _bcg_rows(), "label1": "BCG"}
    r = await admin.post(base, json=body)
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    res = (await admin.get(f"{base}/{aid}/result")).json()
    p = res["pooled"]
    # Valores de referência publicados para este conjunto (DerSimonian-Laird)
    assert math.log(p["estimate"]) == pytest.approx(-0.7141, abs=1e-4)
    assert p["tau2"] == pytest.approx(0.3088, abs=1e-4)
    assert p["i2"] == pytest.approx(92.12, abs=0.01)
    assert p["q"] == pytest.approx(152.2330, abs=1e-3) and p["df"] == 12
    assert p["k"] == 13 and p["participants"] == sum(a + b + c + d for _, a, b, c, d in BCG)
    assert sum(s["weight"] for s in res["studies"]) == pytest.approx(100)
    assert res["log_scale"] and res["egger"] is not None
    lo, hi = p["prediction"]
    assert lo < p["estimate"] < hi

    fixed = {**body, "model": "fixed"}
    await admin.put(f"{base}/{aid}", json=fixed)
    p = (await admin.get(f"{base}/{aid}/result")).json()["pooled"]
    assert math.log(p["estimate"]) == pytest.approx(-0.4303, abs=1e-4)
    assert p["prediction"] is None and p["tau2"] == 0

    grouped = {**body, "rows": _bcg_rows(subgroups=True)}
    await admin.put(f"{base}/{aid}", json=grouped)
    res = (await admin.get(f"{base}/{aid}/result")).json()
    assert [g["name"] for g in res["subgroups"]] == ["antes de 1960", "depois"]
    assert res["subgroup_test"]["df"] == 1

    csv_text = (await admin.get(f"{base}/{aid}/export")).text
    assert "Aronson 1948" in csv_text and "weight" in csv_text

    dup = {**body, "rows": [_bcg_rows()[0], _bcg_rows()[0]]}
    assert (await admin.put(f"{base}/{aid}", json=dup)).status_code == 422


async def test_grade_rows(admin):
    pid = (await admin.post("/api/projects", json={"title": "BCG"})).json()["id"]
    rev = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    aid = (
        await admin.post(
            f"/api/projects/{pid}/meta", json={"name": "TB", "measure": "RR", "rows": _bcg_rows()}
        )
    ).json()["id"]
    base = f"/api/projects/{pid}/grade"
    body = {
        "outcome": "Tuberculose",
        "analysis_id": aid,
        "domains": {"inconsistency": {"rating": -2, "reason": "I² de 92%"}},
    }
    assert (await rev.post(base, json=body)).status_code == 403
    r = await admin.post(base, json=body)
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["certainty"] == "low"
    assert g["auto"]["k"] == 13 and not g["auto"]["crosses_null"]
    assert g["auto"]["egger_p"] is not None
    assert "inconsistency_high" in g["suggestions"]
    # Observacional começa em baixa; subir por efeito grande
    obs = {
        "outcome": "Outro",
        "design": "observational",
        "domains": {"large_effect": {"rating": 1}},
    }
    g2 = (await admin.post(base, json=obs)).json()
    assert g2["certainty"] == "moderate" and g2["auto"] is None
    worst = {
        "outcome": "X",
        "domains": {k: {"rating": -2} for k in ("risk_of_bias", "imprecision")},
    }
    assert (await admin.post(base, json=worst)).json()["certainty"] == "very_low"
    rows = (await rev.get(base)).json()
    assert [x["outcome"] for x in rows] == ["Tuberculose", "Outro", "X"]
    # Apagar a meta-análise mantém a linha, sem os dados automáticos
    assert (await admin.delete(f"/api/projects/{pid}/meta/{aid}")).status_code == 204
    row = (await rev.get(base)).json()[0]
    assert row["analysis_id"] is None and row["auto"] is None
    bad = {**body, "analysis_id": aid}
    assert (await admin.put(f"{base}/{row['id']}", json=bad)).status_code == 404
