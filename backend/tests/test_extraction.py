import csv
import io
import json
import uuid

import httpx

from revalli.modules.ai import client
from revalli.modules.extraction.ai import Page, locate_quote
from revalli.modules.extraction.templates import rob2_fields, robins_fields, suggest
from tests.conftest import invite_and_join
from tests.test_fulltext import TITLES, _project_ft, _upload, make_pdf

FT = "full_text"


async def _project_included(admin):
    pid, ids = await _project_ft(admin)
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["reviewers_full_text"] = 1
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    for it in (await admin.get(f"/api/projects/{pid}/screening/{FT}/queue")).json()["items"]:
        await admin.post(
            f"/api/projects/{pid}/screening/{FT}/decisions",
            json={"record_id": it["id"], "decision": "include"},
        )
    return pid, [ids[t] for t, _ in TITLES]


SIMPLE = {
    "name": "Dados",
    "extractors": 2,
    "fields": [
        {"id": "s1", "label": "Estudo", "type": "section"},
        {"id": "country", "label": "País", "type": "text", "required": True},
        {"id": "n", "label": "N", "type": "integer"},
        {"id": "design", "label": "Desenho", "type": "choice", "options": ["ECR", "Coorte"]},
        {
            "id": "dose",
            "label": "Dose",
            "type": "number",
            "show_if": [{"field": "design", "values": ["ECR"]}],
        },
        {
            "id": "arms",
            "label": "Grupos",
            "type": "table",
            "columns": [
                {"id": "group", "label": "Grupo"},
                {"id": "n", "label": "N", "type": "integer"},
                {"id": "mean", "label": "Média", "type": "number"},
            ],
        },
    ],
}


async def test_form_crud_and_versions(admin):
    pid, _ = await _project_included(admin)
    base = f"/api/projects/{pid}/extraction/forms"
    r = await admin.post(base, json=SIMPLE)
    assert r.status_code == 201, r.text
    form = r.json()
    assert form["version"] == 1
    bad = {**SIMPLE, "fields": [*SIMPLE["fields"], {"id": "n", "label": "x", "type": "text"}]}
    assert (await admin.post(base, json=bad)).status_code == 422
    no_opts = {**SIMPLE, "fields": [{"id": "x", "label": "x", "type": "choice"}]}
    assert (await admin.post(base, json=no_opts)).status_code == 422
    # Mudar só o nome não cria versão nova; mudar campos cria
    r = await admin.put(f"{base}/{form['id']}", json={**SIMPLE, "name": "Dados 2"})
    assert r.json()["version"] == 1 and r.json()["name"] == "Dados 2"
    r = await admin.put(
        f"{base}/{form['id']}", json={**SIMPLE, "name": "Dados 2", "fields": SIMPLE["fields"][:3]}
    )
    assert r.json()["version"] == 2
    for tpl in ("rob2", "robins_i", "study_characteristics"):
        r = await admin.post(f"{base}/template", json={"template": tpl})
        assert r.status_code == 201, r.text
    names = [f["name"] for f in (await admin.get(base)).json()]
    assert names == ["Dados 2", "RoB 2", "ROBINS-I", "Características dos estudos"]
    assert (await admin.delete(f"{base}/{form['id']}")).status_code == 204
    assert len((await admin.get(base)).json()) == 3


async def test_double_extraction_compare_consensus_export(admin):
    pid, (a, b, c) = await _project_included(admin)
    rev = await invite_and_join(admin, "rev@ex.org", pid, "extractor")
    obs = await invite_and_join(admin, "obs@ex.org", pid, "observer")
    form = (await admin.post(f"/api/projects/{pid}/extraction/forms", json=SIMPLE)).json()
    base = f"/api/projects/{pid}/extraction/forms/{form['id']}"
    # Dois relatórios do mesmo estudo viram uma unidade só
    await admin.post(f"/api/projects/{pid}/studies", json={"record_ids": [a, b], "label": "Silva"})
    units = (await admin.get(f"{base}/units")).json()
    assert len(units) == 2 and all(u["state"] == "pending" for u in units)
    unit = next(u for u in units if u["label"] == "Silva")
    assert set(unit["report_ids"]) == {a, b}
    rid = unit["record_id"]

    # Validação
    r = await admin.put(f"{base}/units/{rid}/mine", json={"values": {"n": "doze"}})
    assert r.status_code == 422 and "n" in r.json()["detail"]
    r = await admin.put(f"{base}/units/{rid}/mine", json={"values": {"design": "X"}})
    assert r.status_code == 422
    r = await admin.put(f"{base}/units/{rid}/mine", json={"values": {"n": 10}, "status": "done"})
    assert r.status_code == 422 and "country" in r.json()["detail"]

    mine = {
        "country": " Brasil ",
        "n": "120",
        "design": "Coorte",
        "dose": 5,  # oculto: só vale para ECR
        "arms": [{"group": "Exercício", "n": 60, "mean": "12,5"}, {"group": ""}],
    }
    r = await admin.put(
        f"{base}/units/{rid}/mine",
        json={"values": mine, "quotes": {"n": {"text": "120 participants", "page": 2}}},
    )
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["values"] == {
        "country": "Brasil",
        "n": 120,
        "design": "Coorte",
        "arms": [{"group": "Exercício", "n": 60, "mean": 12.5}],
    }
    assert saved["quotes"]["n"]["page"] == 2 and saved["status"] == "draft"

    # A outra pessoa não vê nada antes de terminar
    detail = (await rev.get(f"{base}/units/{rid}")).json()
    assert detail["others"] == [] and detail["can_see_others"] is False
    assert (await rev.get(f"{base}/units/{rid}/compare")).status_code == 403
    assert (await obs.put(f"{base}/units/{rid}/mine", json={"values": {}})).status_code == 403
    assert (await rev.get(f"{base}/export")).status_code == 403

    other = {**mine, "country": "brasil", "n": 118}
    r = await rev.put(f"{base}/units/{rid}/mine", json={"values": other, "status": "done"})
    assert r.status_code == 200, r.text
    detail = (await rev.get(f"{base}/units/{rid}")).json()
    assert detail["can_see_others"] is True and len(detail["others"]) == 1
    await admin.put(f"{base}/units/{rid}/mine", json={"values": mine, "status": "done"})

    states = {u["record_id"]: u["state"] for u in (await admin.get(f"{base}/units")).json()}
    assert states[rid] == "conflict"
    cmp = (await admin.get(f"{base}/units/{rid}/compare")).json()
    by_field = {f["field_id"]: f["agree"] for f in cmp["fields"]}
    assert by_field == {"country": True, "n": False, "design": True, "arms": True}
    assert "n" not in cmp["agreed_values"] and cmp["agreed_values"]["design"] == "Coorte"

    # Consenso: só líder ou árbitro
    final = {**cmp["agreed_values"], "n": 120}
    assert (
        await rev.put(f"{base}/units/{rid}/consensus", json={"values": final})
    ).status_code == 403
    r = await admin.put(f"{base}/units/{rid}/consensus", json={"values": final})
    assert r.status_code == 200 and r.json()["status"] == "done"
    states = {u["record_id"]: u["state"] for u in (await admin.get(f"{base}/units")).json()}
    assert states[rid] == "resolved"

    wide = list(csv.reader(io.StringIO((await admin.get(f"{base}/export")).text.lstrip("﻿"))))
    header, rows = wide[0], wide[1:]
    assert header[:6] == ["study", "record_id", "title", "year", "doi", "status"]
    assert "arms.mean" in header
    row = next(r for r in rows if r[0] == "Silva")
    assert row[header.index("status")] == "consensus" and row[header.index("n")] == "120"
    assert row[header.index("arms.group")] == "Exercício"
    long_text = (await admin.get(f"{base}/export?layout=long")).text
    assert "arms,Grupos,1,mean,12.5" in long_text

    for cl in (rev, obs):
        await cl.aclose()


async def test_rob2_template_and_summary(admin):
    pid, (a, b, c) = await _project_included(admin)
    r = await admin.post(
        f"/api/projects/{pid}/extraction/forms/template", json={"template": "rob2", "extractors": 1}
    )
    form = r.json()
    base = f"/api/projects/{pid}/extraction/forms/{form['id']}"
    low = {
        "d1_1": "Y", "d1_2": "Y", "d1_3": "N",
        "d2_1": "N", "d2_2": "N", "d2_6": "Y",
        "d3_1": "Y",
        "d4_1": "N", "d4_2": "N", "d4_3": "N",
        "d5_1": "Y", "d5_2": "N", "d5_3": "N",
    }  # fmt: skip
    r = await admin.put(f"{base}/units/{a}/mine", json={"values": low, "status": "done"})
    assert r.status_code == 200, r.text
    assert r.json()["suggested"]["overall_j"] == "low"
    high = {**low, "d1_2": "N"}
    r = await admin.put(f"{base}/units/{b}/mine", json={"values": high, "status": "done"})
    assert r.json()["suggested"]["d1_j"] == "high" and r.json()["suggested"]["overall_j"] == "high"
    # Julgamento escolhido pela pessoa vale mais que o calculado
    some = {**low, "d3_j": "some"}
    await admin.put(f"{base}/units/{c}/mine", json={"values": some, "status": "done"})
    assert {u["state"] for u in (await admin.get(f"{base}/units")).json()} == {"complete"}
    summary = (await admin.get(f"{base}/rob")).json()
    assert [d["domain"] for d in summary["domains"]] == ["d1", "d2", "d3", "d4", "d5", "overall"]
    assert summary["scale"] == ["low", "some", "high"]
    overall = {row["record_id"]: row["judgements"]["overall_j"] for row in summary["rows"]}
    assert overall == {a: "low", b: "high", c: "some"}


def _rob2(**answers):
    return suggest(rob2_fields(), answers)


def test_rob2_algorithm():
    assert _rob2(d1_1="Y", d1_2="Y", d1_3="N")["d1_j"] == "low"
    assert _rob2(d1_1="N", d1_2="Y", d1_3="N")["d1_j"] == "some"
    assert _rob2(d1_1="Y", d1_2="NI", d1_3="Y")["d1_j"] == "high"
    assert _rob2(d1_1="Y", d1_2="NI", d1_3="N")["d1_j"] == "some"
    assert "d1_j" not in _rob2(d1_1="Y", d1_2="Y")
    # D2: sem cegamento, desvios que afetam o desfecho e desequilibrados
    d2 = dict(d2_1="Y", d2_2="Y", d2_3="Y", d2_4="Y", d2_5="N", d2_6="Y")
    assert _rob2(**d2)["d2_j"] == "high"
    assert _rob2(**{**d2, "d2_5": "Y"})["d2_j"] == "some"
    assert _rob2(**{**d2, "d2_3": "N"})["d2_j"] == "low"
    assert _rob2(**{**d2, "d2_3": "N", "d2_6": "N", "d2_7": "Y"})["d2_j"] == "high"
    assert _rob2(d3_1="N", d3_2="N", d3_3="Y", d3_4="N")["d3_j"] == "some"
    assert _rob2(d3_1="N", d3_2="N", d3_3="Y", d3_4="PY")["d3_j"] == "high"
    assert _rob2(d4_1="N", d4_2="NI", d4_3="N")["d4_j"] == "some"
    assert _rob2(d4_1="PY", d4_2="N")["d4_j"] == "high"
    assert _rob2(d5_1="N", d5_2="N", d5_3="N")["d5_j"] == "some"
    assert _rob2(d5_2="Y")["d5_j"] == "high"


def test_robins_overall():
    fields = robins_fields()
    vals = {f"d{i}_j": "low" for i in range(1, 8)}
    assert suggest(fields, vals)["overall_j"] == "low"
    assert suggest(fields, {**vals, "d3_j": "moderate", "d5_j": "ni"})["overall_j"] == "ni"
    assert suggest(fields, {**vals, "d5_j": "ni", "d2_j": "serious"})["overall_j"] == "serious"
    assert "overall_j" not in suggest(fields, {"d1_j": "low"})


# --- Extração por IA ---------------------------------------------------------------------

AI_FORM = {
    "name": "IA",
    "extractors": 1,
    "fields": [
        {"id": "n", "label": "Número de participantes", "type": "integer", "ai": True},
        {"id": "country", "label": "País", "type": "text", "ai": True},
        {
            "id": "design",
            "label": "Desenho",
            "type": "choice",
            "options": ["ECR", "Coorte"],
            "ai": True,
        },
        {"id": "notes", "label": "Notas", "type": "long_text"},
    ],
}


def _fake_extract(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    prompt = body["messages"][-1]["content"]
    assert "[[page 1]]" in prompt and '"id": "notes"' not in prompt
    answer = {
        "fields": {
            "n": {"value": "120", "quote": "We randomised 120 adults with anxiety", "page": 1},
            # Trecho inventado: não existe no PDF
            "country": {"value": "Brasil", "quote": "The trial took place in Lisbon", "page": 2},
            "design": {"value": "Meta-análise", "quote": None, "page": None},
        }
    }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(answer)}}],
            "usage": {"prompt_tokens": 3000, "completion_tokens": 200},
        },
    )


def test_locate_quote():
    pages = [Page(uuid.uuid4(), 1, "Intro."), Page(uuid.uuid4(), 2, "We  randomised 120\nadults.")]
    found = locate_quote("we randomised 120 adults", pages)
    assert found["page"] == 2 and found["score"] == 100
    assert locate_quote("short", pages) is None
    assert locate_quote("completely different sentence here", pages)["score"] < 90


async def test_ai_extraction_with_verified_quotes(admin):
    pid, (a, b, c) = await _project_included(admin)
    prov = (
        await admin.post(
            "/api/ai/providers",
            json={"name": "T", "kind": "custom", "base_url": "http://fake/v1", "is_local": True},
        )
    ).json()
    choice = {"provider_id": prov["id"], "model": "fake"}
    await admin.put("/api/ai/settings", json={"extraction": choice})
    form = (await admin.post(f"/api/projects/{pid}/extraction/forms", json=AI_FORM)).json()
    base = f"/api/projects/{pid}/extraction/forms/{form['id']}"
    assert (await admin.post(f"{base}/ai", json={})).status_code == 409  # IA desligada
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    pdf = make_pdf("Aerobic exercise trial", "We randomised 120 adults with anxiety to exercise.")
    await _upload(admin, pid, a, pdf)
    client.set_transport(httpx.MockTransport(_fake_extract))
    try:
        r = await admin.post(f"{base}/ai", json={})
    finally:
        client.set_transport(None)
    assert r.status_code == 202, r.text
    assert r.json()["result"] == {"total": 3, "done": 1, "no_pdf": 2, "errors": 0, "stopped": None}
    detail = (await admin.get(f"{base}/units/{a}")).json()
    ai_ext = detail["ai"]
    assert ai_ext["values"] == {"n": 120, "country": "Brasil"}  # opção inválida descartada
    assert ai_ext["quotes"]["n"]["verified"] is True and ai_ext["quotes"]["n"]["page"] == 1
    assert ai_ext["quotes"]["country"]["verified"] is False
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    assert usage["calls"] == 1 and usage["input_tokens"] == 3000
