import json
from urllib.parse import parse_qs

import httpx
import pytest

from revalli.modules.ai import client as ai_client
from revalli.modules.sources import clients
from tests.test_ai import _configure
from tests.test_extraction import _project_included
from tests.test_fulltext import TITLES
from tests.test_records import _import, _ris


def _work(oa, title, doi=None, refs=(), year=2020, pmid=None):
    return {
        "id": f"https://openalex.org/{oa}",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "ids": {"pmid": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"} if pmid else {},
        "title": title,
        "publication_year": year,
        "authorships": [{"author": {"display_name": "Ana Souza"}}],
        "primary_location": {"source": {"display_name": "J Anxiety"}},
        "biblio": {"volume": "3", "issue": "1", "first_page": "10", "last_page": "19"},
        "abstract_inverted_index": {"Short": [0], "abstract": [1]},
        "referenced_works": [f"https://openalex.org/{r}" for r in refs],
        "type": "article",
    }


WORKS = {
    w["id"].rsplit("/", 1)[1]: w
    for w in [
        _work("W1", TITLES[0][0], TITLES[0][1], refs=["W10", "W11", "W2"]),
        _work("W2", TITLES[1][0], TITLES[1][1], refs=["W11", "W12"]),
        _work("W3", TITLES[2][0], refs=[]),
        _work("W10", "Older trial of running", "10.9999/w10"),
        _work("W11", "Meta-analysis of exercise", "10.9999/w11", pmid="111"),
        _work("W12", "Already imported paper", "10.5555/known"),
        _work("W20", "New trial citing aerobic", "10.9999/w20"),
        _work("W21", "Review citing both", "10.9999/w21"),
    ]
}
CITES = {"W1": ["W20", "W21"], "W2": ["W21"], "W3": []}
CALLS: list[str] = []


def _page(results):
    return httpx.Response(
        200, json={"meta": {"count": len(results), "next_cursor": None}, "results": results}
    )


# Revistas da coleção SciELO Brasil (ArticleMeta) e os trabalhos delas no OpenAlex
SCIELO_ISSNS = {"scl": ["1111-1111", "2222-2222", "3333-3333"], "psi": ["4444-4444"]}
BY_ISSN = {
    "1111-1111": _work("W30", "Ansiedade e exercício em adultos", "10.1590/w30"),
    "2222-2222": _work("W31", "Ansiedade em estudantes", "10.1590/w31"),
    "3333-3333": _work("W32", "Ansiedade e sono", "10.1590/w32"),
    "4444-4444": _work("W33", "Ansiedade no esporte", "10.1590/w33"),
}


def _articlemeta(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    CALLS.append("articlemeta:" + q["collection"])
    issns = SCIELO_ISSNS.get(q["collection"], [])
    start, size = int(q["offset"]), int(q["limit"])
    objects = [{"code": c, "collection": q["collection"]} for c in issns][start : start + size]
    return httpx.Response(200, json={"meta": {"total": len(issns)}, "objects": objects})


def _openalex(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    CALLS.append(q.get("filter") or q.get("search") or "exact:" + q.get("search.exact", ""))
    flt = q.get("filter", "")
    if flt.startswith("primary_location.source.issn:"):
        wanted = flt.split(":", 1)[1].split("|")
        return _page([BY_ISSN[i] for i in wanted if i in BY_ISSN])
    if flt.startswith("openalex:"):
        return _page([WORKS[i] for i in flt[9:].split("|") if i in WORKS])
    if flt.startswith("doi:"):
        wanted = set(flt[4:].split("|"))
        return _page([w for w in WORKS.values() if w["doi"] in wanted])
    if flt.startswith("pmid:"):
        return _page([])
    if flt.startswith("cites:"):
        return _page([WORKS[i] for i in CITES.get(flt[6:], [])])
    search = q.get("search") or q.get("search.exact", "")
    found = [w for w in WORKS.values() if search.lower() in w["title"].lower()]
    if search == "anxiety":
        found = [WORKS["W1"], WORKS["W2"], WORKS["W10"]]
    return _page(found[: int(q.get("per-page", 25))])


PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>{}</PubmedArticleSet>"""
ARTICLE = """<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>
<Journal><JournalIssue><Volume>5</Volume><PubDate><Year>2021</Year></PubDate></JournalIssue>
<Title>Anxiety Journal</Title></Journal><ArticleTitle>{title}</ArticleTitle>
<Abstract><AbstractText>Abstract {pmid}.</AbstractText></Abstract>
<AuthorList><Author><LastName>Lima</LastName><ForeName>Rui</ForeName></Author></AuthorList>
</Article></MedlineCitation></PubmedArticle>"""
PUBMED = [("901", "Pubmed trial one"), ("902", "Pubmed trial two"), ("903", "Pubmed three")]


def _pubmed(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    CALLS.append(request.url.path)
    if request.url.path.endswith("esearch.fcgi"):
        if q["term"] == "bad[[":
            return httpx.Response(200, json={"esearchresult": {"ERROR": "Invalid query"}})
        ids = [p for p, _ in PUBMED][: int(q["retmax"])]
        extra = {}
        if q["term"] == "anxiety zzz":
            extra = {
                "querytranslation": '"anxiety"[All Fields]',
                "warninglist": {"quotedphrasesnotfound": ['"zzz"'], "phrasesignored": []},
                "errorlist": {"phrasesnotfound": [], "fieldsnotfound": ["Nope"]},
            }
        return httpx.Response(
            200,
            json={
                "esearchresult": {
                    "count": str(len(PUBMED)),
                    "idlist": ids,
                    "webenv": "ENV",
                    "querykey": "1",
                    **extra,
                }
            },
        )
    if "id" in q:
        chosen = [p for p in PUBMED if p[0] in q["id"].split(",")]
    else:
        assert q["WebEnv"] == "ENV" and q["query_key"] == "1"
        start, size = int(q["retstart"]), int(q["retmax"])
        chosen = PUBMED[start : start + size]
    body = "".join(ARTICLE.format(pmid=p, title=t) for p, t in chosen)
    return httpx.Response(200, text=PUBMED_XML.format(body))


EPMC = [
    {
        "id": str(i),
        "source": "MED",
        "pmid": str(700 + i),
        "doi": f"10.8888/e{i}",
        "title": f"Europe trial {i}",
        "authorList": {"author": [{"fullName": "Costa A"}]},
        "journalInfo": {"journal": {"title": "EJ"}, "volume": "2", "issue": "4"},
        "pubYear": "2019",
        "pageInfo": "1-9",
        "abstractText": "Text.",
        "pubTypeList": {"pubType": ["research-article"]},
    }
    for i in range(3)
]


def _europepmc(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    CALLS.append(q["cursorMark"])
    start = 0 if q["cursorMark"] == "*" else int(q["cursorMark"])
    size = int(q["pageSize"])
    items = EPMC[start : start + size]
    return httpx.Response(
        200,
        json={
            "hitCount": len(EPMC),
            "nextCursorMark": str(start + size),
            "resultList": {"result": items},
        },
    )


def _router(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if "scielo" in host:
        return _articlemeta(request)
    if "openalex" in host:
        return _openalex(request)
    if "ncbi" in host:
        return _pubmed(request)
    if "ebi" in host:
        return _europepmc(request)
    return httpx.Response(404)


@pytest.fixture(autouse=True)
def fake_apis():
    CALLS.clear()
    clients.set_transport(httpx.MockTransport(_router))
    yield
    clients.set_transport(None)


async def test_snowball_backward_and_forward(admin):
    pid, (a, b, c) = await _project_included(admin)
    # Um registro que já está no projeto não volta como achado
    await _import(admin, pid, "k.ris", content=_ris("Already imported", doi="10.5555/known"))
    info = (await admin.get(f"/api/projects/{pid}/sources/snowball")).json()
    assert info == {"included": 3, "enabled": True}

    r = await admin.post(f"/api/projects/{pid}/sources/snowball", json={"direction": "both"})
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["status"] == "done", job
    res = job["result"]
    assert res["seeds"] == 3 and res["matched"] == 3 and res["not_found"] == []
    assert res["already_in_project"] == 1
    assert [(s["direction"], s["imported"]) for s in res["searches"]] == [
        ("backward", 2),
        ("forward", 2),
    ]
    # A semente sem DOI foi achada pelo título
    assert any(TITLES[2][0][:20] in call for call in CALLS)

    searches = (await admin.get(f"/api/projects/{pid}/searches")).json()
    methods = sorted(s["method"] for s in searches)
    assert methods == ["citation_backward", "citation_forward", "database", "database"]
    back = next(s for s in searches if s["method"] == "citation_backward")
    assert back["source"] == "OpenAlex" and back["file_format"] == "api"
    assert back["searched_on"] is not None

    recs = {
        x["title"]: x for x in (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    }
    meta = recs["Meta-analysis of exercise"]
    assert meta["doi"] == "10.9999/w11" and meta["pmid"] == "111"
    assert meta["abstract"] == "Short abstract" and meta["pages"] == "10-19"
    assert sorted(meta["citation"]["seeds"]) == sorted([a, b])
    assert meta["citation"]["direction"] == "backward"
    assert recs["Review citing both"]["citation"]["seeds"] == [a, b]
    assert "Already imported paper" not in recs

    prisma = (await admin.get(f"/api/projects/{pid}/report/prisma")).json()
    ident = prisma["identification"]
    assert [s["method"] for s in ident["by_source"]] == ["database"]
    assert {(s["method"], s["records"]) for s in ident["other_methods"]} == {
        ("citation_backward", 2),
        ("citation_forward", 2),
    }

    # Uma direção só, a partir de sementes escolhidas
    r = await admin.post(
        f"/api/projects/{pid}/sources/snowball",
        json={"direction": "forward", "record_ids": [a]},
    )
    assert r.json()["result"]["searches"] == [
        {"id": r.json()["result"]["searches"][0]["id"], "direction": "forward", "imported": 0}
    ]


async def test_snowball_needs_seeds_and_lead(admin):
    pid = (await admin.post("/api/projects", json={"title": "Vazio"})).json()["id"]
    r = await admin.post(f"/api/projects/{pid}/sources/snowball", json={})
    assert r.status_code == 409 and r.json()["detail"] == "no_seeds"
    r = await admin.post(
        f"/api/projects/{pid}/sources/snowball",
        json={"record_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert r.status_code == 404


async def test_api_search_preview_and_import(admin):
    pid = (await admin.post("/api/projects", json={"title": "API"})).json()["id"]
    base = f"/api/projects/{pid}/sources"

    r = await admin.post(f"{base}/preview", json={"source": "pubmed", "query": "anxiety"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["count"] == 3 and len(p["sample"]) == 3
    assert p["sample"][0] == {
        "title": "Pubmed trial one",
        "authors": ["Lima, Rui"],
        "year": 2021,
        "journal": "Anxiety Journal",
        "doi": None,
        "pmid": "901",
    }
    assert p["translation"] == "" and p["warnings"] == []
    r = await admin.post(f"{base}/preview", json={"source": "pubmed", "query": "anxiety zzz"})
    p = r.json()
    assert p["translation"] == '"anxiety"[All Fields]'
    assert p["warnings"] == ["Nope", '"zzz"']
    r = await admin.post(f"{base}/preview", json={"source": "pubmed", "query": "bad[["})
    assert r.status_code == 502 and r.json()["detail"].startswith("source_unavailable: ")

    r = await admin.post(f"{base}/search", json={"source": "pubmed", "query": "anxiety"})
    assert r.status_code == 202, r.text
    res = r.json()["result"]
    assert res["source"] == "PubMed" and res["imported"] == 3 and res["truncated"] is False

    r = await admin.post(f"{base}/search", json={"source": "europepmc", "query": "x", "limit": 2})
    res = r.json()["result"]
    assert res["found"] == 3 and res["imported"] == 2 and res["truncated"] is True

    r = await admin.post(f"{base}/search", json={"source": "openalex", "query": "anxiety"})
    assert r.json()["result"]["imported"] == 3

    searches = {s["source"]: s for s in (await admin.get(f"/api/projects/{pid}/searches")).json()}
    epmc = searches["Europe PMC"]
    assert epmc["query"] == "x" and epmc["reported_count"] == 3 and epmc["imported_count"] == 2
    assert epmc["method"] == "database" and epmc["file_format"] == "api"
    recs = {
        x["title"]: x for x in (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    }
    assert recs["Europe trial 1"]["doi"] == "10.8888/e1"
    assert recs["Europe trial 1"]["authors"] == ["Costa A"]
    assert recs["Pubmed trial two"]["abstract"] == "Abstract 902."
    # O OpenAlex trouxe de novo dois trabalhos que outras bases não tinham; a deduplicação roda
    jobs = (await admin.get(f"/api/projects/{pid}/jobs")).json()
    assert {j["kind"] for j in jobs} == {"api_search"}

    r = await admin.post(f"{base}/search", json={"source": "scopus", "query": "x"})
    assert r.status_code == 422


async def test_search_apis_can_be_disabled(admin, monkeypatch):
    from revalli.core.config import get_settings

    pid = (await admin.post("/api/projects", json={"title": "API"})).json()["id"]
    monkeypatch.setattr(get_settings(), "search_apis_enabled", False)
    r = await admin.post(
        f"/api/projects/{pid}/sources/preview", json={"source": "pubmed", "query": "x"}
    )
    assert r.status_code == 409 and r.json()["detail"] == "search_apis_disabled"


def _translator(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert "Scopus" in body["messages"][1]["content"]
    content = json.dumps(
        {"query": 'TITLE-ABS-KEY("exercise" AND anxi*)', "notes": ["Check truncation."]}
    )
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        },
    )


async def test_translate_query(admin):
    pid = (await admin.post("/api/projects", json={"title": "Tradução"})).json()["id"]
    url = f"/api/projects/{pid}/sources/translate"
    body = {"query": '"exercise"[mh] AND anxi*[tiab]', "target": "scopus"}
    assert (await admin.post(url, json=body)).json()["detail"] == "ai_disabled"
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    r = await admin.post(url, json=body)
    assert r.status_code == 409 and r.json()["detail"] == "ai_not_configured"
    await _configure(admin)
    ai_client.set_transport(httpx.MockTransport(_translator))
    try:
        r = await admin.post(url, json=body)
    finally:
        ai_client.set_transport(None)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "query": 'TITLE-ABS-KEY("exercise" AND anxi*)',
        "notes": ["Check truncation."],
        "model": "fake-8b",
    }
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    assert usage["calls"] == 1 and usage["input_tokens"] == 100


@pytest.mark.parametrize(
    "target,marker",
    [("scielo", "SciELO (searched through OpenAlex"), ("capes", "CAPES"), ("pepsic", "PePSIC")],
)
async def test_translate_query_to_brazilian_bases(admin, target, marker):
    pid = (await admin.post("/api/projects", json={"title": "Tradução"})).json()["id"]
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    await _configure(admin)
    sent = []

    def spy(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["messages"][-1]["content"])
        content = json.dumps({"query": "exercicio AND ansiedade", "notes": []})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    ai_client.set_transport(httpx.MockTransport(spy))
    try:
        r = await admin.post(
            f"/api/projects/{pid}/sources/translate",
            json={"query": "exercise AND anxiety", "target": target},
        )
    finally:
        ai_client.set_transport(None)
    assert r.status_code == 200, r.text
    assert marker in sent[0] and "Portuguese and Spanish" in sent[0]


async def test_translate_rejects_unknown_target(admin):
    pid = (await admin.post("/api/projects", json={"title": "Tradução"})).json()["id"]
    r = await admin.post(
        f"/api/projects/{pid}/sources/translate", json={"query": "x", "target": "google"}
    )
    assert r.status_code == 422


async def test_scielo_and_pepsic_search_openalex_restricted_to_collection_journals(
    admin, monkeypatch
):
    monkeypatch.setattr(clients, "ISSN_CHUNK", 2)
    clients._collections.clear()
    pid = (await admin.post("/api/projects", json={"title": "SciELO"})).json()["id"]
    base = f"/api/projects/{pid}/sources"

    r = await admin.post(f"{base}/preview", json={"source": "scielo", "query": "ansiedade"})
    assert r.status_code == 200, r.text
    p = r.json()
    # 3 revistas em lotes de 2: a contagem soma os dois lotes
    assert p["count"] == 3 and len(p["sample"]) == 3
    assert CALLS.count("articlemeta:scl") == 1
    issn_calls = [c for c in CALLS if c.startswith("primary_location.source.issn:")]
    assert issn_calls == [
        "primary_location.source.issn:1111-1111|2222-2222",
        "primary_location.source.issn:3333-3333",
    ]

    r = await admin.post(f"{base}/search", json={"source": "scielo", "query": "ansiedade"})
    res = r.json()["result"]
    assert res["source"] == "SciELO (via OpenAlex)" and res["found"] == 3 and res["imported"] == 3
    # A lista de revistas ficou em cache: o ArticleMeta não é consultado de novo
    assert CALLS.count("articlemeta:scl") == 1

    r = await admin.post(f"{base}/search", json={"source": "pepsic", "query": "ansiedade"})
    res = r.json()["result"]
    assert res["source"] == "PePSIC (via OpenAlex)" and res["imported"] == 1
    assert CALLS.count("articlemeta:psi") == 1

    r = await admin.post(f"{base}/search", json={"source": "scielo", "query": "x", "limit": 2})
    assert r.json()["result"]["imported"] == 2 and r.json()["result"]["truncated"] is True


async def test_wildcard_queries_use_openalex_exact_search(admin):
    pid = (await admin.post("/api/projects", json={"title": "Curinga"})).json()["id"]
    url = f"/api/projects/{pid}/sources/preview"
    seen: list[dict] = []

    def spy(request: httpx.Request) -> httpx.Response:
        if "openalex" in request.url.host:
            seen.append(dict(request.url.params))
        return _router(request)

    clients.set_transport(httpx.MockTransport(spy))
    for source in ("openalex", "scielo", "pepsic"):
        seen.clear()
        r = await admin.post(url, json={"source": source, "query": "anxi* AND sono"})
        assert r.status_code == 200, r.text
        assert seen and all(
            p.get("search.exact") == "anxi* AND sono" and "search" not in p for p in seen
        )
    seen.clear()
    await admin.post(url, json={"source": "openalex", "query": "anxiety AND sono"})
    assert seen[0].get("search") == "anxiety AND sono" and "search.exact" not in seen[0]


async def test_rate_limited_source_is_retried_then_reported(admin):
    pid = (await admin.post("/api/projects", json={"title": "Calma"})).json()["id"]
    url = f"/api/projects/{pid}/sources/preview"
    body = {"source": "openalex", "query": "anxiety"}
    state = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, json={"error": "Rate limit exceeded"})
        return _router(request)

    clients.set_transport(httpx.MockTransport(flaky))
    r = await admin.post(url, json=body)
    assert r.status_code == 200 and r.json()["count"] == 3 and state["n"] == 2

    clients.set_transport(
        httpx.MockTransport(lambda req: httpx.Response(429, json={"error": "Rate limit"}))
    )
    r = await admin.post(url, json=body)
    # Depois de várias tentativas, o motivo chega à tela
    assert r.status_code == 502 and "http 429" in r.json()["detail"]


def _assistant(sent: list):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body["messages"])
        content = json.dumps(
            {
                "reply": "Entendi: efeitos iatrogênicos de falar sobre bullying. Qual faixa etária?",
                "strategies": [
                    {
                        "base": "pubmed",
                        "query": '(bullying OR cyberbullying) AND (iatrogeni* OR "adverse effect*")',
                        "notes": ["Truncamento com *"],
                    },
                    {"base": "SciELO", "query": '(bullying OR "assédio escolar") AND iatrogeni*'},
                    {"base": "pubmed", "query": "duplicada"},
                    {"base": "google", "query": "base desconhecida"},
                    {"base": "scopus", "query": ""},
                ],
            }
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 300, "completion_tokens": 80},
            },
        )

    return handler


async def test_search_assistant_proposes_one_strategy_per_known_base(admin):
    pid = (await admin.post("/api/projects", json={"title": "Bullying"})).json()["id"]
    url = f"/api/projects/{pid}/sources/assist"
    chat = {"messages": [{"role": "user", "content": "Efeitos iatrogênicos de falar de bullying"}]}
    assert (await admin.post(url, json=chat)).json()["detail"] == "ai_disabled"
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    await _configure(admin)
    sent: list = []
    ai_client.set_transport(httpx.MockTransport(_assistant(sent)))
    try:
        r = await admin.post(url, json=chat)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["reply"].startswith("Entendi")
        # Base desconhecida, repetida ou sem texto não passam; o nome da base é normalizado
        assert [s["base"] for s in out["strategies"]] == ["pubmed", "scielo"]
        assert out["strategies"][0]["notes"] == ["Truncamento com *"]
        system = sent[0][0]["content"]
        assert "Review title: Bullying" in system and "scielo:" in system and "pubmed:" in system
        # A conversa inteira vai para o modelo, na ordem
        follow = {
            "messages": [
                *chat["messages"],
                {"role": "assistant", "content": out["reply"]},
                {"role": "user", "content": "Adolescentes, 10 a 19 anos"},
            ]
        }
        assert (await admin.post(url, json=follow)).status_code == 200
        assert [m["role"] for m in sent[1]] == ["system", "user", "assistant", "user"]
        # A conversa precisa terminar numa fala da pessoa
        bad = {"messages": [{"role": "assistant", "content": "oi"}]}
        assert (await admin.post(url, json=bad)).status_code == 422
    finally:
        ai_client.set_transport(None)
    usage = (await admin.get(f"/api/projects/{pid}/ai/usage")).json()
    assert usage["calls"] == 2


HEAVY = "(a OR b OR c) AND (d OR e OR f) AND (g OR h OR i)"


async def test_heavy_openalex_queries_are_spaced_out(monkeypatch):
    from revalli.core.config import get_settings

    assert clients.is_heavy({"search": HEAVY}) and not clients.is_heavy({"search": "a AND b"})
    assert clients.is_heavy({"search.exact": HEAVY}) and not clients.is_heavy({})
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(get_settings(), "api_delay_seconds", 0.35)
    monkeypatch.setattr(clients.asyncio, "sleep", fake_sleep)
    clients._next_heavy.clear()
    url = "https://api.openalex.org/works"
    await clients.throttle(url, {"search": HEAVY})
    assert sleeps == []  # a primeira consulta passa direto
    await clients.throttle(url, {"search": HEAVY})
    assert len(sleeps) == 1 and 0.5 < sleeps[0] <= clients.HEAVY_INTERVAL
    # Consulta leve não espera nem ocupa a fila
    await clients.throttle(url, {"search": "a AND b"})
    assert len(sleeps) == 1
    clients._next_heavy.clear()


async def test_retry_waits_for_the_time_the_server_asks(monkeypatch):
    from revalli.core.config import get_settings

    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(get_settings(), "api_delay_seconds", 0.35)
    monkeypatch.setattr(clients.asyncio, "sleep", fake_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": "Rate limit", "retryAfter": 2})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        r = await clients.get(c, "https://api.example.org/x", {})
    assert r.status_code == 200 and calls["n"] == 3
    # Respeita o retryAfter do corpo e espera um pouco mais a cada tentativa
    assert waits == [2.0, 4.0]


def test_quoted_phrases_with_wildcards_are_rewritten_for_openalex():
    q = '(bullying OR "assédio escolar") AND ("efeito* adverso*" OR "iatrogeni*" OR "adverse effect")'
    assert clients.adapt_query(q) == (
        '(bullying OR "assédio escolar") AND ((efeito* AND adverso*) OR iatrogeni* '
        'OR "adverse effect")'
    )
    assert clients.adapt_query("plain words") == "plain words"
    assert clients.search_param('"efeito* adverso*"') == {"search.exact": "(efeito* AND adverso*)"}


async def test_preview_reports_the_adapted_query(admin):
    pid = (await admin.post("/api/projects", json={"title": "Aspas"})).json()["id"]
    url = f"/api/projects/{pid}/sources/preview"
    r = await admin.post(url, json={"source": "scielo", "query": '"efeito* adverso*" AND anxi'})
    assert r.status_code == 200, r.text
    assert r.json()["translation"] == "(efeito* AND adverso*) AND anxi"
    r = await admin.post(url, json={"source": "openalex", "query": "anxiety"})
    assert r.json()["translation"] == ""


async def test_exhausted_daily_budget_fails_fast_with_a_clear_code(admin):
    pid = (await admin.post("/api/projects", json={"title": "Orçamento"})).json()["id"]
    calls = {"n": 0}

    def broke(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = {
            "error": "Rate limit exceeded",
            "message": "Insufficient budget",
            "retryAfter": 81005,
        }
        return httpx.Response(429, json=body)

    clients.set_transport(httpx.MockTransport(broke))
    r = await admin.post(
        f"/api/projects/{pid}/sources/preview", json={"source": "openalex", "query": "anxiety"}
    )
    # Uma tentativa só: esperar 22 horas não faz sentido
    assert calls["n"] == 1
    assert r.status_code == 502 and r.json()["detail"].startswith("openalex_key_needed: ")
