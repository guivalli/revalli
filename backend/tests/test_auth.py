from tests.conftest import PASSWORD, make_client


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["database"] is True


async def test_setup_only_once(client):
    assert (await client.get("/api/setup")).json() == {"needs_setup": True}
    r = await client.post(
        "/api/setup", json={"email": "a@b.org", "full_name": "A", "password": PASSWORD}
    )
    assert r.status_code == 201
    assert r.json()["is_admin"] is True
    assert (await client.get("/api/setup")).json() == {"needs_setup": False}
    r = await client.post(
        "/api/setup", json={"email": "c@d.org", "full_name": "C", "password": PASSWORD}
    )
    assert r.status_code == 409


async def test_setup_rejects_short_password(client):
    r = await client.post(
        "/api/setup", json={"email": "a@b.org", "full_name": "A", "password": "curta"}
    )
    assert r.status_code == 422


async def test_setup_logs_in_and_email_is_normalized(admin):
    r = await admin.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "admin@example.org"


async def test_login_logout(admin):
    async with make_client() as c:
        assert (await c.get("/api/auth/me")).status_code == 401
        r = await c.post("/api/auth/login", json={"email": "ADMIN@example.org", "password": "x"})
        assert r.status_code == 401
        r = await c.post(
            "/api/auth/login", json={"email": "admin@example.org", "password": PASSWORD}
        )
        assert r.status_code == 200
        assert (await c.get("/api/auth/me")).status_code == 200
        assert (await c.post("/api/auth/logout", json={})).status_code == 204
        assert (await c.get("/api/auth/me")).status_code == 401


async def test_session_cookie_is_httponly(client):
    r = await client.post(
        "/api/setup", json={"email": "a@b.org", "full_name": "A", "password": PASSWORD}
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_login_rate_limit(admin):
    async with make_client() as c:
        for _ in range(10):
            r = await c.post(
                "/api/auth/login", json={"email": "admin@example.org", "password": "x"}
            )
            assert r.status_code == 401
        r = await c.post(
            "/api/auth/login", json={"email": "admin@example.org", "password": PASSWORD}
        )
        assert r.status_code == 429


async def test_writes_require_json(admin):
    r = await admin.post(
        "/api/projects",
        content="title=x",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 415


async def test_instance_invitation_flow(admin):
    r = await admin.post("/api/invitations", json={"email": "nova@ex.org"})
    token = r.json()["invite_url"].rsplit("/", 1)[1]
    info = (await admin.get(f"/api/invitations/{token}")).json()
    assert info == {
        "email": "nova@ex.org",
        "project_title": None,
        "role": None,
        "account_exists": False,
    }
    async with make_client() as c:
        r = await c.post(f"/api/invitations/{token}/accept", json={"full_name": "Nova"})
        assert r.status_code == 422
        r = await c.post(
            f"/api/invitations/{token}/accept", json={"full_name": "Nova", "password": PASSWORD}
        )
        assert r.status_code == 200
        assert r.json()["is_admin"] is False
        assert (await c.get("/api/auth/me")).json()["email"] == "nova@ex.org"
    # O convite não pode ser reutilizado
    assert (await admin.get(f"/api/invitations/{token}")).status_code == 404


async def test_only_admin_invites_to_instance(admin):
    from tests.conftest import invite_and_join

    member = await invite_and_join(admin, "membro@ex.org")
    r = await member.post("/api/invitations", json={"email": "outro@ex.org"})
    assert r.status_code == 403
    await member.aclose()
