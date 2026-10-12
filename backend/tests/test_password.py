"""Troca de senha e redefinição por link gerado pelo administrador."""

from tests.conftest import PASSWORD, invite_and_join, make_client

NEW = "uma-senha-nova-bem-longa"


async def test_change_own_password(admin):
    r = await admin.post(
        "/api/auth/password", json={"current_password": "errada-errada", "new_password": NEW}
    )
    assert r.status_code == 403 and r.json()["detail"] == "password_incorrect"
    short = await admin.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": "curta"}
    )
    assert short.status_code == 422
    ok = await admin.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW}
    )
    assert ok.status_code == 204
    # A sessão atual continua valendo; a senha antiga não entra mais
    assert (await admin.get("/api/auth/me")).status_code == 200
    other = make_client()
    bad = await other.post(
        "/api/auth/login", json={"email": "admin@example.org", "password": PASSWORD}
    )
    assert bad.status_code == 401
    good = await other.post("/api/auth/login", json={"email": "admin@example.org", "password": NEW})
    assert good.status_code == 200
    await other.aclose()


async def test_admin_generates_reset_link_and_person_sets_new_password(admin):
    member = await invite_and_join(admin, "rev@ex.org", name="Revisora")
    me = (await member.get("/api/auth/me")).json()

    # Só administrador gera o link
    assert (await member.post(f"/api/users/{me['id']}/password-reset", json={})).status_code == 403

    r = await admin.post(f"/api/users/{me['id']}/password-reset", json={})
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"] == "rev@ex.org" and "/redefinir-senha/" in created["reset_url"]
    token = created["reset_url"].rsplit("/", 1)[1]

    public = make_client()
    info = (await public.get(f"/api/password-resets/{token}")).json()
    assert info == {"email": "rev@ex.org", "full_name": "Revisora"}
    short = await public.post(f"/api/password-resets/{token}/accept", json={"password": "curta"})
    assert short.status_code == 422
    done = await public.post(f"/api/password-resets/{token}/accept", json={"password": NEW})
    assert done.status_code == 200 and done.json()["email"] == "rev@ex.org"
    assert (await public.get("/api/auth/me")).status_code == 200

    # O link vale uma vez, e a sessão antiga da pessoa foi encerrada
    again = await public.post(f"/api/password-resets/{token}/accept", json={"password": NEW + "x"})
    assert again.status_code == 404 and again.json()["detail"] == "reset_invalid"
    assert (await member.get("/api/auth/me")).status_code == 401
    login = make_client()
    ok = await login.post("/api/auth/login", json={"email": "rev@ex.org", "password": NEW})
    assert ok.status_code == 200
    for c in (public, login, member):
        await c.aclose()


async def test_new_reset_link_replaces_the_previous_one(admin):
    member = await invite_and_join(admin, "rev2@ex.org", name="Outra")
    uid = (await member.get("/api/auth/me")).json()["id"]
    first = (await admin.post(f"/api/users/{uid}/password-reset", json={})).json()["reset_url"]
    second = (await admin.post(f"/api/users/{uid}/password-reset", json={})).json()["reset_url"]
    public = make_client()
    t1, t2 = first.rsplit("/", 1)[1], second.rsplit("/", 1)[1]
    assert (await public.get(f"/api/password-resets/{t1}")).status_code == 404
    assert (await public.get(f"/api/password-resets/{t2}")).status_code == 200
    # Conta técnica da IA e usuário inexistente não têm link
    missing = await admin.post(
        "/api/users/00000000-0000-0000-0000-000000000000/password-reset", json={}
    )
    assert missing.status_code == 404
    await public.aclose()
    await member.aclose()
