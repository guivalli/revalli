import uuid
from datetime import timedelta

from sqlalchemy import update

from revalli.core.db import SessionLocal, utcnow
from revalli.modules.tokens.models import ApiToken
from tests.conftest import invite_and_join, make_client


def _bearer(token: str):
    return make_client_with(headers={"Authorization": f"Bearer {token}"})


def make_client_with(headers):
    c = make_client()
    c.headers.update(headers)
    return c


async def _make(admin, **body):
    r = await admin.post("/api/tokens", json={"name": "Painel", **body})
    assert r.status_code == 201, r.text
    return r.json()


async def test_token_reads_projects_and_cannot_write(admin):
    pid = (await admin.post("/api/projects", json={"title": "A"})).json()["id"]
    created = await _make(admin)
    assert created["token"].startswith("rvl_") and created["prefix"] == created["token"][:10]
    listed = (await admin.get("/api/tokens")).json()
    assert [t["id"] for t in listed] == [created["id"]] and "token" not in listed[0]

    async with _bearer(created["token"]) as api:
        r = await api.get("/api/projects")
        assert r.status_code == 200 and [p["id"] for p in r.json()] == [pid]
        assert (await api.get(f"/api/projects/{pid}/summary")).status_code == 200
        assert (await api.get("/api/auth/me")).json()["email"] == "admin@example.org"
        # Só leitura: escrever, mesmo em JSON, é recusado
        r = await api.post("/api/projects", json={"title": "B"})
        assert r.status_code == 403 and r.json()["detail"] == "token_read_only"
        r = await api.delete(f"/api/projects/{pid}")
        assert r.status_code == 403 and r.json()["detail"] == "token_read_only"
        assert (await admin.get(f"/api/projects/{pid}/summary")).status_code == 200
        # Fora de /api/projects: administração e gestão de chaves ficam de fora
        for path in ("/api/ai/providers", "/api/tokens", "/api/ai/settings"):
            r = await api.get(path)
            assert r.status_code == 403 and r.json()["detail"] == "token_scope", path
        # Uma chave não cria outra
        r = await api.post("/api/tokens", json={"name": "x"})
        assert r.status_code == 403

    used = (await admin.get("/api/tokens")).json()[0]
    assert used["last_used_at"] is not None


async def test_token_invalid_revoked_expired(admin):
    created = await _make(admin, expires_in_days=7)
    async with _bearer("rvl_nope") as api:
        assert (await api.get("/api/projects")).status_code == 401
    # Com um cabeçalho inválido, o cookie de sessão não vale como alternativa
    admin.headers["Authorization"] = "Bearer rvl_nope"
    assert (await admin.get("/api/projects")).status_code == 401
    del admin.headers["Authorization"]

    async with SessionLocal() as db:
        await db.execute(
            update(ApiToken)
            .where(ApiToken.id == uuid.UUID(created["id"]))
            .values(expires_at=utcnow() - timedelta(minutes=1))
        )
        await db.commit()
    async with _bearer(created["token"]) as api:
        assert (await api.get("/api/projects")).status_code == 401

    fresh = await _make(admin)
    async with _bearer(fresh["token"]) as api:
        assert (await api.get("/api/projects")).status_code == 200
        assert (await admin.delete(f"/api/tokens/{fresh['id']}")).status_code == 204
        assert (await api.get("/api/projects")).status_code == 401


async def test_project_scoped_token(admin):
    a = (await admin.post("/api/projects", json={"title": "A"})).json()["id"]
    b = (await admin.post("/api/projects", json={"title": "B"})).json()["id"]
    created = await _make(admin, project_id=a)
    async with _bearer(created["token"]) as api:
        assert [p["id"] for p in (await api.get("/api/projects")).json()] == [a]
        assert (await api.get(f"/api/projects/{a}/summary")).status_code == 200
        assert (await api.get(f"/api/projects/{b}/summary")).status_code == 404


async def test_tokens_belong_to_their_owner(admin):
    pid = (await admin.post("/api/projects", json={"title": "A"})).json()["id"]
    other = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    mine = await _make(admin)
    assert (await other.get("/api/tokens")).json() == []
    assert (await other.delete(f"/api/tokens/{mine['id']}")).status_code == 404
    # Não dá para criar chave de um projeto do qual não se participa
    private = (await admin.post("/api/projects", json={"title": "Privado"})).json()["id"]
    r = await other.post("/api/tokens", json={"name": "x", "project_id": private})
    assert r.status_code == 404
    # A chave de um revisor enxerga o que o revisor enxerga
    t = (await other.post("/api/tokens", json={"name": "rev"})).json()["token"]
    async with _bearer(t) as api:
        ids = [p["id"] for p in (await api.get("/api/projects")).json()]
        assert ids == [pid]
        assert (await api.get(f"/api/projects/{private}/summary")).status_code == 404
    await other.aclose()
