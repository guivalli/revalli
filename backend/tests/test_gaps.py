import csv
import io

from tests.conftest import invite_and_join
from tests.test_extraction import _project_included

FORM = {
    "name": "Características",
    "extractors": 1,
    "fields": [
        {
            "id": "intervention",
            "label": "Intervenção",
            "type": "choice",
            "options": ["Exercício", "Yoga", "Mindfulness"],
        },
        {
            "id": "outcomes",
            "label": "Desfechos",
            "type": "multi",
            "options": ["Ansiedade", "Depressão", "Sono"],
        },
        {"id": "notes", "label": "Notas", "type": "text"},
    ],
}


async def _code(admin, base, name, parent=None):
    body = {"name": name, **({"parent_id": parent} if parent else {})}
    return (await admin.post(f"{base}/codes", json=body)).json()["id"]


def _cells(data):
    return {(c["row"], c["col"]): set(c["studies"]) for c in data["cells"]}


async def test_gap_map_from_codes(admin):
    pid, (a, b, c) = await _project_included(admin)
    base = f"/api/projects/{pid}/coding"
    inter = await _code(admin, base, "Intervenção")
    exercise = await _code(admin, base, "Exercício", inter)
    yoga = await _code(admin, base, "Yoga", inter)
    outcome = await _code(admin, base, "Desfecho")
    anxiety = await _code(admin, base, "Ansiedade", outcome)
    await _code(admin, base, "Qualidade de vida", outcome)
    gad7 = await _code(admin, base, "GAD-7", anxiety)  # subcódigo: conta como Ansiedade

    for rid, text, codes in (
        (a, "Aerobic exercise reduced anxiety", [exercise, anxiety]),
        (b, "Yoga lowered GAD-7 scores", [yoga, gad7]),
        (c, "Walking groups were offered", [exercise]),
    ):
        r = await admin.post(
            f"{base}/excerpts", json={"record_id": rid, "text": text, "code_ids": codes}
        )
        assert r.status_code == 201, r.text

    gaps = f"/api/projects/{pid}/gaps"
    dims = (await admin.get(f"{gaps}/dimensions")).json()
    assert {d["label"] for d in dims["codes"]} == {
        "Intervenção",
        "Desfecho",
        "Desfecho > Ansiedade",
    }
    assert dims["fields"] == []

    r = await admin.get(gaps, params={"rows": f"codes:{inter}", "cols": f"codes:{outcome}"})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["total_studies"] == 3
    assert [x["label"] for x in m["rows"]["categories"]] == ["Exercício", "Yoga"]
    cols = {x["label"]: x for x in m["cols"]["categories"]}
    assert set(cols) == {"Ansiedade", "Qualidade de vida", ""}  # "" = sem classificação
    cells = _cells(m)
    assert cells[(exercise, anxiety)] == {a}
    assert cells[(yoga, anxiety)] == {b}  # via GAD-7
    assert cells[(exercise, "__none__")] == {c}
    # Qualidade de vida não tem nenhum estudo: é a lacuna
    qol = next(k for k, v in cols.items() if k == "Qualidade de vida")
    assert cols[qol]["n"] == 0 and not any(col == cols[qol]["key"] for _, col in cells)
    assert m["studies"][a]["title"].startswith("Aerobic")

    # Mesmo código nos dois eixos, e CSV com a lacuna explícita
    text = (
        await admin.get(
            f"{gaps}/export", params={"rows": f"codes:{inter}", "cols": f"codes:{outcome}"}
        )
    ).text
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0] == ["Intervenção", "Desfecho", "studies", "study_labels"]
    by = {(r[0], r[1]): r[2] for r in rows[1:]}
    assert by[("Yoga", "Qualidade de vida")] == "0" and by[("Exercício", "Ansiedade")] == "1"


async def test_gap_map_from_extraction_fields(admin):
    pid, (a, b, c) = await _project_included(admin)
    form = (await admin.post(f"/api/projects/{pid}/extraction/forms", json=FORM)).json()
    fbase = f"/api/projects/{pid}/extraction/forms/{form['id']}"
    data = {
        a: {"intervention": "Exercício", "outcomes": ["Ansiedade", "Sono"]},
        b: {"intervention": "Yoga", "outcomes": ["Ansiedade"]},
        c: {"intervention": "Exercício", "outcomes": []},
    }
    units = {u["record_id"]: u for u in (await admin.get(f"{fbase}/units")).json()}
    for rid, values in data.items():
        r = await admin.put(
            f"{fbase}/units/{units[rid]['record_id']}/mine",
            json={"values": values, "status": "done"},
        )
        assert r.status_code == 200, r.text

    gaps = f"/api/projects/{pid}/gaps"
    dims = (await admin.get(f"{gaps}/dimensions")).json()
    refs = {d["label"]: d["ref"] for d in dims["fields"]}
    assert set(refs) == {"Características › Intervenção", "Características › Desfechos"}
    r = await admin.get(
        gaps,
        params={
            "rows": refs["Características › Intervenção"],
            "cols": refs["Características › Desfechos"],
        },
    )
    assert r.status_code == 200, r.text
    m = r.json()
    cells = _cells(m)
    assert cells[("Exercício", "Ansiedade")] == {a}
    assert cells[("Exercício", "Sono")] == {a}  # campo "multi": o estudo conta em cada opção
    assert cells[("Yoga", "Ansiedade")] == {b}
    assert cells[("Exercício", "__none__")] == {c}
    # Mindfulness e Depressão não têm estudos: aparecem com zero
    assert {x["label"]: x["n"] for x in m["rows"]["categories"]}["Mindfulness"] == 0
    assert {x["label"]: x["n"] for x in m["cols"]["categories"]}["Depressão"] == 0


async def test_gap_map_validation_and_permissions(admin):
    pid, _ = await _project_included(admin)
    gaps = f"/api/projects/{pid}/gaps"
    q = {"rows": "banana", "cols": "codes:x"}
    assert (await admin.get(gaps, params=q)).status_code == 422
    missing = "codes:00000000-0000-0000-0000-000000000000"
    r = await admin.get(gaps, params={"rows": missing, "cols": missing})
    assert r.status_code == 404 and r.json()["detail"] == "dimension_not_found"
    # Código sem subcódigos não serve de eixo
    base = f"/api/projects/{pid}/coding"
    leaf = await _code(admin, base, "Sozinho")
    r = await admin.get(gaps, params={"rows": f"codes:{leaf}", "cols": f"codes:{leaf}"})
    assert r.status_code == 404 and r.json()["detail"] == "code_has_no_children"
    # Quem não é do projeto não vê (404 como no resto da API)
    stranger = await invite_and_join(admin, "x@ex.org")
    assert (await stranger.get(f"{gaps}/dimensions")).status_code == 404
    await stranger.aclose()
