"""Bases além da psicologia (ERIC, ClinicalTrials.gov, preprints, arXiv) e a escolha por projeto."""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from revalli.modules.ai import client as ai_client
from revalli.modules.sources import catalog, clients, fields
from tests.test_ai import _configure
from tests.test_sources import _router

SEEN: list[dict] = []

ERIC_DOCS = [
    {
        "id": f"EJ{i}",
        "title": f"Math anxiety &amp; school {i}",
        "author": ["Greenwood, Jay"],
        "description": "Students &quot;fear&quot; math.",
        "subject": ["Mathematics Anxiety", "Teaching Methods"],
        "publicationtype": ["Journal Articles", "Reports - Research"],
        "publicationdateyear": 2020 + i,
        "language": ["English"],
        "source": "Journal of Education",
    }
    for i in range(3)
]


def _eric(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    SEEN.append(q)
    start, rows = int(q["start"]), int(q["rows"])
    docs = ERIC_DOCS[start : start + rows]
    return httpx.Response(200, json={"response": {"numFound": len(ERIC_DOCS), "docs": docs}})


def _study(n: int) -> dict:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": f"NCT0000000{n}",
                "briefTitle": f"Exercise for anxiety {n}",
            },
            "statusModule": {"startDateStruct": {"date": f"2019-0{n + 1}"}},
            "descriptionModule": {"briefSummary": "Tests exercise."},
            "conditionsModule": {"conditions": ["Anxiety"], "keywords": ["Exercise"]},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Universidade X"}},
            "designModule": {"studyType": "INTERVENTIONAL"},
        }
    }


STUDIES = [_study(i) for i in range(3)]


def _clinicaltrials(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    SEEN.append(q)
    start = int(q.get("pageToken") or 0)
    size = int(q["pageSize"])
    chunk = STUDIES[start : start + size]
    body: dict = {"studies": chunk, "totalCount": len(STUDIES)}
    if start + size < len(STUDIES):
        body["nextPageToken"] = str(start + size)
    return httpx.Response(200, json=body)


ATOM = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns="http://www.w3.org/2005/Atom">
  <opensearch:totalResults>{total}</opensearch:totalResults>
  {entries}
</feed>"""
ENTRY = """<entry>
  <id>http://arxiv.org/abs/2101.0000{n}v1</id>
  <title>Deep   learning
    for anxiety {n}</title>
  <summary>  A short abstract {n}. </summary>
  <published>2021-01-0{n}T10:00:00Z</published>
  <author><name>Ana Souza</name></author><author><name>Rui Lima</name></author>
  <arxiv:doi>10.1000/arxiv.{n}</arxiv:doi>
  <link href="https://arxiv.org/abs/2101.0000{n}v1" rel="alternate" type="text/html"/>
  <category term="cs.LG"/>
</entry>"""


def _arxiv(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    SEEN.append(q)
    if "bad" in q["search_query"]:
        entry = (
            "<entry><id>http://arxiv.org/api/errors#x</id><title>Error</title>"
            "<summary>incorrect id format</summary></entry>"
        )
        return httpx.Response(200, text=ATOM.format(total=1, entries=entry))
    start, size = int(q["start"]), int(q["max_results"])
    chosen = list(range(1, 4))[start : start + size]
    entries = "".join(ENTRY.format(n=n) for n in chosen)
    return httpx.Response(200, text=ATOM.format(total=3, entries=entries))


DOAJ_ITEMS = [
    {
        "id": f"d{i}",
        "bibjson": {
            "title": f"Open access anxiety {i}",
            "abstract": "Abstract text.",
            "year": "2021",
            "author": [{"name": "Ana Souza"}, {"name": "Rui Lima"}],
            "journal": {"title": "Open Journal", "volume": "4", "number": "2", "language": ["EN"]},
            "identifier": [{"type": "doi", "id": f"10.7777/d{i}"}, {"type": "eissn", "id": "1-1"}],
            "keywords": ["anxiety"],
            "start_page": "10",
            "end_page": "19",
            "link": [{"type": "fulltext", "url": f"https://example.org/d{i}"}],
        },
    }
    for i in range(3)
]


def _doaj(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    SEEN.append({**q, "path": request.url.path})
    if "bad" in request.url.path:
        return httpx.Response(400, json={"error": "Query contains disallowed Lucene features"})
    page, size = int(q["page"]), int(q["pageSize"])
    items = DOAJ_ITEMS[(page - 1) * size : page * size]
    return httpx.Response(200, json={"total": len(DOAJ_ITEMS), "results": items})


OPENAIRE_ITEMS = [
    {
        "id": f"o{i}",
        "mainTitle": f"Thesis on anxiety {i}",
        "descriptions": ["A thesis abstract."],
        "publicationDate": "2020-05-01",
        "authors": [{"fullName": "Costa, Ana"}],
        "pids": [{"scheme": "doi", "value": f"10.6666/o{i}"}, {"scheme": "pmid", "value": "123"}],
        "container": {"name": "Repository Journal", "vol": "3", "sp": "1", "ep": "9"},
        "subjects": [{"subject": {"scheme": "keyword", "value": "anxiety"}}],
        "type": "publication",
    }
    for i in range(3)
]


def _openaire(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    SEEN.append(q)
    start = 0 if q["cursor"] == "*" else int(q["cursor"])
    size = int(q["pageSize"])
    header = {"numFound": len(OPENAIRE_ITEMS)}
    if start + size < len(OPENAIRE_ITEMS):
        header["nextCursor"] = str(start + size)
    return httpx.Response(
        200, json={"header": header, "results": OPENAIRE_ITEMS[start : start + size]}
    )


S2_PAPERS = [
    {
        "paperId": f"p{i}",
        "title": f"Learning to treat anxiety {i}",
        "abstract": "Abstract.",
        "year": 2022,
        "authors": [{"authorId": "1", "name": "Ana Souza"}],
        "venue": "NeurIPS",
        "externalIds": {"DOI": f"10.5555/s{i}", "PubMed": "777"},
        "url": f"https://www.semanticscholar.org/paper/p{i}",
        "publicationTypes": ["JournalArticle", "Review"],
        "fieldsOfStudy": ["Psychology"],
    }
    for i in range(3)
]
S2_HEADERS: list[str | None] = []


def _semanticscholar(request: httpx.Request) -> httpx.Response:
    q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
    SEEN.append(q)
    S2_HEADERS.append(request.headers.get("x-api-key"))
    if "nokey" in q["query"] and not request.headers.get("x-api-key"):
        return httpx.Response(429, json={"message": "Too Many Requests"})
    first = "token" not in q
    body: dict = {"total": len(S2_PAPERS), "data": S2_PAPERS[:2] if first else S2_PAPERS[2:]}
    if first:
        body["token"] = "next"
    return httpx.Response(200, json=body)


def _hosts(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if "doaj" in host:
        return _doaj(request)
    if "openaire" in host:
        return _openaire(request)
    if "semanticscholar" in host:
        return _semanticscholar(request)
    if "ies.ed.gov" in host:
        return _eric(request)
    if "clinicaltrials" in host:
        return _clinicaltrials(request)
    if "arxiv" in host:
        return _arxiv(request)
    return _router(request)


@pytest.fixture(autouse=True)
def fake_apis():
    SEEN.clear()
    S2_HEADERS.clear()
    clients.set_transport(httpx.MockTransport(_hosts))
    yield
    clients.set_transport(None)


async def _project(admin) -> str:
    return (await admin.post("/api/projects", json={"title": "Bases"})).json()["id"]


async def test_eric_search_maps_records_and_keeps_the_strategy(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/sources"
    rows = [
        {"term": '"math anxiety"', "field": "title_abstract"},
        {"term": "2018-2022", "field": "year", "op": "AND"},
    ]
    r = await admin.post(f"{base}/preview", json={"source": "eric", "rows": rows})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["count"] == 3
    assert out["strategy"] == (
        '(title:"math anxiety" OR description:"math anxiety") AND publicationdateyear:[2018 TO 2022]'
    )
    assert out["sample"][0]["title"] == "Math anxiety & school 0"
    assert out["sample"][0]["journal"] == "Journal of Education"

    r = await admin.post(f"{base}/search", json={"source": "eric", "rows": rows, "limit": 2})
    assert r.status_code == 202, r.text
    res = r.json()["result"]
    assert res["source"] == "ERIC" and res["imported"] == 2 and res["truncated"] is True
    recs = (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    first = next(x for x in recs if x["title"] == "Math anxiety & school 0")
    assert first["abstract"] == 'Students "fear" math.'
    assert first["year"] == 2020 and "Mathematics Anxiety" in first["keywords"]
    assert first["url"] == "https://eric.ed.gov/?id=EJ0"
    assert first["publication_type"] == "Journal Articles; Reports - Research"


async def test_clinicaltrials_search_pages_and_maps_registry_records(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/sources"
    rows = [
        {"term": "anxiety", "field": "condition"},
        {"term": "exercise", "field": "intervention"},
    ]
    r = await admin.post(f"{base}/search", json={"source": "clinicaltrials", "rows": rows})
    assert r.status_code == 202, r.text
    res = r.json()["result"]
    assert res["source"] == "ClinicalTrials.gov" and res["imported"] == 3 and res["found"] == 3
    assert SEEN[0]["query.term"] == ("AREA[Condition]anxiety AND AREA[InterventionName]exercise")
    assert SEEN[0]["countTotal"] == "true"
    recs = (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    rec = next(x for x in recs if x["title"] == "Exercise for anxiety 1")
    assert rec["year"] == 2019 and rec["journal"] == "ClinicalTrials.gov"
    assert rec["url"] == "https://clinicaltrials.gov/study/NCT00000001"
    assert rec["keywords"] == ["Anxiety", "Exercise"]
    assert rec["authors"] == ["Universidade X"]
    assert rec["publication_type"] == "Trial registry (INTERVENTIONAL)"


async def test_clinicaltrials_native_expression_is_sent_untouched(admin):
    pid = await _project(admin)
    query = "AREA[Condition](anxiety OR depression) AND AREA[StudyType]INTERVENTIONAL"
    r = await admin.post(
        f"/api/projects/{pid}/sources/preview", json={"source": "clinicaltrials", "query": query}
    )
    assert r.status_code == 200, r.text
    assert SEEN[0]["query.term"] == query and r.json()["corrections"] == []


async def test_arxiv_search_reads_atom_and_reports_errors(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/sources"
    r = await admin.post(
        f"{base}/preview",
        json={
            "source": "arxiv",
            "rows": [
                {"term": '"deep learning"', "field": "title"},
                {"term": "children", "field": "abstract", "op": "NOT"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["strategy"] == 'ti:"deep learning" ANDNOT abs:children'
    assert out["count"] == 3 and out["sample"][0]["title"] == "Deep learning for anxiety 1"
    assert out["sample"][0]["authors"] == ["Ana Souza", "Rui Lima"]
    assert out["sample"][0]["doi"] == "10.1000/arxiv.1" and out["sample"][0]["year"] == 2021

    r = await admin.post(f"{base}/search", json={"source": "arxiv", "query": "ti:anxiety"})
    assert r.status_code == 202, r.text
    assert r.json()["result"]["imported"] == 3
    # Termos soltos vão para `all:`, que é o que o arXiv entende
    r = await admin.post(f"{base}/preview", json={"source": "arxiv", "query": "anxiety NOT kids"})
    assert r.json()["strategy"] == "all:anxiety ANDNOT all:kids"

    r = await admin.post(f"{base}/preview", json={"source": "arxiv", "query": "bad"})
    assert r.status_code == 502 and "incorrect id format" in r.json()["detail"]


async def test_preprints_are_europe_pmc_restricted_to_the_preprint_source(admin):
    pid = await _project(admin)
    seen: list[dict] = []

    def spy(request: httpx.Request) -> httpx.Response:
        if "ebi" in request.url.host:
            seen.append({k: v[0] for k, v in parse_qs(request.url.query.decode()).items()})
        return _hosts(request)

    clients.set_transport(httpx.MockTransport(spy))
    r = await admin.post(
        f"/api/projects/{pid}/sources/search",
        json={"source": "preprints", "rows": [{"term": "anxiety", "field": "title"}]},
    )
    assert r.status_code == 202, r.text
    assert seen[0]["query"] == "(TITLE:anxiety) AND SRC:PPR"
    assert r.json()["result"]["source"] == "Preprints (Europe PMC)"
    searches = (await admin.get(f"/api/projects/{pid}/searches")).json()
    assert searches[0]["query"] == "(TITLE:anxiety) AND SRC:PPR"


def test_new_bases_compile_rows_and_text():
    rows = [
        fields.Row("anxiety OR stress", "title_abstract"),
        fields.Row("children", "keyword"),
        fields.Row("adults", "title", "NOT"),
    ]
    assert fields.compile_strategy("eric", rows=rows).native == (
        "(((title:anxiety OR description:anxiety) OR (title:stress OR description:stress)) "
        "AND subject:children) NOT title:adults"
    )
    ct = fields.compile_strategy("clinicaltrials", rows=rows).native
    assert ct.endswith("AND NOT (AREA[BriefTitle]adults OR AREA[OfficialTitle]adults)")
    assert "AREA[Keyword]children" in ct
    assert fields.compile_strategy(
        "clinicaltrials", rows=[fields.Row("2018-2022", "year")]
    ).native == ("AREA[StartDate]RANGE[2018-01-01,2022-12-31]")
    # Siglas nativas da base não são correção
    assert fields.compile_strategy("eric", "title:anxiety AND subject:children").corrections == []
    assert fields.compile_strategy("arxiv", "ti:anxiety AND abs:kids").corrections == []
    # Siglas de outras bases são trocadas, como nas demais
    assert fields.compile_strategy("eric", "ti:anxiety").corrections == ["field_tags_converted: ti"]


def test_catalog_covers_every_source_and_target():
    from revalli.modules.sources.schemas import SourceName

    direct = {d.id for d in catalog.DATABASES if d.direct}
    assert direct == set(clients.SOURCES) == set(SourceName.__args__)
    assert set(catalog.IDS) == set(fields.BY_SOURCE) | {
        d.id for d in catalog.DATABASES if not d.direct
    }
    assert all(set(ids) <= set(catalog.IDS) for ids in catalog.PACKS.values())
    assert set(catalog.DEFAULT_ENABLED) <= set(catalog.IDS)


async def test_databases_default_save_and_validation(admin):
    pid = await _project(admin)
    url = f"/api/projects/{pid}/sources/databases"
    r = await admin.get(url)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["saved"] is False and out["enabled"] == list(catalog.DEFAULT_ENABLED)
    assert {c["id"]: c["direct"] for c in out["catalog"]}["eric"] is True
    assert {c["id"]: c["direct"] for c in out["catalog"]}["ieee"] is False
    assert set(out["packs"]) == set(catalog.PACKS)

    r = await admin.put(url, json={"enabled": ["scielo", "eric", "pubmed", "eric"]})
    assert r.status_code == 200, r.text
    # Na ordem do catálogo, sem repetição
    assert r.json()["enabled"] == ["pubmed", "eric", "scielo"] and r.json()["saved"] is True
    assert (await admin.get(url)).json()["enabled"] == ["pubmed", "eric", "scielo"]

    assert (await admin.put(url, json={"enabled": []})).status_code == 422
    assert (await admin.put(url, json={"enabled": ["google"]})).status_code == 422

    # Salvar o protocolo da triagem não apaga a escolha das bases
    r = await admin.get(f"/api/projects/{pid}/screening/settings")
    assert r.status_code == 200, r.text
    assert (
        await admin.put(f"/api/projects/{pid}/screening/settings", json=r.json())
    ).status_code == 200
    assert (await admin.get(url)).json()["enabled"] == ["pubmed", "eric", "scielo"]


async def test_search_assistant_only_proposes_the_selected_bases(admin):
    pid = await _project(admin)
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    await _configure(admin)
    await admin.put(f"/api/projects/{pid}/sources/databases", json={"enabled": ["eric", "arxiv"]})
    sent: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["messages"])
        content = json.dumps(
            {
                "reply": "Entendi.",
                "strategies": [
                    {"base": "eric", "query": "title:anxiety"},
                    {"base": "pubmed", "query": "anxiety[tiab]"},
                    {"base": "arxiv", "query": "ti:anxiety"},
                ],
            }
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    ai_client.set_transport(httpx.MockTransport(handler))
    try:
        r = await admin.post(
            f"/api/projects/{pid}/sources/assist",
            json={"messages": [{"role": "user", "content": "ansiedade matemática"}]},
        )
    finally:
        ai_client.set_transport(None)
    assert r.status_code == 200, r.text
    # O PubMed não foi escolhido: a proposta dele é descartada e nem entra no prompt
    assert [s["base"] for s in r.json()["strategies"]] == ["eric", "arxiv"]
    system = sent[0][0]["content"]
    assert "- eric:" in system and "- arxiv:" in system and "- pubmed:" not in system


@pytest.mark.parametrize(
    "target,marker",
    [
        ("eric", "ERIC"),
        ("clinicaltrials", "AREA[Condition]"),
        ("preprints", "SRC:PPR"),
        ("ieee", "IEEE Xplore"),
        ("econlit", "EconLit"),
    ],
)
async def test_translate_query_to_new_bases(admin, target, marker):
    pid = await _project(admin)
    await admin.put(f"/api/projects/{pid}/ai/settings", json={"enabled": True})
    await _configure(admin)
    sent = []

    def spy(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["messages"][-1]["content"])
        content = json.dumps({"query": "anxiety", "notes": []})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    ai_client.set_transport(httpx.MockTransport(spy))
    try:
        r = await admin.post(
            f"/api/projects/{pid}/sources/translate", json={"query": "anxiety", "target": target}
        )
    finally:
        ai_client.set_transport(None)
    assert r.status_code == 200, r.text
    assert marker in sent[0]


async def test_doaj_search_sends_lucene_in_the_path_and_drops_wildcards(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/sources"
    rows = [
        {"term": "anxi*", "field": "title"},
        {"term": "children", "field": "keyword", "op": "AND"},
        {"term": "adults", "field": "title", "op": "NOT"},
    ]
    r = await admin.post(f"{base}/preview", json={"source": "doaj", "rows": rows})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["strategy"] == (
        "(bibjson.title:anxi AND bibjson.keywords:children) AND NOT bibjson.title:adults"
    )
    assert out["corrections"] == ["truncation_removed"]
    assert out["count"] == 3 and out["sample"][0]["doi"] == "10.7777/d0"
    assert "bibjson.title%3Aanxi" in SEEN[0]["path"] or "bibjson.title:anxi" in SEEN[0]["path"]

    r = await admin.post(f"{base}/search", json={"source": "doaj", "rows": rows, "limit": 2})
    assert r.status_code == 202, r.text
    assert r.json()["result"]["imported"] == 2 and r.json()["result"]["truncated"] is True
    recs = (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    rec = recs[0]
    assert rec["journal"] == "Open Journal" and rec["year"] == 2021 and rec["pages"] == "10-19"
    assert rec["url"].startswith("https://example.org/d")

    r = await admin.post(f"{base}/preview", json={"source": "doaj", "query": "bad"})
    assert r.status_code == 502


async def test_openaire_search_sends_one_parameter_per_field(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/sources"
    rows = [
        {"term": "anxiety", "field": "title"},
        {"term": "children OR adolescents", "field": "abstract"},
        {"term": "2018-2023", "field": "year"},
    ]
    r = await admin.post(f"{base}/search", json={"source": "openaire", "rows": rows})
    assert r.status_code == 202, r.text
    res = r.json()["result"]
    assert res["source"] == "OpenAIRE" and res["imported"] == 3 and res["found"] == 3
    q = SEEN[0]
    assert q["type"] == "publication" and q["mainTitle"] == "anxiety"
    assert q["description"] == "(children OR adolescents)"
    assert q["fromPublicationDate"] == "2018-01-01" and q["toPublicationDate"] == "2023-12-31"
    recs = (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    first = next(x for x in recs if x["title"] == "Thesis on anxiety 0")
    assert first["doi"] == "10.6666/o0" and first["pmid"] == "123" and first["year"] == 2020
    assert first["abstract"] == "A thesis abstract." and first["keywords"] == ["anxiety"]
    searches = (await admin.get(f"/api/projects/{pid}/searches")).json()
    assert searches[0]["query"].startswith("mainTitle=anxiety AND description=(children OR")

    # Texto livre vai inteiro para a busca em todos os metadados
    r = await admin.post(
        f"{base}/preview", json={"source": "openaire", "query": "anxiety AND child*"}
    )
    assert r.status_code == 200, r.text
    assert SEEN[-1]["search"] == "anxiety AND child"
    assert r.json()["corrections"] == ["truncation_removed"]


async def test_semanticscholar_pages_with_token_and_reports_a_missing_key(admin, monkeypatch):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/sources"
    rows = [
        {"term": "anxiety OR stress", "field": "title_abstract"},
        {"term": "treatment", "field": "title_abstract"},
        {"term": "2015-2022", "field": "year"},
        {"term": "Review", "field": "type"},
    ]
    r = await admin.post(f"{base}/preview", json={"source": "semanticscholar", "rows": rows})
    assert r.status_code == 200, r.text
    out = r.json()
    assert SEEN[0]["query"] == "(anxiety | stress) + treatment"
    assert SEEN[0]["year"] == "2015-2022" and SEEN[0]["publicationTypes"] == "Review"
    assert out["count"] == 3 and out["sample"][0]["doi"] == "10.5555/s0"

    r = await admin.post(f"{base}/search", json={"source": "semanticscholar", "rows": rows})
    assert r.status_code == 202, r.text
    assert r.json()["result"]["imported"] == 3
    assert any("token" in q for q in SEEN)
    recs = (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    assert {x["journal"] for x in recs} == {"NeurIPS"}

    # Sem chave, o 429 vira um aviso que diz o que fazer; com chave, ela vai no cabeçalho
    r = await admin.post(f"{base}/preview", json={"source": "semanticscholar", "query": "nokey"})
    assert r.status_code == 502 and r.json()["detail"].startswith("semantic_scholar_key_needed")
    assert S2_HEADERS[-1] is None
    from revalli.core.config import get_settings

    monkeypatch.setattr(get_settings(), "semantic_scholar_api_key", "abc123")
    r = await admin.post(f"{base}/preview", json={"source": "semanticscholar", "query": "nokey"})
    assert r.status_code == 200, r.text
    assert S2_HEADERS[-1] == "abc123"


def test_lote_two_bases_compile_text_and_rows():
    assert fields.compile_strategy(
        "semanticscholar", 'anxiety AND ("young people" OR child*) NOT adults'
    ).native == ('anxiety + ("young people" | child*) -adults')
    assert fields.compile_strategy("doaj", "anxiety NOT adults").native == (
        "anxiety AND NOT adults"
    )
    assert (
        fields.compile_strategy(
            "doaj", rows=[fields.Row("2019", "year"), fields.Row("pt", "language")]
        ).native
        == "bibjson.year:2019 AND bibjson.journal.language:PT"
    )
    # OR entre campos não existe no OpenAIRE; NOT sem campo anterior é avisado
    c = fields.compile_strategy(
        "openaire",
        rows=[
            fields.Row("a", "title"),
            fields.Row("b", "abstract", "OR"),
            fields.Row("c", "author", "NOT"),
        ],
    )
    assert c.native == "mainTitle=a AND description=b"
    assert c.corrections == ["or_across_fields: abstract", "not_across_fields: author"]
    assert not fields.mixes_fields_with_or("openaire")
    assert not fields.mixes_fields_with_or("semanticscholar")
