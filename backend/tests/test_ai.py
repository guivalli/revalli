import json

import httpx
import pytest

from revalli.modules.ai import client
from revalli.modules.ai.client import AIError, parse_json
from tests.conftest import invite_and_join
from tests.test_records import _import, _ris

TA = "title_abstract"
CALLS: list[dict] = []


def _fake_vector(text: str) -> list[float]:
    v = [0.0] * 16
    for w in text.lower().split():
        v[sum(map(ord, w)) % 16] += 1
    return v


def _fake_llm(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/embeddings"):
        texts = json.loads(request.content)["input"]
        data = [{"index": i, "embedding": _fake_vector(t)} for i, t in enumerate(texts)]
        return httpx.Response(200, json={"data": data, "usage": {"prompt_tokens": 5 * len(texts)}})
    if request.url.path.endswith("/models"):
        if request.headers.get("authorization") != "Bearer sk-test-1234":
            return httpx.Response(401, json={"error": "bad key"})
        return httpx.Response(200, json={"data": [{"id": "fake-8b"}, {"id": "fake-70b"}]})
    body = json.loads(request.content)
    CALLS.append(body)
    system = body["messages"][0]["content"]
    record = body["messages"][-1]["content"]
    if system.startswith("You help a research team turn"):
        content = json.dumps(
            {
                "summary": "Exercício para ansiedade em adultos.",
                "items": [
                    {
                        "kind": "include",
                        "name": "Adultos",
                        "definition": "Participantes com 18 anos ou mais.",
                        "examples": ["Universitários", ""],
                    },
                    {"kind": "exclude", "name": "Animais", "definition": "Estudos pré-clínicos."},
                    {"kind": "bogus", "name": "Descartado"},
                ],
                "questions": ["Qual a definição de ansiedade?", ""],
            }
        )
    elif system.startswith("You help a research team organise the reasons"):
        content = json.dumps(
            {
                "groups": [
                    {
                        "label": "Estudo com animais",
                        "existing": None,
                        "members": ["estudo em animais", "Pesquisa pré-clínica"],
                    },
                    {"label": "Fora do tema", "existing": None, "members": ["Fora do tema"]},
                ]
            }
        )
    elif system.startswith("You help a research team organise"):
        content = json.dumps(
            {
                "tags": [
                    {"name": "Ansiedade", "description": "Transtornos de ansiedade."},
                    {"name": "ansiedade", "description": "duplicada"},
                    {"name": "Yoga", "description": "Práticas de yoga."},
                ]
            }
        )
    elif "broken" in record:
        content = "sorry, no json here"
    elif "rats" in record:
        content = '<think>animals</think>{"decision": "exclude", "confidence": 0.9, '
        content += (
            '"justification": "Estudo em animais.", "exclusion_reason": "estudo em animais", '
        )
        content += '"criteria": [{"criterion": "Humanos", "status": "violated"}]}'
    elif "unclear" in record:
        content = '```json\n{"decision": "maybe", "confidence": 0.4, "justification": "?"}\n```'
    else:
        content = json.dumps(
            {
                "decision": "include",
                "confidence": 0.8,
                "justification": "Adultos com ansiedade.",
                "tags": ["ansiedade", "Novo tema", "ANSIEDADE", "a", "b", "c"],
            }
        )
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
        },
    )


@pytest.fixture(autouse=True)
def fake_llm():
    CALLS.clear()
    client.set_transport(httpx.MockTransport(_fake_llm))
    yield
    client.set_transport(None)


async def _configure(admin, local=False, price=(1.0, 2.0)):
    r = await admin.post(
        "/api/ai/providers",
        json={
            "name": "Teste",
            "kind": "custom",
            "base_url": "http://fake/v1",
            "api_key": "sk-test-1234",
            "is_local": local,
        },
    )
    assert r.status_code == 201, r.text
    prov = r.json()
    assert prov["api_key_hint"] == "…1234" and "api_key" not in prov
    s = {
        "screening": {
            "provider_id": prov["id"],
            "model": "fake-8b",
            "price_input": price[0],
            "price_output": price[1],
        },
        "embeddings": {"provider_id": prov["id"], "model": "fake-embed"},
    }
    assert (await admin.put("/api/ai/settings", json=s)).status_code == 200
    return prov


async def _project(admin, titles, reviewers=2, mode="suggest", budget=None):
    pid = (await admin.post("/api/projects", json={"title": "Exercício e ansiedade"})).json()["id"]
    content = b"".join(_ris(t, author=f"A{i}, X") + b"\n" for i, t in enumerate(titles))
    assert (await _import(admin, pid, "x.ris", content=content)).status_code == 201
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s |= {"reviewers_title_abstract": reviewers, "inclusion_criteria": "Adultos com ansiedade"}
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    ai = {"enabled": True, "mode": mode, "budget_usd": budget}
    assert (await admin.put(f"/api/projects/{pid}/ai/settings", json=ai)).status_code == 200
    return pid


def test_parse_json_variants():
    assert parse_json('<think>x</think> {"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json('Here: {"a": 3} done') == {"a": 3}
    with pytest.raises(AIError):
        parse_json("nothing")


async def test_providers_admin_only_and_key_hidden(admin):
    prov = await _configure(admin)
    assert (await admin.post(f"/api/ai/providers/{prov['id']}/test", json={})).json() == [
        "fake-70b",
        "fake-8b",
    ]
    listing = (await admin.get("/api/ai/providers")).json()
    assert "sk-test" not in json.dumps(listing)
    # Atualizar sem chave mantém a chave antiga
    body = {"name": "Novo", "base_url": "http://fake/v1", "kind": "custom"}
    r = await admin.put(f"/api/ai/providers/{prov['id']}", json=body)
    assert r.json()["api_key_hint"] == "…1234"
    assert (await admin.post(f"/api/ai/providers/{prov['id']}/test", json={})).status_code == 200
    r = await admin.put(f"/api/ai/providers/{prov['id']}", json=body | {"clear_api_key": True})
    assert r.json()["api_key_hint"] == ""
    assert (await admin.post(f"/api/ai/providers/{prov['id']}/test", json={})).status_code == 502
    ana = await invite_and_join(admin, "ana@ex.org")
    assert (await ana.get("/api/ai/providers")).status_code == 403
    await ana.aclose()


async def test_estimate_and_suggest_mode_with_cache(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety", "Anxiety in rats", "unclear thing"])
    est = (await admin.post(f"/api/projects/{pid}/ai/estimate", json={})).json()
    assert est["records"] == 3 and est["cached"] == 0 and est["cost_usd"] > 0
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["status"] == "done", job
    assert job["result"]["done"] == 3 and len(CALLS) == 3
    sugs = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()
    by = {s["decision"] for s in sugs}
    assert by == {"include", "exclude", "maybe"}
    rats = next(s for s in sugs if s["decision"] == "exclude")
    assert rats["criteria"] == [{"criterion": "Humanos", "status": "violated"}]
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    # 3 chamadas de 1000 tokens de entrada a US$1/M e 100 de saída a US$2/M
    assert usage["calls"] == 3 and usage["spent_usd"] == pytest.approx(0.0036)
    # Rodar de novo não chama o modelo: tudo vem do cache
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["result"]["cached"] == 3 and len(CALLS) == 3
    # No modo sugestão a IA não vota
    prog = (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()
    assert prog["pending"] == 3


async def test_suggestions_hidden_until_reviewer_decides(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    ana = await invite_and_join(admin, "ana@ex.org", pid, "reviewer", name="Ana")
    assert (await ana.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json() == []
    rid = (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"][0]["id"]
    await ana.post(
        f"/api/projects/{pid}/screening/{TA}/decisions",
        json={"record_id": rid, "decision": "include"},
    )
    assert len((await ana.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()) == 1
    await ana.aclose()


async def test_second_reviewer_votes_and_calibration(admin):
    await _configure(admin)
    pid = await _project(
        admin,
        ["Exercise and anxiety", "Anxiety in rats", "Yoga and anxiety"],
        mode="second_reviewer",
    )
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["result"]["done"] == 3
    prog = (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()
    ia = next(r for r in prog["reviewers"] if r["full_name"] == "IA")
    assert ia["decided"] == 3 and ia["excluded"] == 1
    # Uma pessoa completa a dupla em cada registro
    q = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"]
    for item in q:
        decision = "exclude" if "rats" in item["title"] else "include"
        if "Yoga" in item["title"]:
            decision = "exclude"  # discorda da IA
        await admin.post(
            f"/api/projects/{pid}/screening/{TA}/decisions",
            json={"record_id": item["id"], "decision": decision},
        )
    prog = (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()
    assert prog["included"] == 1 and prog["excluded"] == 1 and prog["conflicts"] == 1
    # A IA não vota de novo em registros que já têm a dupla completa
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["result"]["total"] == 0
    cal = (await admin.get(f"/api/projects/{pid}/ai/{TA}/calibration")).json()
    # Verdade humana: 1 incluído e 2 excluídos (Yoga excluído pelo humano)
    assert cal["n"] == 3 and cal["tp"] == 1 and cal["fp"] == 1 and cal["tn"] == 1
    assert cal["sensitivity"] == 1.0 and cal["specificity"] == 0.5


async def test_budget_local_only_and_flags(admin):
    await _configure(admin, local=False)
    pid = await _project(admin, ["Exercise and anxiety", "Yoga and anxiety"], budget=0.0015)
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["result"]["done"] == 1 and job["result"]["stopped"] == "budget"
    # Projeto "só local" recusa um provedor remoto
    ai = {"enabled": True, "local_only": True}
    await admin.put(f"/api/projects/{pid}/ai/settings", json=ai)
    r = await admin.post(f"/api/projects/{pid}/ai/run", json={})
    assert r.status_code == 409 and r.json()["detail"] == "ai_local_only"
    # Checagem dos excluídos: humanos excluem, a IA discorda
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["reviewers_title_abstract"] = 1
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    for item in (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"]:
        await admin.post(
            f"/api/projects/{pid}/screening/{TA}/decisions",
            json={"record_id": item["id"], "decision": "exclude"},
        )
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={"scope": "excluded"})).json()
    assert job["status"] == "done"
    flags = (await admin.get(f"/api/projects/{pid}/ai/{TA}/flags")).json()
    assert len(flags) == 2
    assert {f["record"]["title"] for f in flags} == {"Exercise and anxiety", "Yoga and anxiety"}
    assert flags[0]["suggestion"]["decision"] == "include"


async def test_invalid_answers_are_counted_not_fatal(admin):
    await _configure(admin)
    pid = await _project(admin, ["broken record", "Exercise and anxiety"])
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["status"] == "done"
    assert job["result"]["errors"] == 1 and job["result"]["done"] == 1


async def test_ai_disabled_and_not_configured(admin):
    pid = await _project(admin, ["x"])
    r = await admin.post(f"/api/projects/{pid}/ai/run", json={})
    assert r.status_code == 409 and r.json()["detail"] == "ai_not_configured"
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": False})
    assert (await admin.post(f"/api/projects/{pid}/ai/run", json={})).status_code == 409


async def test_active_learning_orders_queue_and_suggests_stop(admin):
    await _configure(admin)
    relevant = [f"Exercise reduces anxiety in adults trial {i}" for i in range(3)]
    irrelevant = [f"Liver toxicity in rats model {i}" for i in range(12)]
    pid = await _project(admin, relevant + irrelevant, reviewers=1)
    ai = {"enabled": True, "active_learning": True, "stop_after_irrelevant": 10}
    await admin.put(f"/api/projects/{pid}/ai/settings", json=ai)
    job = (await admin.post(f"/api/projects/{pid}/ai/embed", json={})).json()
    assert job["status"] == "done" and job["result"]["embedded"] == 15, job
    # Rodar de novo não recalcula nada
    job = (await admin.post(f"/api/projects/{pid}/ai/embed", json={})).json()
    assert job["result"]["embedded"] == 0

    q = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue?limit=100")).json()["items"]

    async def decide(item, decision):
        r = await admin.post(
            f"/api/projects/{pid}/screening/{TA}/decisions",
            json={"record_id": item["id"], "decision": decision},
        )
        assert r.status_code == 200

    # Sem rótulos dos dois tipos, a ordem é a de importação
    await decide(next(i for i in q if "trial 0" in i["title"]), "include")
    await decide(next(i for i in q if "rats model 0" in i["title"]), "exclude")
    q = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue?limit=3")).json()["items"]
    assert all("anxiety" in i["title"] for i in q[:2]), [i["title"] for i in q]

    for item in q[:2]:
        await decide(item, "include")
    rest = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue?limit=100")).json()
    for item in rest["items"]:
        await decide(item, "exclude")
    c = (await admin.get(f"/api/projects/{pid}/ai/curve")).json()
    assert c["screened"] == 15 and c["found"] == 3 and c["since_last_include"] == 11
    assert c["points"][-1] == {"screened": 15, "found": 3}
    # Tudo triado: não há o que parar
    assert c["should_stop"] is False


async def test_curve_suggests_stop_with_unseen_records(admin):
    await _configure(admin)
    titles = ["Exercise and anxiety"] + [f"Unrelated rats study {i}" for i in range(12)]
    pid = await _project(admin, titles, reviewers=1)
    await admin.put(
        f"/api/projects/{pid}/ai/settings", json={"enabled": True, "stop_after_irrelevant": 10}
    )
    q = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue?limit=100")).json()["items"]
    for item in q[:11]:
        decision = "include" if "anxiety" in item["title"] else "exclude"
        await admin.post(
            f"/api/projects/{pid}/screening/{TA}/decisions",
            json={"record_id": item["id"], "decision": decision},
        )
    c = (await admin.get(f"/api/projects/{pid}/ai/curve")).json()
    assert c["since_last_include"] == 10 and c["should_stop"] is True
    assert c["prioritized"] is False and c["expected_remaining"] is None


def test_logistic_regression_separates_classes():
    import numpy as np

    from revalli.modules.ai.active import predict, train_logistic

    x = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9], [0.2, 1]], dtype=np.float32)
    y = np.array([1, 1, 0, 0, 0], dtype=np.float64)
    w = train_logistic(x, y)
    p = predict(w, np.array([[1, 0], [0, 1]], dtype=np.float32))
    assert p[0] > 0.5 > p[1]


async def test_organize_criteria_returns_draft_without_saving(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    body = {
        "inclusion_criteria": "Adultos com ansiedade",
        "exclusion_criteria": "Estudos em animais",
    }
    job = (await admin.post(f"/api/projects/{pid}/ai/criteria/organize", json=body)).json()
    assert job["status"] == "done", job
    out = job["result"]
    # O item de tipo inválido some; exemplos vazios são limpos
    assert [i["name"] for i in out["items"]] == ["Adultos", "Animais"]
    assert out["items"][0]["examples"] == ["Universitários"]
    assert out["questions"] == ["Qual a definição de ansiedade?"]
    sent = CALLS[-1]["messages"][-1]["content"]
    assert "Adultos com ansiedade" in sent and "Estudos em animais" in sent
    # Nada foi salvo: o texto original continua valendo até a equipe aprovar
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    assert s["criteria_items"] == []
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    assert usage["calls"] == 1


async def test_organize_criteria_validation_and_permissions(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    url = f"/api/projects/{pid}/ai/criteria/organize"
    # Sem texto nenhum a IA propõe um rascunho a partir do título e da descrição
    job = (await admin.post(url, json={})).json()
    assert job["status"] == "done" and job["result"]["items"]
    assert "has not written any criteria yet" in CALLS[-1]["messages"][-1]["content"]
    ana = await invite_and_join(admin, "ana@ex.org", pid, "reviewer", name="Ana")
    assert (await ana.post(url, json={"inclusion_criteria": "x"})).status_code == 403
    await ana.aclose()
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": False})
    r = await admin.post(url, json={"inclusion_criteria": "x"})
    assert r.status_code == 409


async def test_approved_criteria_replace_free_text_in_prompt(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    free_prompt = CALLS[-1]["messages"][0]["content"]
    assert "Adultos com ansiedade" in free_prompt
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["criteria_items"] = [
        {"kind": "include", "name": "Adultos", "definition": "18 anos ou mais", "examples": ["x"]},
        {"kind": "exclude", "name": "Animais", "definition": "", "examples": []},
    ]
    saved = await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    assert saved.status_code == 200 and len(saved.json()["criteria_items"]) == 2
    n = len(CALLS)
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    # O prompt mudou, então a resposta antiga não vale e o modelo é chamado de novo
    assert job["result"]["cached"] == 0 and len(CALLS) == n + 1
    prompt = CALLS[-1]["messages"][0]["content"]
    assert "1. Adultos: 18 anos ou mais (examples: x)" in prompt
    assert "1. Animais" in prompt and "Adultos com ansiedade" not in prompt


async def test_tags_are_canonical_unique_and_capped(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["tag_vocabulary"] = [
        {"name": "Ansiedade", "description": "Transtornos de ansiedade"},
        {"name": "ansiedade", "description": "repetida"},
    ]
    saved = (await admin.put(f"/api/projects/{pid}/screening/settings", json=s)).json()
    assert [t["name"] for t in saved["tag_vocabulary"]] == ["Ansiedade"]
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    assert "Ansiedade: Transtornos de ansiedade" in CALLS[-1]["messages"][0]["content"]
    sug = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()[0]
    # Grafia do vocabulário, sem repetição e no máximo 4
    assert sug["tags"] == ["Ansiedade", "Novo tema", "a", "b"]
    # O vocabulário aparece nas etiquetas sugeridas ao digitar
    labels = (await admin.get(f"/api/projects/{pid}/screening/labels")).json()
    assert "Ansiedade" in labels


async def test_tags_can_be_turned_off(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    ai = {"enabled": True, "suggest_tags": False}
    await admin.put(f"/api/projects/{pid}/ai/settings", json=ai)
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    assert "Tags:" not in CALLS[-1]["messages"][0]["content"]
    sug = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()[0]
    assert sug["tags"] == []


async def test_suggest_tag_vocabulary(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety", "Yoga and anxiety"])
    job = (await admin.post(f"/api/projects/{pid}/ai/tags/suggest", json={})).json()
    assert job["status"] == "done", job
    names = [t["name"] for t in job["result"]["tags"]]
    assert names == ["Ansiedade", "Yoga"] and job["result"]["sampled"] == 2
    sent = CALLS[-1]["messages"][-1]["content"]
    assert "Exercise and anxiety" in sent and "Yoga and anxiety" in sent


async def test_reveal_suggestions_before_deciding(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    ana = await invite_and_join(admin, "ana@ex.org", pid, "reviewer", name="Ana")
    assert (await ana.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json() == []
    ai = {"enabled": True, "reveal_suggestions": "before"}
    assert (await admin.put(f"/api/projects/{pid}/ai/settings", json=ai)).status_code == 200
    assert len((await ana.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()) == 1
    await ana.aclose()


async def test_exclusion_reason_is_suggested_only_for_exclusions(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety", "Anxiety in rats"])
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    assert "Exclusion reason:" in CALLS[-1]["messages"][0]["content"]
    sugs = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()
    by = {s["decision"]: s for s in sugs}
    assert by["exclude"]["exclusion_reason"] == "estudo em animais"
    assert by["include"]["exclusion_reason"] == ""


async def test_exclusion_reason_can_be_turned_off(admin):
    await _configure(admin)
    pid = await _project(admin, ["Anxiety in rats"])
    await admin.put(
        f"/api/projects/{pid}/ai/settings", json={"enabled": True, "suggest_reasons": False}
    )
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    assert "Exclusion reason:" not in CALLS[-1]["messages"][0]["content"]
    sug = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()[0]
    assert sug["exclusion_reason"] == ""


async def test_group_and_apply_exclusion_reasons(admin):
    await _configure(admin)
    pid = await _project(admin, ["Anxiety in rats", "Rats and stress rats"])
    url = f"/api/projects/{pid}/ai/reasons/organize"
    # Sem sugestões ainda: nada para agrupar
    job = (await admin.post(url, json={})).json()
    assert job["status"] == "failed" and "no_reasons_to_group" in job["error"]
    await admin.post(f"/api/projects/{pid}/ai/run", json={})
    job = (await admin.post(url, json={})).json()
    assert job["status"] == "done", job
    groups = job["result"]["groups"]
    # A IA agrupou um motivo e esqueceu outro: nenhum motivo bruto some
    assert groups[0]["label"] == "Estudo com animais" and groups[0]["count"] == 2
    assert groups[0]["existing"] is False
    sent = CALLS[-1]["messages"][-1]["content"]
    assert "estudo em animais (2)" in sent
    # Aplicar cria o motivo no protocolo e aponta as sugestões para ele
    body = {"groups": [{"label": "Estudo com animais", "members": groups[0]["members"]}]}
    r = await admin.post(f"/api/projects/{pid}/ai/reasons/apply", json=body)
    assert r.status_code == 200 and r.json() == {"created": 1, "updated": 2}
    reasons = (await admin.get(f"/api/projects/{pid}/screening/reasons")).json()
    assert [x["label"] for x in reasons] == ["Estudo com animais"]
    sugs = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()
    assert {s["exclusion_reason"] for s in sugs} == {"Estudo com animais"}
    # Aplicar de novo reaproveita o motivo (e reativa se estava arquivado)
    await admin.patch(
        f"/api/projects/{pid}/screening/reasons/{reasons[0]['id']}", json={"archived": True}
    )
    r = await admin.post(f"/api/projects/{pid}/ai/reasons/apply", json=body)
    assert r.json()["created"] == 0
    reasons = (await admin.get(f"/api/projects/{pid}/screening/reasons")).json()
    assert len(reasons) == 1 and reasons[0]["archived"] is False


async def test_apply_reasons_is_lead_only(admin):
    await _configure(admin)
    pid = await _project(admin, ["Anxiety in rats"])
    ana = await invite_and_join(admin, "ana@ex.org", pid, "reviewer", name="Ana")
    body = {"groups": [{"label": "X", "members": []}]}
    assert (await ana.post(f"/api/projects/{pid}/ai/reasons/apply", json=body)).status_code == 403
    assert (await ana.post(f"/api/projects/{pid}/ai/reasons/organize", json={})).status_code == 403
    await ana.aclose()


async def test_screening_without_criteria_is_refused(admin):
    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["inclusion_criteria"] = "   "
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    for path in ("estimate", "run"):
        r = await admin.post(f"/api/projects/{pid}/ai/{path}", json={})
        assert r.status_code == 409 and r.json()["detail"] == "criteria_missing"
    assert CALLS == []
    # Critérios detalhados também valem
    s["criteria_items"] = [{"kind": "include", "name": "Adultos", "definition": "", "examples": []}]
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    assert (await admin.post(f"/api/projects/{pid}/ai/estimate", json={})).status_code == 200


async def test_stop_screening_keeps_what_was_done_then_continue_and_redo(admin):
    from sqlalchemy import update

    from revalli.core.db import SessionLocal
    from revalli.models import Job

    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety", "Yoga and anxiety", "Anxiety in rats"])
    calls = {"n": 0}

    async def stopping(request: httpx.Request) -> httpx.Response:
        response = _fake_llm(request)
        calls["n"] += 1
        if calls["n"] == 1:
            # A pessoa clica em "Parar" enquanto o primeiro registro é analisado
            async with SessionLocal() as db:
                await db.execute(
                    update(Job).where(Job.kind == "ai_screen").values(status="cancelling")
                )
                await db.commit()
        return response

    client.set_transport(httpx.MockTransport(stopping))
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["status"] == "cancelled", job
    assert job["result"]["done"] == 1 and job["result"]["stopped"] == "user"
    sugs = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()
    assert len(sugs) == 1
    # Parado não é falha: não aparece como tarefa ativa nem como erro
    assert (await admin.get(f"/api/projects/{pid}/jobs?active=true")).json() == []

    # Continuar: o que já foi analisado vem do cache
    client.set_transport(httpx.MockTransport(_fake_llm))
    n = len(CALLS)
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={})).json()
    assert job["status"] == "done" and job["result"]["cached"] == 1 and job["result"]["done"] == 3
    assert len(CALLS) == n + 2

    # Refazer: analisa tudo de novo e atualiza as respostas, sem duplicá-las
    n = len(CALLS)
    est = (await admin.post(f"/api/projects/{pid}/ai/estimate", json={"force": True})).json()
    assert est["cached"] == 0 and est["records"] == 3
    job = (await admin.post(f"/api/projects/{pid}/ai/run", json={"force": True})).json()
    assert job["result"]["cached"] == 0 and len(CALLS) == n + 3
    sugs = (await admin.get(f"/api/projects/{pid}/ai/{TA}/suggestions")).json()
    assert len(sugs) == 3


async def test_cancel_endpoint_states_and_permissions(admin):
    from revalli.core.db import SessionLocal
    from revalli.models import Job

    await _configure(admin)
    pid = await _project(admin, ["Exercise and anxiety"])
    ana = await invite_and_join(admin, "ana@ex.org", pid, "reviewer", name="Ana")
    async with SessionLocal() as db:
        queued = Job(project_id=pid, kind="ai_screen", status="queued")
        running = Job(project_id=pid, kind="ai_screen", status="running")
        done = Job(project_id=pid, kind="ai_screen", status="done")
        other = Job(project_id=pid, kind="dedup", status="running")
        db.add_all([queued, running, done, other])
        await db.commit()
        ids = [j.id for j in (queued, running, done, other)]
    url = f"/api/projects/{pid}/jobs"
    assert (await ana.post(f"{url}/{ids[0]}/cancel", json={})).status_code == 403
    await ana.aclose()
    assert (await admin.post(f"{url}/{ids[0]}/cancel", json={})).json()["status"] == "cancelled"
    assert (await admin.post(f"{url}/{ids[1]}/cancel", json={})).json()["status"] == "cancelling"
    assert (await admin.post(f"{url}/{ids[2]}/cancel", json={})).json()["status"] == "done"
    r = await admin.post(f"{url}/{ids[3]}/cancel", json={})
    assert r.status_code == 409 and r.json()["detail"] == "not_cancellable"
    # Parando ainda conta como tarefa ativa, para a interface mostrar "parando…"
    active = (await admin.get(f"{url}?active=true")).json()
    assert {j["status"] for j in active} == {"cancelling", "running"}
