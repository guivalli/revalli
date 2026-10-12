import io
import uuid
import zipfile

import httpx
import pymupdf
import pytest

from revalli.modules.fulltext import service as ft_service
from revalli.modules.fulltext import storage
from revalli.modules.fulltext.studies import trial_ids
from tests.conftest import invite_and_join
from tests.test_records import UPLOAD_HEADERS, _import, _ris

TA = "title_abstract"
TITLES = [
    ("Aerobic exercise for generalized anxiety disorder in adults", "10.1234/aero.1"),
    ("Yoga practice and anxiety symptoms in university students", "10.1234/yoga.2"),
    ("Resistance training effects on anxiety among older women", None),
]


def make_pdf(*lines: str, pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for p in range(pages):
        page = doc.new_page()
        y = 72
        for line in lines if p == 0 else [f"Page {p + 1} body text " * 5]:
            page.insert_text((72, y), line, fontsize=10)
            y += 14
        # Texto suficiente para não parecer PDF escaneado
        page.insert_text((72, y + 20), "Methods and results paragraph. " * 8, fontsize=8)
    data = doc.tobytes()
    doc.close()
    return data


async def _project_ft(admin, content: bytes | None = None):
    pid = (await admin.post("/api/projects", json={"title": "PDFs"})).json()["id"]
    if content is None:
        content = b"".join(
            _ris(t, author=f"A{i}, X", doi=d) + b"\n" for i, (t, d) in enumerate(TITLES)
        )
    await _import(admin, pid, "x.ris", content=content)
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["reviewers_title_abstract"] = 1
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    items = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"]
    for it in items:
        await admin.post(
            f"/api/projects/{pid}/screening/{TA}/decisions",
            json={"record_id": it["id"], "decision": "include"},
        )
    return pid, {it["title"]: it["id"] for it in items}


async def _upload(client, pid, rid, data, name="paper.pdf"):
    return await client.post(
        f"/api/projects/{pid}/records/{rid}/files",
        files={"file": (name, data, "application/pdf")},
        headers=UPLOAD_HEADERS,
    )


async def test_upload_view_and_delete(admin):
    pid, ids = await _project_ft(admin)
    rid = ids[TITLES[0][0]]
    pdf = make_pdf("Aerobic exercise", pages=3)
    r = await _upload(admin, pid, rid, pdf)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["pages"] == 3 and f["is_main"] and f["has_text"]
    # O mesmo arquivo de novo não duplica
    again = (await _upload(admin, pid, rid, pdf)).json()
    assert again["id"] == f["id"]
    second = (await _upload(admin, pid, rid, make_pdf("Supplement"), "supp.pdf")).json()
    assert second["is_main"] is False
    c = await admin.get(f"/api/projects/{pid}/files/{f['id']}/content")
    assert c.status_code == 200 and c.headers["content-type"] == "application/pdf"
    assert c.content.startswith(b"%PDF")
    assert (await _upload(admin, pid, rid, b"not a pdf")).status_code == 422
    assert (await admin.delete(f"/api/projects/{pid}/files/{f['id']}")).status_code == 204
    files = (await admin.get(f"/api/projects/{pid}/records/{rid}/files")).json()
    assert [x["id"] for x in files] == [second["id"]] and files[0]["is_main"]
    summary = (await admin.get(f"/api/projects/{pid}/files/summary")).json()
    assert summary == {"records": 3, "with_pdf": 1, "without_text": 0, "from_open_access": 0}
    # Excluir o projeto apaga os arquivos do disco
    folder = storage.files_dir(uuid.UUID(pid))
    assert any(folder.iterdir())
    assert (await admin.delete(f"/api/projects/{pid}")).status_code == 204
    assert not folder.exists()


async def test_upload_permissions(admin):
    pid, ids = await _project_ft(admin)
    obs = await invite_and_join(admin, "obs@ex.org", pid, "observer")
    rev = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    rid = ids[TITLES[1][0]]
    assert (await _upload(obs, pid, rid, make_pdf("x"))).status_code == 403
    r = await _upload(rev, pid, rid, make_pdf("x"))
    assert r.status_code == 201
    # Observador pode ler o PDF, mas não apagar
    assert (await obs.get(f"/api/projects/{pid}/files/{r.json()['id']}/content")).status_code == 200
    assert (await obs.delete(f"/api/projects/{pid}/files/{r.json()['id']}")).status_code == 403
    other = (await admin.post("/api/projects", json={"title": "Outro"})).json()["id"]
    assert (
        await rev.get(f"/api/projects/{other}/files/{r.json()['id']}/content")
    ).status_code == 404
    for c in (obs, rev):
        await c.aclose()


async def test_zip_matches_by_doi_and_title(admin):
    pid, ids = await _project_ft(admin)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # DOI no texto
        z.writestr("a.pdf", make_pdf("Some header", "https://doi.org/10.1234/AERO.1"))
        # DOI no nome do arquivo
        z.writestr("pdfs/10.1234_yoga.2.pdf", make_pdf("No identifiers here"))
        # Título na primeira página
        z.writestr("c.pdf", make_pdf("Resistance training effects on anxiety among older women"))
        z.writestr("d.pdf", make_pdf("Completely unrelated cardiology study"))
        z.writestr("broken.pdf", b"garbage")
        z.writestr("__MACOSX/._a.pdf", b"meta")
    r = await admin.post(
        f"/api/projects/{pid}/files/zip",
        files={"file": ("pdfs.zip", buf.getvalue(), "application/zip")},
        headers=UPLOAD_HEADERS,
    )
    assert r.status_code == 202, r.text
    res = r.json()["result"]
    assert (
        res["matched"] == 3 and res["unmatched"] == ["d.pdf"] and res["invalid"] == ["broken.pdf"]
    )
    for title, _ in TITLES:
        files = (await admin.get(f"/api/projects/{pid}/records/{ids[title]}/files")).json()
        assert len(files) == 1 and files[0]["source"] == "zip"


async def test_public_url_guard():
    from revalli.core import safefetch

    ok = await safefetch.public_ips("europepmc.org", 443)
    assert ok == ["93.184.216.34"]
    for bad in ("localhost", "127.0.0.1", "10.0.0.5", "db", "169.254.169.254", "::1", "x.internal"):
        with pytest.raises(safefetch.FetchError):
            await safefetch.public_ips(bad, 80)

    # Um nome público que resolve para a rede interna também é recusado
    async def internal(host: str, port: int) -> list[str]:
        return ["192.168.1.10"]

    safefetch.set_resolver(internal)
    with pytest.raises(safefetch.FetchError):
        await safefetch.public_ips("evil.example.org", 80)


async def test_open_access_download(admin, monkeypatch):
    pid, ids = await _project_ft(admin)
    pdf = make_pdf("Aerobic exercise open access")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/works":
            flt = request.url.params["filter"]
            assert "10.1234/aero.1" in flt and "10.1234/yoga.2" in flt
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "doi": "https://doi.org/10.1234/aero.1",
                            "best_oa_location": {"pdf_url": "https://repo.example.org/a.pdf"},
                            "locations": [],
                        },
                        {
                            "doi": "https://doi.org/10.1234/yoga.2",
                            "best_oa_location": {"pdf_url": "http://10.0.0.1/internal.pdf"},
                        },
                    ]
                },
            )
        # A conexão vai para o IP já conferido; o nome segue no cabeçalho Host
        if request.headers.get("host") == "repo.example.org":
            return httpx.Response(200, content=pdf)
        # O que o OpenAlex não resolve segue para as outras fontes, que aqui não têm nada
        if request.headers.get("host") == "www.ebi.ac.uk":
            return httpx.Response(200, json={"resultList": {"result": []}})
        if request.headers.get("host") == "doi.org":
            return httpx.Response(404)
        raise AssertionError(f"unexpected request {request.url}")

    real = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(ft_service.httpx, "AsyncClient", fake_client)
    r = await admin.post(f"/api/projects/{pid}/files/open-access", json={})
    assert r.status_code == 202, r.text
    result = r.json()["result"]
    assert result["checked"] == 2 and result["found"] == 2 and result["downloaded"] == 1
    assert result["by_source"] == {"openalex": 1}
    # Sem e-mail de contato o Unpaywall não é usado, e o resultado avisa
    assert result["skipped"] == ["unpaywall"]
    files = (await admin.get(f"/api/projects/{pid}/records/{ids[TITLES[0][0]]}/files")).json()
    assert files[0]["source"] == "open_access"
    assert files[0]["source_url"] == "https://repo.example.org/a.pdf"


def test_trial_ids():
    text = "Registered at ClinicalTrials.gov (nct01234567) and EudraCT: 2019-001234-56; ISRCTN12345678."
    assert trial_ids(text) == {"NCT01234567", "EudraCT 2019-001234-56", "ISRCTN12345678"}
    assert trial_ids("NCT123 is too short") == set()


async def _include_all_ft(admin, pid):
    items = (await admin.get(f"/api/projects/{pid}/screening/full_text/queue")).json()["items"]
    for it in items:
        r = await admin.post(
            f"/api/projects/{pid}/screening/full_text/decisions",
            json={"record_id": it["id"], "decision": "include"},
        )
        assert r.status_code in (200, 201), r.text


async def test_studies_group_suggest_and_prisma(admin):
    pid, ids = await _project_ft(admin)
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["reviewers_full_text"] = 1
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    a, b, c = (ids[t] for t, _ in TITLES)
    # Dois PDFs citam o mesmo registro de ensaio
    await _upload(admin, pid, a, make_pdf("Trial registration: NCT01234567"))
    await _upload(admin, pid, b, make_pdf("Follow-up of trial NCT01234567"))
    sug = (await admin.get(f"/api/projects/{pid}/studies/suggestions")).json()
    assert len(sug) == 1 and sug[0]["key"] == "NCT01234567"
    assert {r["id"] for r in sug[0]["records"]} == {a, b}

    r = await admin.post(f"/api/projects/{pid}/studies", json={"record_ids": [a, b]})
    assert r.status_code == 201, r.text
    study = r.json()
    assert study["label"].startswith("A0")
    assert [x["is_primary"] for x in study["reports"]] == [True, False]
    assert (await admin.get(f"/api/projects/{pid}/studies/suggestions")).json() == []

    # Adicionar o terceiro registro ao mesmo estudo e trocar o principal
    r = await admin.post(f"/api/projects/{pid}/studies", json={"record_ids": [c, a], "label": "X"})
    assert r.json()["id"] == study["id"] and len(r.json()["reports"]) == 3
    r = await admin.patch(
        f"/api/projects/{pid}/studies/{study['id']}", json={"primary_record_id": c}
    )
    assert [x["id"] for x in r.json()["reports"] if x["is_primary"]] == [c]
    assert r.json()["label"] == "X"

    await _include_all_ft(admin, pid)
    p = (await admin.get(f"/api/projects/{pid}/report/prisma")).json()
    assert p["included"] == 1 and p["included_reports"] == 3
    csv_text = (await admin.get(f"/api/projects/{pid}/export?format=csv&phase=full_text")).text
    assert csv_text.splitlines()[0].endswith(",study") and csv_text.count(",X\r\n") == 3

    # Tirar relatórios até sobrar um desfaz o grupo
    base = f"/api/projects/{pid}/studies/{study['id']}/reports"
    assert (await admin.delete(f"{base}/{c}")).status_code == 204
    studies = (await admin.get(f"/api/projects/{pid}/studies")).json()
    assert len(studies) == 1 and sum(x["is_primary"] for x in studies[0]["reports"]) == 1
    assert (await admin.delete(f"{base}/{b}")).status_code == 204
    assert (await admin.get(f"/api/projects/{pid}/studies")).json() == []
    p = (await admin.get(f"/api/projects/{pid}/report/prisma")).json()
    assert p["included"] == 3 and p["included_reports"] == 3


async def test_studies_merge_and_permissions(admin):
    pid, ids = await _project_ft(admin)
    a, b, c = (ids[t] for t, _ in TITLES)
    s1 = (await admin.post(f"/api/projects/{pid}/studies", json={"record_ids": [a, b]})).json()
    # c entra no grupo de a; grupos diferentes são fundidos
    other = await admin.post(f"/api/projects/{pid}/studies", json={"record_ids": [c, a]})
    assert other.json()["id"] == s1["id"]
    cands = (await admin.get(f"/api/projects/{pid}/studies/candidates?q=yoga")).json()
    assert [x["id"] for x in cands] == [b] and cands[0]["study_id"] == s1["id"]
    obs = await invite_and_join(admin, "obs2@ex.org", pid, "observer")
    assert (await obs.get(f"/api/projects/{pid}/studies")).status_code == 200
    assert (
        await obs.post(f"/api/projects/{pid}/studies", json={"record_ids": [a, b]})
    ).status_code == 403
    other_pid = (await admin.post("/api/projects", json={"title": "Outro"})).json()["id"]
    r = await admin.post(f"/api/projects/{other_pid}/studies", json={"record_ids": [a, b]})
    assert r.status_code == 404
    assert (await admin.delete(f"/api/projects/{pid}/studies/{s1['id']}")).status_code == 204
    assert (await admin.get(f"/api/projects/{pid}/studies")).json() == []
    await obs.aclose()


async def test_open_access_chain_and_pending_list(admin, monkeypatch):
    from revalli.core.config import get_settings

    monkeypatch.setattr(get_settings(), "enrichment_contact_email", "grupo@example.org")
    pdfs = {name: make_pdf(f"Open paper {name}") for name in "abc"}

    def ris(title, doi=None, url=None, pmid=None):
        lines = ["TY  - JOUR", f"TI  - {title}", "AU  - Silva, J", "PY  - 2021"]
        for tag, value in (("DO", doi), ("UR", url), ("AN", pmid)):
            if value:
                lines.append(f"{tag}  - {value}")
        return ("\n".join(lines) + "\nER  - \n").encode()

    content = b"\n".join(
        [
            ris("Paper A found by Unpaywall in a repository", doi="10.5555/a"),
            ris("Paper B found by Europe PMC with a PMID", doi="10.5555/b", pmid="12345678"),
            ris("Paper C only known by the journal page", url="https://revista.example.org/c"),
            ris("Paper D nobody has anywhere online", doi="10.5555/d"),
            ris("Paper E behind a blocked publisher page", doi="10.5555/e"),
        ]
    )
    pid, ids = await _project_ft(admin, content)

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.headers.get("host", request.url.host)
        path = request.url.path
        if host == "api.openalex.org":
            return httpx.Response(200, json={"results": []})
        if host == "api.unpaywall.org":
            assert request.url.params["email"] == "grupo@example.org"
            doi = path.removeprefix("/v2/")
            if doi == "10.5555/a":
                loc = {
                    "url_for_pdf": "https://repo.example.org/a.pdf",
                    "url": "https://repo.example.org/a",
                }
                return httpx.Response(200, json={"best_oa_location": loc, "oa_locations": [loc]})
            if doi == "10.5555/e":
                loc = {"url_for_pdf": None, "url_for_landing_page": "https://blocked.example.org/e"}
                return httpx.Response(200, json={"best_oa_location": loc, "oa_locations": [loc]})
            return httpx.Response(404, json={"error": True})
        if host == "www.ebi.ac.uk":
            if "12345678" in request.url.params["query"]:
                item = {
                    "availability": "Free",
                    "documentStyle": "pdf",
                    "url": "https://epmc.example.org/b.pdf",
                }
                paid = {
                    "availability": "Subscription required",
                    "documentStyle": "pdf",
                    "url": "https://paid.example.org/b.pdf",
                }
                body = {
                    "resultList": {"result": [{"fullTextUrlList": {"fullTextUrl": [paid, item]}}]}
                }
                return httpx.Response(200, json=body)
            return httpx.Response(200, json={"resultList": {"result": []}})
        if host == "repo.example.org" and path == "/a.pdf":
            return httpx.Response(200, content=pdfs["a"])
        if host == "epmc.example.org" and path == "/b.pdf":
            return httpx.Response(200, content=pdfs["b"])
        if host == "revista.example.org" and path == "/c":
            page = '<html><head><meta name="citation_pdf_url" content="/pdf/c.pdf"></head></html>'
            return httpx.Response(200, content=page.encode(), headers={"content-type": "text/html"})
        if host == "revista.example.org" and path == "/pdf/c.pdf":
            return httpx.Response(200, content=pdfs["c"])
        if host in ("blocked.example.org", "doi.org"):
            return httpx.Response(403 if host == "blocked.example.org" else 404)
        raise AssertionError(f"unexpected request {request.url}")

    real = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(ft_service.httpx, "AsyncClient", fake_client)
    r = await admin.post(f"/api/projects/{pid}/files/open-access", json={})
    assert r.status_code == 202, r.text
    result = r.json()["result"]
    assert result["checked"] == 5 and result["downloaded"] == 3 and result["found"] == 3
    assert result["by_source"] == {"unpaywall": 1, "europepmc": 1, "article_page": 1}
    assert "skipped" not in result

    # Quem ninguém achou fica na lista de pendentes, com DOI e link
    pending = (await admin.get(f"/api/projects/{pid}/files/pending")).json()
    assert sorted(p["doi"] for p in pending) == ["10.5555/d", "10.5555/e"]
    assert {p["link"] for p in pending} == {
        "https://doi.org/10.5555/d",
        "https://doi.org/10.5555/e",
    }

    # CSV para baixar a lista
    csv_resp = await admin.get(f"/api/projects/{pid}/files/pending.csv")
    assert csv_resp.status_code == 200 and csv_resp.text.startswith("\ufeff")
    assert "https://doi.org/10.5555/d" in csv_resp.text


def test_pdf_links_in_page_markup():
    from revalli.modules.fulltext.finders import pdf_links_in_html

    markup = (
        '<meta name="Citation_PDF_URL" content="https://a.org/x.pdf">'
        '<link rel="alternate" type="application/pdf" href="/files/y.pdf">'
        '<meta name="citation_pdf_url" content="https://a.org/x.pdf">'
    )
    assert pdf_links_in_html(markup, "https://rev.org/art/1") == [
        "https://a.org/x.pdf",
        "https://rev.org/files/y.pdf",
    ]
    assert pdf_links_in_html("<html><body>sem marcas", "https://rev.org/") == []


async def test_open_access_uses_landing_pages_known_to_openalex(admin, monkeypatch):
    pdf = make_pdf("Paper G open on the journal site")
    content = (
        b"TY  - JOUR\nTI  - Paper G whose DOI does not resolve but OpenAlex knows the page\n"
        b"AU  - Silva, J\nPY  - 2021\nDO  - 10.5555/g\nER  - \n"
        b"TY  - JOUR\nTI  - Paper H that only has an OpenAlex page as link\n"
        b"AU  - Souza, M\nPY  - 2022\nUR  - https://openalex.org/W999\nER  - \n"
    )
    pid, _ = await _project_ft(admin, content)
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.headers.get("host", request.url.host)
        asked.append(host)
        if host == "api.openalex.org":
            work = {
                "doi": "https://doi.org/10.5555/g",
                "best_oa_location": {
                    "pdf_url": None,
                    "landing_page_url": "https://revista.example.org/g",
                },
                "locations": [
                    {"pdf_url": None, "landing_page_url": "https://revista.example.org/g"}
                ],
            }
            return httpx.Response(200, json={"results": [work]})
        if host == "revista.example.org" and request.url.path == "/g":
            page = '<meta name="citation_pdf_url" content="https://revista.example.org/g.pdf">'
            return httpx.Response(200, content=page.encode(), headers={"content-type": "text/html"})
        if host == "revista.example.org" and request.url.path == "/g.pdf":
            return httpx.Response(200, content=pdf)
        if host in ("api.unpaywall.org", "doi.org"):
            return httpx.Response(404)
        if host == "www.ebi.ac.uk":
            return httpx.Response(200, json={"resultList": {"result": []}})
        raise AssertionError(f"unexpected request {request.url}")

    real = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(ft_service.httpx, "AsyncClient", fake_client)
    r = await admin.post(f"/api/projects/{pid}/files/open-access", json={})
    result = r.json()["result"]
    assert result["downloaded"] == 1 and result["by_source"] == {"article_page": 1}, result
    # A página do próprio OpenAlex nunca é aberta como se fosse o artigo
    assert "openalex.org" not in asked


async def test_fetch_tries_the_next_address_when_one_does_not_connect():
    from revalli.core import safefetch

    async def two_addresses(host: str, port: int) -> list[str]:
        return ["93.184.216.34", "2606:4700:4700::1111"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.216.34":
            raise httpx.ConnectError("sem rota")
        return httpx.Response(200, content=b"%PDF-1.4 ok")

    safefetch.set_resolver(two_addresses)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            got = await safefetch.get_bytes(c, "https://journal.example.org/a.pdf", max_bytes=1000)
        assert got.data.startswith(b"%PDF")
    finally:
        safefetch.set_resolver(None)
