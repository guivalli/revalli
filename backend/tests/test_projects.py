from tests.conftest import PASSWORD, invite_and_join, make_client


async def _create(client, title="Revisão A"):
    r = await client.post("/api/projects", json={"title": title, "review_type": "scoping"})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_and_list(admin):
    p = await _create(admin)
    assert p["my_role"] == "lead"
    assert p["member_count"] == 1
    assert p["review_type"] == "scoping"
    projects = (await admin.get("/api/projects")).json()
    assert [x["id"] for x in projects] == [p["id"]]


async def test_project_invite_adds_member_with_role(admin):
    p = await _create(admin)
    rev = await invite_and_join(admin, "rev@ex.org", p["id"], "reviewer", name="Revisora")
    projects = (await rev.get("/api/projects")).json()
    assert len(projects) == 1 and projects[0]["my_role"] == "reviewer"
    members = (await admin.get(f"/api/projects/{p['id']}/members")).json()
    assert {m["email"]: m["role"] for m in members} == {
        "admin@example.org": "lead",
        "rev@ex.org": "reviewer",
    }
    await rev.aclose()


async def test_non_member_cannot_see_project(admin):
    p = await _create(admin)
    other = await invite_and_join(admin, "fora@ex.org")
    assert (await other.get(f"/api/projects/{p['id']}")).status_code == 404
    assert (await other.get("/api/projects")).json() == []
    await other.aclose()


async def test_reviewer_cannot_edit_or_invite(admin):
    p = await _create(admin)
    rev = await invite_and_join(admin, "rev@ex.org", p["id"], "reviewer")
    assert (await rev.patch(f"/api/projects/{p['id']}", json={"title": "x"})).status_code == 403
    r = await rev.post(
        "/api/invitations", json={"email": "z@ex.org", "project_id": p["id"], "role": "reviewer"}
    )
    assert r.status_code == 403
    assert (await rev.delete(f"/api/projects/{p['id']}")).status_code == 403
    await rev.aclose()


async def test_lead_manages_members(admin):
    p = await _create(admin)
    rev = await invite_and_join(admin, "rev@ex.org", p["id"], "reviewer")
    me = (await rev.get("/api/auth/me")).json()
    url = f"/api/projects/{p['id']}/members/{me['id']}"
    r = await admin.patch(url, json={"role": "arbitrator"})
    assert r.status_code == 200 and r.json()["role"] == "arbitrator"
    assert (await admin.delete(url)).status_code == 204
    assert (await rev.get(f"/api/projects/{p['id']}")).status_code == 404
    await rev.aclose()


async def test_add_existing_user_by_email(admin):
    p = await _create(admin)
    other = await invite_and_join(admin, "existe@ex.org")
    r = await admin.post(
        f"/api/projects/{p['id']}/members", json={"email": "EXISTE@ex.org", "role": "observer"}
    )
    assert r.status_code == 201 and r.json()["role"] == "observer"
    r = await admin.post(f"/api/projects/{p['id']}/members", json={"email": "existe@ex.org"})
    assert r.status_code == 409
    r = await admin.post(f"/api/projects/{p['id']}/members", json={"email": "nao@ex.org"})
    assert r.status_code == 404
    await other.aclose()


async def test_cannot_remove_last_lead(admin):
    p = await _create(admin)
    me = (await admin.get("/api/auth/me")).json()
    url = f"/api/projects/{p['id']}/members/{me['id']}"
    assert (await admin.patch(url, json={"role": "reviewer"})).status_code == 409
    assert (await admin.delete(url)).status_code == 409


async def test_existing_account_must_login_to_accept(admin):
    p = await _create(admin)
    other = await invite_and_join(admin, "existe@ex.org")
    r = await admin.post("/api/invitations", json={"email": "existe@ex.org", "project_id": p["id"]})
    token = r.json()["invite_url"].rsplit("/", 1)[1]
    async with make_client() as anon:
        r = await anon.post(f"/api/invitations/{token}/accept", json={})
        assert r.status_code == 401
    r = await other.post(f"/api/invitations/{token}/accept", json={})
    assert r.status_code == 200
    assert (await other.get(f"/api/projects/{p['id']}")).json()["my_role"] == "reviewer"
    await other.aclose()


async def test_delete_project(admin):
    p = await _create(admin)
    assert (await admin.delete(f"/api/projects/{p['id']}")).status_code == 204
    assert (await admin.get(f"/api/projects/{p['id']}")).status_code == 404


async def test_login_after_invite(admin):
    c = await invite_and_join(admin, "x@ex.org")
    await c.aclose()
    async with make_client() as c2:
        r = await c2.post("/api/auth/login", json={"email": "x@ex.org", "password": PASSWORD})
        assert r.status_code == 200
