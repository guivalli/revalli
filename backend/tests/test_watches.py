import json
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import update

from revalli.core.db import SessionLocal, utcnow
from revalli.modules.imports.parsers import parse_csl_json, parse_file
from revalli.modules.sources import clients
from revalli.modules.watches import service as watch_service
from revalli.modules.watches.models import Watch
from revalli.modules.watches.scheduler import dispatch_due
from tests import test_sources
from tests.conftest import invite_and_join
from tests.test_records import _import, _ris


@pytest.fixture(autouse=True)
def fake_bases():
    original = list(test_sources.PUBMED)
    clients.set_transport(httpx.MockTransport(test_sources._router))
    yield
    clients.set_transport(None)
    watch_service.set_transport(None)
    test_sources.PUBMED[:] = original


async def _project(admin) -> str:
    return (await admin.post("/api/projects", json={"title": "Viva"})).json()["id"]


async def _records(admin, pid) -> int:
    r = await admin.get(f"/api/projects/{pid}/records", params={"page_size": 1})
    return r.json()["total"]


API = {"kind": "api_search", "source": "pubmed", "query": "anxiety", "every_days": 7}


async def test_living_search_imports_only_what_is_new(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"
    r = await admin.post(base, json={**API, "name": "Ansiedade"})
    assert r.status_code == 201, r.text
    w = r.json()
    assert w["has_secret"] is False and w["next_run_at"] and w["last_status"] == ""

    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.status_code == 202 and r.json()["result"]["new"] == 3, r.json()
    assert await _records(admin, pid) == 3

    # Mesma busca de novo: nada novo, nada duplicado
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["new"] == 0 and r.json()["result"]["found"] == 3
    assert await _records(admin, pid) == 3

    # A base ganhou um artigo: só ele entra, como uma busca "(atualização)"
    test_sources.PUBMED.append(("904", "Pubmed trial four"))
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["new"] == 1
    assert await _records(admin, pid) == 4
    searches = (await admin.get(f"/api/projects/{pid}/searches")).json()
    assert [s["source"] for s in searches].count("PubMed (atualização)") == 2

    got = (await admin.get(base)).json()[0]
    assert got["last_status"] == "ok" and got["last_new"] == 1 and got["total_new"] == 4
    assert got["last_found"] == 4


async def test_failed_run_is_recorded_and_retried_tomorrow(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"
    w = (await admin.post(base, json={**API, "query": "bad[["})).json()
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["status"] == "done" and "error" in r.json()["result"]
    got = (await admin.get(base)).json()[0]
    assert got["last_status"] == "error" and got["last_error"] and got["last_new"] == 0
    # Tenta de novo em um dia, não no intervalo normal
    assert got["next_run_at"] < (utcnow() + timedelta(days=2)).isoformat()
    # Quando volta a funcionar, recupera
    await admin.put(f"{base}/{w['id']}", json={**API})
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["new"] == 3
    assert (await admin.get(base)).json()[0]["last_status"] == "ok"


def _feed(handler):
    watch_service.set_transport(httpx.MockTransport(handler))


async def test_feed_url_with_secret_and_redirects(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"
    ris = _ris("Exercise and anxiety in older adults", doi="10.1234/a") + _ris(
        "Yoga for generalized anxiety disorder in adults", doi="10.1234/b"
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers["host"] == "lib.example.org" and request.url.path == "/old":
            return httpx.Response(302, headers={"location": "https://cdn.example.net/lib.ris"})
        if request.headers["host"] == "lib.example.org":
            return httpx.Response(200, content=ris)
        if request.headers["host"] == "cdn.example.net":
            return httpx.Response(200, content=ris)
        return httpx.Response(404)

    _feed(handler)
    body = {
        "kind": "feed_url",
        "url": "https://lib.example.org/export.ris",
        "secret": "Bearer abc123",
        "every_days": 1,
    }
    w = (await admin.post(base, json=body)).json()
    assert w["has_secret"] is True and "abc123" not in json.dumps(w)
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["new"] == 2, r.json()
    assert seen[0].headers["authorization"] == "Bearer abc123"
    # A conexão foi para o IP conferido, com o nome no Host
    assert seen[0].url.host == "93.184.216.34"

    # Redirecionamento para outro servidor não leva a credencial junto
    seen.clear()
    await admin.put(f"{base}/{w['id']}", json={**body, "url": "https://lib.example.org/old"})
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["new"] == 0  # já tinha
    assert [x.headers["host"] for x in seen] == ["lib.example.org", "cdn.example.net"]
    assert "authorization" in seen[0].headers and "authorization" not in seen[1].headers


async def test_feed_cannot_reach_internal_addresses(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não devia conectar: {request.url}")

    _feed(handler)
    for url in (
        "http://127.0.0.1/x.ris",
        "http://169.254.169.254/latest/meta-data",
        "http://db:5432/x.ris",
        "http://localhost:8000/api/health",
    ):
        w = (await admin.post(base, json={"kind": "feed_url", "url": url})).json()
        r = await admin.post(f"{base}/{w['id']}/run", json={})
        assert r.json()["result"]["error"] == "blocked_address", url
        await admin.delete(f"{base}/{w['id']}")

    # Redirecionamento de um servidor público para a rede interna
    def redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://10.0.0.7/secret.ris"})

    _feed(redirect)
    w = (
        await admin.post(base, json={"kind": "feed_url", "url": "https://lib.example.org/a.ris"})
    ).json()
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["error"] == "blocked_address"


async def test_feed_unknown_format_and_http_error(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"
    w = (
        await admin.post(base, json={"kind": "feed_url", "url": "https://lib.example.org/a"})
    ).json()
    _feed(lambda r: httpx.Response(200, content=b"<html>login</html>"))
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["error"] == "unknown_format"
    _feed(lambda r: httpx.Response(403))
    r = await admin.post(f"{base}/{w['id']}/run", json={})
    assert r.json()["result"]["error"] == "http_403"


async def test_permissions_and_validation(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"
    rev = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    w = (await admin.post(base, json=API)).json()
    assert len((await rev.get(base)).json()) == 1  # membros veem o estado
    assert (await rev.post(base, json=API)).status_code == 403
    assert (await rev.post(f"{base}/{w['id']}/run", json={})).status_code == 403
    assert (await rev.delete(f"{base}/{w['id']}")).status_code == 403
    assert (
        await admin.post(base, json={"kind": "api_search", "source": "pubmed"})
    ).status_code == 422
    assert (await admin.post(base, json={"kind": "feed_url"})).status_code == 422
    assert (
        await admin.post(base, json={"kind": "feed_url", "url": "ftp://x/y"})
    ).status_code == 422
    other = await _project(admin)
    assert (
        await admin.post(f"/api/projects/{other}/watches/{w['id']}/run", json={})
    ).status_code == 404
    assert (await admin.delete(f"{base}/{w['id']}")).status_code == 204
    await rev.aclose()


async def test_scheduler_dispatches_due_watches_once(admin):
    pid = await _project(admin)
    base = f"/api/projects/{pid}/watches"
    due = (await admin.post(base, json=API)).json()
    off = (await admin.post(base, json={**API, "enabled": False})).json()
    later = (await admin.post(base, json=API)).json()
    past = utcnow() - timedelta(hours=1)
    async with SessionLocal() as db:
        await db.execute(
            update(Watch)
            .where(Watch.id.in_([uuid.UUID(due["id"]), uuid.UUID(off["id"])]))
            .values(next_run_at=past)
        )
        await db.commit()
    sent: list[str] = []
    assert await dispatch_due(sent.append) == 1
    # A passada seguinte não cria o mesmo job de novo
    assert await dispatch_due(sent.append) == 0
    assert len(sent) == 1
    jobs = (await admin.get(f"/api/projects/{pid}/jobs")).json()
    assert [j["kind"] for j in jobs] == ["watch_run"] and jobs[0]["status"] == "queued"
    assert later["id"] != due["id"]


def test_csl_json_parser():
    text = json.dumps(
        [
            {
                "id": "a",
                "type": "article-journal",
                "title": "Exercise and anxiety",
                "author": [{"family": "Silva", "given": "Ana"}, {"literal": "WHO Group"}],
                "issued": {"date-parts": [[2021, 5]]},
                "container-title": "J Anxiety",
                "volume": "3",
                "page": "10–19",
                "DOI": "https://doi.org/10.1234/ABC",
                "PMID": "123",
                "keyword": "exercise, anxiety",
            },
            "lixo",
        ]
    )
    (rec,) = [r.clean() for r in parse_csl_json(text)]
    assert rec.authors == ["Silva, Ana", "WHO Group"] and rec.year == 2021
    assert rec.doi == "10.1234/abc" and rec.pmid == "123" and rec.pages == "10-19"
    assert rec.keywords == ["exercise", "anxiety"]
    fmt, recs = parse_file("lib.json", text.encode())
    assert fmt == "csl" and len(recs) == 1
    with pytest.raises(Exception):  # noqa: B017
        parse_csl_json("{not json")


async def test_csl_export_roundtrips(admin):
    pid = await _project(admin)
    await _import(
        admin, pid, "a.ris", content=_ris("Exercise and anxiety in older adults", doi="10.1234/a")
    )
    r = await admin.get(f"/api/projects/{pid}/export", params={"format": "csl"})
    assert r.status_code == 200 and r.headers["content-type"].startswith(
        "application/vnd.citationstyles"
    )
    assert r.headers["content-disposition"].endswith('.json"')
    items = r.json()
    assert (
        items[0]["title"] == "Exercise and anxiety in older adults"
        and items[0]["DOI"] == "10.1234/a"
    )
    assert items[0]["author"] == [{"family": "Silva", "given": "J"}]
    # O que sai pode entrar de novo
    _, back = parse_file("x.json", r.content)
    assert back[0].doi == "10.1234/a" and back[0].authors == ["Silva, J"]
