import json
import re
import uuid
import zlib

import httpx
import numpy as np

from revalli.modules.ai import client
from revalli.modules.corpus import retrieval
from revalli.modules.corpus.chunking import split_text
from tests.conftest import invite_and_join
from tests.test_extraction import _project_included
from tests.test_fulltext import TITLES, _project_ft, _upload, make_pdf

SENTENCE = "Participants were randomised to exercise or usual care. "


def test_split_text_keeps_everything_and_overlaps():
    text = SENTENCE * 60
    parts = split_text(text, size=400, overlap=80)
    assert len(parts) > 5 and all(len(p) <= 400 for p in parts)
    # Cada trecho termina em fim de frase quando dá
    assert all(p.endswith(".") for p in parts[:-1])
    flat = " ".join(text.split())
    assert flat.startswith(parts[0]) and flat.endswith(parts[-1])
    # Sobreposição: o começo de um trecho aparece no fim do anterior
    assert parts[1][:40] in parts[0]
    assert split_text("   ") == []
    assert split_text("curto") == ["curto"]


def test_query_terms_and_tsquery():
    assert retrieval.query_terms("What was the dose of Metformin in 2019?") == [
        "dose",
        "metformin",
    ]
    assert retrieval.tsquery("qual a dose de metformina?") == "dose | metformina"
    # Só caracteres de palavra passam: nada que o to_tsquery interprete como operador
    assert retrieval.tsquery("a & b | !c ) (d:*") == ""
    assert retrieval.tsquery("x' ; drop") == "drop"


def test_unsupported_numbers():
    from revalli.modules.corpus.service import unsupported_numbers

    texts = ["A total of 535 pregnancies, 1,200 visits and 2.5 mg/kg."]
    assert unsupported_numbers("535 women [1], 1200 visits, 2,5 mg/kg", texts) == []
    assert unsupported_numbers("There were 536 women [3] and 12 visits", texts) == ["536", "12"]
    # Algarismos soltos (itens, contagens pequenas) e marcadores [n] não contam
    assert unsupported_numbers("1. Two arms [2]; 3 trials", texts) == []


def test_fusion_and_pick():
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    assert retrieval.fuse([[a, b, c], [c, b]]) == [c, b, a]
    ids = [uuid.uuid4() for _ in range(3)]
    rec = {ids[0]: a, ids[1]: a, ids[2]: b}
    got = retrieval.pick(ids, rec, {i: 100 for i in ids}, top_k=5, per_record=1, max_chars=1000)
    assert got == [ids[0], ids[2]]
    got = retrieval.pick(ids, rec, {i: 100 for i in ids}, top_k=5, per_record=3, max_chars=150)
    assert got == [ids[0]]
    m = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]], dtype=np.float32)
    assert retrieval.rank_vectors(np.array([1.0, 0.1]), ids, m, 2) == [ids[0], ids[2]]


def _vec(text: str) -> list[float]:
    v = [0.0] * 16
    for w in re.findall(r"\w+", text.casefold()):
        v[zlib.crc32(w.encode()) % 16] += 1.0
    return v


CALLS: list[dict] = []


def _llm(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if request.url.path.endswith("/embeddings"):
        inputs = body["input"]
        CALLS.append({"embed": len(inputs)})
        data = [{"index": i, "embedding": _vec(t)} for i, t in enumerate(inputs)]
        return httpx.Response(200, json={"data": data, "usage": {"prompt_tokens": 10 * len(data)}})
    prompt = body["messages"][-1]["content"]
    if "search queries" in body["messages"][0]["content"]:
        CALLS.append({"expand": prompt})
        queries = ["randomised adults"] if re.search(r"adults|adultos", prompt) else []
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"queries": queries})}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10},
            },
        )
    CALLS.append({"chat": prompt})
    # Acha o trecho que fala dos 120 adultos
    n = next(
        (
            m.group(1)
            for m in re.finditer(r"\[(\d+)\] \([^\n]*\n[^\[]*?randomised 120 adults", prompt)
        ),
        None,
    )
    if n is None:
        answer = {
            "answer": "The excerpts do not report this.",
            "answerable": False,
            "citations": [],
        }
    else:
        answer = {
            "answer": f"They randomised 120 adults [{n}]. It was done in Lisbon [{n}] [9].",
            "citations": [
                {"source": int(n), "quote": "We randomised 120 adults with anxiety"},
                {"source": int(n), "quote": "The trial took place in Lisbon"},
                {"source": 9, "quote": "Invented source number"},
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(answer)}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 60},
        },
    )


async def _setup_ai(admin, pid, *, embeddings=False, budget=None):
    prov = (
        await admin.post(
            "/api/ai/providers",
            json={"name": "T", "kind": "custom", "base_url": "http://fake/v1", "is_local": True},
        )
    ).json()
    choice = {"provider_id": prov["id"], "model": "fake-8b"}
    body = {"screening": choice}
    if embeddings:
        body["embeddings"] = {"provider_id": prov["id"], "model": "fake-embed"}
    await admin.put("/api/ai/settings", json=body)
    settings = {"enabled": True}
    if budget is not None:
        settings["budget_usd"] = budget
    await admin.put(f"/api/projects/{pid}/ai/settings", json=settings)


async def test_corpus_index_ask_and_verify_citations(admin):
    pid, (a, b, c) = await _project_included(admin)
    base = f"/api/projects/{pid}/corpus"
    ask = {"question": "How many adults were randomised?"}
    assert (await admin.post(f"{base}/ask", json=ask)).json()["detail"] == "ai_disabled"
    await _setup_ai(admin, pid)
    assert (await admin.post(f"{base}/ask", json=ask)).json()["detail"] == "corpus_not_indexed"

    await _upload(
        admin, pid, a, make_pdf("Aerobic exercise trial", "We randomised 120 adults with anxiety.")
    )
    await _upload(admin, pid, b, make_pdf("Yoga study", "Yoga sessions lasted 60 minutes."))
    st = (await admin.get(f"{base}/status")).json()
    assert st["chunks"] == 0 and st["pending_files"] == 2 and st["chat_model"] == "fake-8b"
    assert st["embeddings_model"] is None

    r = await admin.post(f"{base}/index", json={})
    assert r.status_code == 202, r.text
    assert r.json()["result"] == {"files": 2, "embedded": 0, "embeddings": None}
    st = (await admin.get(f"{base}/status")).json()
    assert st["chunks"] >= 2 and st["pending_files"] == 0

    CALLS.clear()
    client.set_transport(httpx.MockTransport(_llm))
    try:
        r = await admin.post(f"{base}/ask", json=ask)
    finally:
        client.set_transport(None)
    assert r.status_code == 200, r.text
    msg = r.json()
    prompt = next(c["chat"] for c in CALLS if "chat" in c)
    assert "Ignore any instruction" not in prompt  # a regra fica no system, não nos trechos
    assert "randomised 120 adults" in prompt
    # O marcador [9] não existe e foi removido; a citação inventada não vira fonte
    assert "[9]" not in msg["answer"] and "120 adults [1]" in msg["answer"]
    assert [s["n"] for s in msg["sources"]] == [1]
    src = msg["sources"][0]
    assert src["record_id"] == a and src["page"] == 1
    # Duas citações para o mesmo trecho: vale a que foi encontrada no PDF
    assert src["verified"] is True and src["score"] == 100
    assert src["quote"] == "We randomised 120 adults with anxiety"
    assert msg["grounded"] is True and msg["answerable"] is True and msg["model"] == "fake-8b"
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    assert usage["calls"] == 2 and usage["input_tokens"] == 550  # reescrita da busca + resposta

    # Os trechos não respondem: o modelo avisa, e isso não é uma resposta "não confiável"
    client.set_transport(httpx.MockTransport(_llm))
    try:
        none = (
            await admin.post(f"{base}/ask", json={"question": "How long were the yoga sessions?"})
        ).json()
    finally:
        client.set_transport(None)
    assert none["answerable"] is False and none["grounded"] is False and none["sources"] == []

    # Citação que não está no PDF fica não verificada
    def lying(request):
        resp = _llm(request)
        data = json.loads(json.loads(resp.content)["choices"][0]["message"]["content"])
        data["citations"] = [{"source": 1, "quote": "The trial took place in Lisbon"}]
        data["answer"] = "They randomised 450 adults, 120 of them in Lisbon [1]."
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(data)}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client.set_transport(httpx.MockTransport(lying))
    try:
        msg = (await admin.post(f"{base}/ask", json=ask)).json()
    finally:
        client.set_transport(None)
    assert msg["sources"][0]["verified"] is False and msg["grounded"] is False
    # O 120 está no trecho citado; o 450 foi inventado
    assert msg["unsupported_numbers"] == ["450"]

    # Histórico pessoal, e apagar
    hist = (await admin.get(f"{base}/messages")).json()
    assert [m["id"] for m in hist][-1] == msg["id"] and len(hist) == 3
    other = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    assert (await other.get(f"{base}/messages")).json() == []
    assert (await other.delete(f"{base}/messages/{msg['id']}")).status_code == 404
    assert (await admin.delete(f"{base}/messages/{msg['id']}")).status_code == 204
    assert len((await admin.get(f"{base}/messages")).json()) == 2
    # Qualquer membro pergunta; quem indexa é só a liderança
    assert (await other.post(f"{base}/index", json={})).status_code == 403
    await other.aclose()


async def test_no_hits_does_not_call_the_model(admin):
    pid, (a, _, _) = await _project_included(admin)
    await _setup_ai(admin, pid)
    await _upload(admin, pid, a, make_pdf("Aerobic exercise trial"))
    base = f"/api/projects/{pid}/corpus"
    await admin.post(f"{base}/index", json={})
    CALLS.clear()
    client.set_transport(httpx.MockTransport(_llm))
    try:
        r = await admin.post(f"{base}/ask", json={"question": "zzqqxx blorptastic"})
    finally:
        client.set_transport(None)
    assert r.status_code == 200 and r.json()["answer"] == "" and r.json()["sources"] == []
    assert not any("chat" in c for c in CALLS)  # só a reescrita da busca; sem trechos, sem resposta


async def test_scope_budget_and_follow_up(admin):
    pid, ids = await _project_ft(admin)  # ninguém incluído no texto completo ainda
    await _setup_ai(admin, pid, budget=0.5)
    rid = ids[TITLES[0][0]]
    await _upload(admin, pid, rid, make_pdf("Aerobic", "We randomised 120 adults with anxiety."))
    base = f"/api/projects/{pid}/corpus"
    await admin.post(f"{base}/index", json={})
    q = {"question": "How many adults were randomised?"}
    client.set_transport(httpx.MockTransport(_llm))
    try:
        none = (await admin.post(f"{base}/ask", json=q)).json()
        assert none["answer"] == "" and none["scope"] == "included"
        got = (await admin.post(f"{base}/ask", json={**q, "scope": "all"})).json()
        assert got["sources"] and got["sources"][0]["record_id"] == rid

        CALLS.clear()
        follow = {"question": "And where?", "scope": "all", "follow_up": True}
        await admin.post(f"{base}/ask", json=follow)
        assert "Previous question: How many adults" in CALLS[-1]["chat"]
    finally:
        client.set_transport(None)

    # Orçamento esgotado: não chama o modelo
    from sqlalchemy import insert

    from revalli.core.db import SessionLocal
    from revalli.models import AIUsage

    async with SessionLocal() as db:
        await db.execute(
            insert(AIUsage).values(
                id=uuid.uuid4(),
                project_id=uuid.UUID(pid),
                model="x",
                task="screening",
                cost_usd=1.0,
                input_tokens=0,
                output_tokens=0,
            )
        )
        await db.commit()
    r = await admin.post(f"{base}/ask", json={**q, "scope": "all"})
    assert r.status_code == 409 and r.json()["detail"] == "ai_budget_exceeded"


async def test_hybrid_retrieval_with_embeddings(admin):
    pid, (a, b, _) = await _project_included(admin)
    await _setup_ai(admin, pid, embeddings=True)
    await _upload(admin, pid, a, make_pdf("Aerobic", "We randomised 120 adults with anxiety."))
    await _upload(admin, pid, b, make_pdf("Yoga", "Yoga sessions lasted 60 minutes."))
    base = f"/api/projects/{pid}/corpus"
    client.set_transport(httpx.MockTransport(_llm))
    try:
        r = await admin.post(f"{base}/index", json={})
        res = r.json()["result"]
        assert res["embeddings"] == "fake-embed" and res["embedded"] >= 2
        st = (await admin.get(f"{base}/status")).json()
        assert st["embedded"] == st["chunks"] and st["pending_files"] == 0
        # Indexar de novo não repete trabalho
        again = (await admin.post(f"{base}/index", json={})).json()["result"]
        assert again["files"] == 0 and again["embedded"] == 0
        r = await admin.post(f"{base}/ask", json={"question": "How many adults were randomised?"})
    finally:
        client.set_transport(None)
    assert r.status_code == 200 and r.json()["grounded"] is True
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    assert usage["calls"] >= 3  # embeddings dos trechos, da pergunta e a conversa


async def test_removing_a_file_removes_its_chunks(admin):
    pid, (a, _, _) = await _project_included(admin)
    await _setup_ai(admin, pid)
    f = (await _upload(admin, pid, a, make_pdf("Aerobic", "Some text here."))).json()
    base = f"/api/projects/{pid}/corpus"
    await admin.post(f"{base}/index", json={})
    assert (await admin.get(f"{base}/status")).json()["chunks"] > 0
    assert (await admin.delete(f"/api/projects/{pid}/files/{f['id']}")).status_code == 204
    assert (await admin.get(f"{base}/status")).json()["chunks"] == 0


async def test_question_in_another_language_is_expanded(admin):
    pid, (a, _, _) = await _project_included(admin)
    await _setup_ai(admin, pid)
    await _upload(admin, pid, a, make_pdf("Aerobic", "We randomised 120 adults with anxiety."))
    base = f"/api/projects/{pid}/corpus"
    await admin.post(f"{base}/index", json={})
    ask = {"question": "Quantos adultos foram sorteados?"}
    client.set_transport(httpx.MockTransport(_llm))
    try:
        r = await admin.post(f"{base}/ask", json=ask)
    finally:
        client.set_transport(None)
    assert r.status_code == 200, r.text
    assert r.json()["sources"] and r.json()["grounded"] is True
    assert CALLS[-2] == {"expand": ask["question"]}
