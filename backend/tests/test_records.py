from pathlib import Path

import httpx

from revalli.modules.records import enrich as enrich_mod
from tests.conftest import invite_and_join

FIX = Path(__file__).parent / "fixtures"
UPLOAD_HEADERS = {"X-Requested-With": "ReValli"}


async def _project(client):
    r = await client.post("/api/projects", json={"title": "Revisão"})
    return r.json()["id"]


async def _import(client, pid, name, source="PubMed", content=None, **extra):
    data = content if content is not None else (FIX / name).read_bytes()
    return await client.post(
        f"/api/projects/{pid}/imports",
        files={"file": (name, data)},
        data={"source": source, **extra},
        headers=UPLOAD_HEADERS,
    )


async def test_upload_requires_custom_header(admin):
    pid = await _project(admin)
    r = await admin.post(
        f"/api/projects/{pid}/imports",
        files={"file": ("a.ris", (FIX / "sample.ris").read_bytes())},
        data={"source": "X"},
    )
    assert r.status_code == 415


async def test_import_ris_and_list(admin):
    pid = await _project(admin)
    r = await _import(
        admin, pid, "sample.ris", source="Scopus", query="exercise AND anxiety", reported_count="2"
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["imported"] == 2
    assert body["search"]["file_format"] == "ris"
    assert body["search"]["query"] == "exercise AND anxiety"
    page = (await admin.get(f"/api/projects/{pid}/records")).json()
    assert page["total"] == 2
    assert page["items"][0]["authors"] == ["Silva, João", "Souza, Maria"]
    found = (await admin.get(f"/api/projects/{pid}/records", params={"q": "ansiedade"})).json()
    assert found["total"] == 1
    by_author = (await admin.get(f"/api/projects/{pid}/records", params={"q": "pereira"})).json()
    assert by_author["total"] == 1


async def test_import_errors(admin):
    pid = await _project(admin)
    r = await _import(admin, pid, "x.pdf", content=b"%PDF-1.4")
    assert r.status_code == 422 and r.json()["detail"] == "unknown_format"
    r = await _import(admin, pid, "x.ris", content=b"TY  - JOUR\nER  - \n")
    assert r.status_code == 422 and r.json()["detail"] == "no_records_found"


async def test_reviewer_cannot_import_but_can_read(admin):
    pid = await _project(admin)
    await _import(admin, pid, "sample.ris")
    rev = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    assert (await _import(rev, pid, "sample.ris")).status_code == 403
    assert (await rev.get(f"/api/projects/{pid}/records")).json()["total"] == 2
    await rev.aclose()


async def test_dedup_across_sources(admin):
    """O mesmo artigo vindo de RIS, BibTeX, WoS e CSV (mesmo DOI) vira um grupo automático."""
    pid = await _project(admin)
    for name, src in [
        ("sample.ris", "Scopus"),
        ("sample.bib", "Google"),
        ("sample_wos.txt", "Web of Science"),
        ("sample.csv", "Outra"),
    ]:
        assert (await _import(admin, pid, name, source=src)).status_code == 201
    summary = (await admin.get(f"/api/projects/{pid}/summary")).json()
    # ris 2 + bib 2 + wos 1 + csv 2 = 7; o artigo do DOI 10.1000/abc.123 aparece 4 vezes
    assert summary["records_total"] == 7
    assert summary["duplicates_removed"] == 3
    assert summary["records_unique"] == 4
    assert {s["source"]: s["records"] for s in summary["by_source"]}["Scopus"] == 2
    groups = (await admin.get(f"/api/projects/{pid}/duplicates?status=confirmed")).json()
    assert groups["total"] == 1
    g = groups["items"][0]
    assert g["method"] == "doi" and len(g["records"]) == 4
    # O principal é o mais completo (tem resumo)
    primary = next(r for r in g["records"] if r["id"] == g["primary_record_id"])
    assert primary["abstract"]
    dups = (await admin.get(f"/api/projects/{pid}/records?filter=duplicates")).json()
    assert dups["total"] == 3


def _ris(title, author="Silva, J", year="2020", doi=None):
    lines = ["TY  - JOUR", f"TI  - {title}", f"AU  - {author}", f"PY  - {year}"]
    if doi:
        lines.append(f"DO  - {doi}")
    return ("\n".join(lines) + "\nER  - \n").encode()


async def test_fuzzy_title_goes_to_review_and_reject_is_remembered(admin):
    pid = await _project(admin)
    await _import(
        admin, pid, "a.ris", content=_ris("Exercise and anxiety in older adults: a trial")
    )
    await _import(
        admin,
        pid,
        "b.ris",
        content=_ris("Exercise and anxiety in older adult: a trial", year="2021"),
    )
    await _import(
        admin,
        pid,
        "c.ris",
        content=_ris("Exercise & anxiety in older adults (a trial)", year="2019"),
    )
    pending = (await admin.get(f"/api/projects/{pid}/duplicates")).json()
    assert pending["total"] == 1
    group = pending["items"][0]
    assert group["method"] == "title"
    assert len(group["records"]) == 3
    assert (await admin.get(f"/api/projects/{pid}/summary")).json()["pending_groups"] == 1

    # Tira o terceiro do grupo
    third = next(r for r in group["records"] if r["year"] == 2019)
    r = await admin.post(
        f"/api/projects/{pid}/duplicates/{group['id']}/split", json={"record_id": third["id"]}
    )
    assert r.status_code == 200 and len(r.json()["records"]) == 2
    # Rejeita o grupo inteiro
    r = await admin.post(f"/api/projects/{pid}/duplicates/{group['id']}/reject", json={})
    assert r.status_code == 204
    # Rodar de novo não recria o grupo
    r = await admin.post(f"/api/projects/{pid}/dedup", json={})
    assert r.status_code == 202 and r.json()["status"] == "done"
    assert (await admin.get(f"/api/projects/{pid}/duplicates")).json()["total"] == 0


async def test_confirm_pending_group(admin):
    pid = await _project(admin)
    await _import(admin, pid, "a.ris", content=_ris("Yoga for anxiety in students: a pilot study"))
    await _import(
        admin,
        pid,
        "b.ris",
        content=_ris("Yoga for anxiety in students. A pilot study", year="2021"),
    )
    group = (await admin.get(f"/api/projects/{pid}/duplicates")).json()["items"][0]
    keep = group["records"][1]["id"]
    r = await admin.post(
        f"/api/projects/{pid}/duplicates/{group['id']}/confirm", json={"primary_record_id": keep}
    )
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    s = (await admin.get(f"/api/projects/{pid}/summary")).json()
    assert (s["duplicates_removed"], s["pending_groups"]) == (1, 0)
    # Importar mais um igual (mesmo DOI de nenhum) mantém o grupo confirmado e o adiciona
    await _import(admin, pid, "c.ris", content=_ris("Yoga for anxiety in students: a pilot study"))
    s = (await admin.get(f"/api/projects/{pid}/summary")).json()
    assert s["records_total"] == 3


async def test_different_authors_or_dois_are_not_grouped(admin):
    pid = await _project(admin)
    await _import(
        admin,
        pid,
        "a.ris",
        content=_ris("Anxiety in nurses during the pandemic", author="Silva, J"),
    )
    await _import(
        admin,
        pid,
        "b.ris",
        content=_ris("Anxiety in nurses during the pandemic", author="Costa, M"),
    )
    await _import(
        admin, pid, "c.ris", content=_ris("A study of depression in nurses", doi="10.1000/x")
    )
    await _import(
        admin, pid, "d.ris", content=_ris("A study of depression in nurses", doi="10.1000/y")
    )
    assert (await admin.get(f"/api/projects/{pid}/duplicates")).json()["total"] == 0
    assert (await admin.get(f"/api/projects/{pid}/duplicates?status=confirmed")).json()[
        "total"
    ] == 0


async def test_delete_search_removes_records_and_groups(admin):
    pid = await _project(admin)
    r1 = await _import(admin, pid, "sample.ris")
    await _import(admin, pid, "sample.bib")
    assert (await admin.get(f"/api/projects/{pid}/summary")).json()["duplicates_removed"] == 1
    sid = r1.json()["search"]["id"]
    assert (await admin.delete(f"/api/projects/{pid}/searches/{sid}")).status_code == 204
    s = (await admin.get(f"/api/projects/{pid}/summary")).json()
    assert (s["records_total"], s["duplicates_removed"]) == (2, 0)
    assert (await admin.get(f"/api/projects/{pid}/duplicates?status=confirmed")).json()[
        "total"
    ] == 0
    assert len((await admin.get(f"/api/projects/{pid}/searches")).json()) == 1


async def test_update_search_metadata(admin):
    pid = await _project(admin)
    sid = (await _import(admin, pid, "sample.ris")).json()["search"]["id"]
    r = await admin.patch(
        f"/api/projects/{pid}/searches/{sid}",
        json={"query": "novo", "searched_on": "2026-10-01", "reported_count": 10},
    )
    assert r.status_code == 200
    assert (r.json()["query"], r.json()["searched_on"], r.json()["reported_count"]) == (
        "novo",
        "2026-10-01",
        10,
    )


def _openalex_handler(request: httpx.Request) -> httpx.Response:
    flt = request.url.params.get("filter", "")
    search = request.url.params.get("search", "")
    if flt.startswith("doi:"):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "doi": "https://doi.org/10.5555/XYZ.9",
                        "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/31234567"},
                        "publication_year": 2019,
                        "abstract_inverted_index": {"Resumo": [0], "recuperado.": [1]},
                    }
                ]
            },
        )
    if search:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Totally different", "doi": "https://doi.org/10.9/no"},
                    {
                        "title": "Mindful breathing reduces exam anxiety",
                        "doi": "https://doi.org/10.7777/breath",
                        "publication_year": 2022,
                        "abstract_inverted_index": {"Breathing": [0], "helps.": [1]},
                    },
                ]
            },
        )
    return httpx.Response(200, json={"results": []})


async def test_enrichment(admin, monkeypatch):
    pid = await _project(admin)
    await _import(admin, pid, "sample.ris")
    await _import(
        admin, pid, "t.ris", content=_ris("Mindful breathing reduces exam anxiety", year="2022")
    )

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(_openalex_handler), **kwargs)

    monkeypatch.setattr(enrich_mod.httpx, "AsyncClient", fake_client)
    r = await admin.post(f"/api/projects/{pid}/enrich", json={})
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["status"] == "done", job
    recs = {
        x["title"]: x for x in (await admin.get(f"/api/projects/{pid}/records")).json()["items"]
    }
    pt = recs["Efeito do exercício na ansiedade de idosos"]
    assert pt["abstract"] == "Resumo recuperado."
    assert pt["enriched"] == {"abstract": "openalex"}
    br = recs["Mindful breathing reduces exam anxiety"]
    assert br["doi"] == "10.7777/breath" and br["abstract"] == "Breathing helps."
    # O que já existia não é sobrescrito
    en = recs["Physical exercise and anxiety in older adults: a randomized trial"]
    assert en["doi"] == "10.1000/abc.123" and en["enriched"] == {}


async def test_jobs_list(admin):
    pid = await _project(admin)
    await _import(admin, pid, "sample.ris")
    jobs = (await admin.get(f"/api/projects/{pid}/jobs")).json()
    assert jobs[0]["kind"] == "dedup" and jobs[0]["status"] == "done"
    assert (await admin.get(f"/api/projects/{pid}/jobs?active=true")).json() == []


async def test_abstract_from_index():
    assert enrich_mod.abstract_from_index({"b": [1], "a": [0, 2]}) == "a b a"
    assert enrich_mod.abstract_from_index(None) == ""
