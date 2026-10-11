import io
import uuid
import zipfile

import httpx
import pymupdf

from revalli.modules.fulltext import service as ft_service
from revalli.modules.fulltext import storage
from revalli.modules.fulltext.service import _public_url
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


async def _project_ft(admin):
    pid = (await admin.post("/api/projects", json={"title": "PDFs"})).json()["id"]
    content = b"".join(_ris(t, author=f"A{i}, X", doi=d) + b"\n" for i, (t, d) in enumerate(TITLES))
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


def test_public_url_guard():
    assert _public_url("https://europepmc.org/a.pdf")
    for bad in (
        "http://localhost/a.pdf",
        "http://127.0.0.1/a.pdf",
        "http://10.0.0.5/a.pdf",
        "http://db:5432/x",
        "file:///etc/passwd",
        "http://169.254.169.254/latest",
    ):
        assert not _public_url(bad), bad


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
        if request.url.host == "repo.example.org":
            return httpx.Response(200, content=pdf)
        raise AssertionError(f"unexpected request {request.url}")

    real = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(ft_service.httpx, "AsyncClient", fake_client)
    r = await admin.post(f"/api/projects/{pid}/files/open-access", json={})
    assert r.status_code == 202, r.text
    assert r.json()["result"] == {"checked": 2, "found": 2, "downloaded": 1}, r.json()["error"]
    files = (await admin.get(f"/api/projects/{pid}/records/{ids[TITLES[0][0]]}/files")).json()
    assert files[0]["source"] == "open_access"
    assert files[0]["source_url"] == "https://repo.example.org/a.pdf"
