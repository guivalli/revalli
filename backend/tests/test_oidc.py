import base64
import hashlib
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, update

from revalli.core.config import get_settings
from revalli.core.db import SessionLocal
from revalli.core.security import verify_password
from revalli.models import User
from revalli.modules.auth import oidc
from tests.conftest import make_client

ISSUER = "https://sso.example.org/realms/lab"
CLIENT_ID = "revalli"


def _jwk(public, kid: str) -> dict:
    nums = public.public_numbers()

    def b64(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": b64(nums.n),
        "e": b64(nums.e),
    }


class Provider:
    """Um provedor OIDC de mentira: descoberta, chaves e troca de código."""

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.id_token = ""
        self.last_form: dict = {}
        self.token_status = 200

    def pem(self, key) -> bytes:
        return key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def sign(self, claims: dict, key=None, kid: str = "k1") -> str:
        return jwt.encode(
            claims, self.pem(key or self.key), algorithm="RS256", headers={"kid": kid}
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": ISSUER + "/auth",
                    "token_endpoint": ISSUER + "/token",
                    "jwks_uri": ISSUER + "/jwks",
                },
            )
        if path.endswith("/jwks"):
            return httpx.Response(200, json={"keys": [_jwk(self.key.public_key(), "k1")]})
        if path.endswith("/token"):
            self.last_form = dict(parse_qs(request.content.decode()))
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"id_token": self.id_token, "access_token": "x"})
        return httpx.Response(404)


@pytest.fixture
def provider(monkeypatch):
    p = Provider()
    s = get_settings()
    monkeypatch.setattr(s, "oidc_issuer", ISSUER)
    monkeypatch.setattr(s, "oidc_client_id", CLIENT_ID)
    monkeypatch.setattr(s, "oidc_client_secret", "shh")
    monkeypatch.setattr(s, "public_url", "https://revalli.example.org")
    oidc.set_transport(httpx.MockTransport(p.handler))
    yield p
    oidc.set_transport(None)


def _claims(nonce: str, **over) -> dict:
    now = int(time.time())
    base = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "user-1",
        "iat": now,
        "exp": now + 300,
        "nonce": nonce,
        "email": "admin@example.org",
        "email_verified": True,
        "name": "Admin SSO",
    }
    return {**base, **over}


async def _begin(c: httpx.AsyncClient) -> dict:
    r = await c.get("/api/auth/oidc/login")
    assert r.status_code == 303, r.text
    return {k: v[0] for k, v in parse_qs(urlsplit(r.headers["location"]).query).items()}


async def _finish(c, provider, claims_over=None, *, key=None, state=None, nonce=None, **claims):
    q = await _begin(c)
    claims = _claims(nonce or q["nonce"], **claims)
    provider.id_token = provider.sign(claims, key=key)
    return q, await c.get(
        "/api/auth/oidc/callback", params={"code": "abc", "state": state or q["state"]}
    )


async def test_disabled_by_default(client):
    assert (await client.get("/api/auth/oidc/config")).json() == {"enabled": False, "label": ""}
    assert (await client.get("/api/auth/oidc/login")).status_code == 404
    assert (await client.get("/api/auth/oidc/callback")).status_code == 404


async def test_login_redirect_uses_pkce_and_exact_redirect_uri(admin, provider):
    anon = make_client()
    assert (await anon.get("/api/auth/oidc/config")).json()["enabled"] is True
    q = await _begin(anon)
    assert q["response_type"] == "code" and q["client_id"] == CLIENT_ID
    assert q["redirect_uri"] == "https://revalli.example.org/api/auth/oidc/callback"
    assert q["scope"] == "openid email profile" and q["code_challenge_method"] == "S256"
    r = await anon.get("/api/auth/oidc/login")
    assert "revalli_oidc" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]
    await anon.aclose()


async def test_existing_user_signs_in(admin, provider):
    anon = make_client()
    q, r = await _finish(anon, provider)
    assert r.status_code == 303 and r.headers["location"] == "/"
    me = await anon.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "admin@example.org"
    # O PKCE chegou ao provedor: o verifier bate com o challenge enviado antes
    verifier = provider.last_form["code_verifier"][0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge.rstrip(b"=").decode() == q["code_challenge"]
    assert provider.last_form["client_secret"] == ["shh"]
    await anon.aclose()


@pytest.mark.parametrize(
    ("over", "error"),
    [
        ({"aud": "outro-cliente"}, "invalid_id_token"),
        ({"iss": "https://evil.example.org"}, "invalid_id_token"),
        ({"exp": 1}, "invalid_id_token"),
        ({"email_verified": False}, "email_not_verified"),
        ({"email_verified": None}, "email_not_verified"),
        ({"email": ""}, "no_email"),
        ({"nonce": "outro"}, "nonce_mismatch"),
    ],
)
async def test_invalid_id_tokens_are_refused(admin, provider, over, error):
    anon = make_client()
    over = dict(over)
    nonce = over.pop("nonce", None)
    _, r = await _finish(anon, provider, nonce=nonce, **over)
    assert r.status_code == 303 and r.headers["location"] == f"/login?erro={error}"
    assert (await anon.get("/api/auth/me")).status_code == 401
    await anon.aclose()


async def test_signature_and_state_are_checked(admin, provider):
    anon = make_client()
    _, r = await _finish(anon, provider, key=provider.other)  # assinado com outra chave
    assert r.headers["location"] == "/login?erro=invalid_id_token"
    _, r = await _finish(anon, provider, state="forjado")
    assert r.headers["location"] == "/login?erro=state_mismatch"
    # Sem o cookie da tentativa (outro navegador): recusa
    other = make_client()
    q = await _begin(anon)
    provider.id_token = provider.sign(_claims(q["nonce"]))
    r = await other.get("/api/auth/oidc/callback", params={"code": "abc", "state": q["state"]})
    assert r.headers["location"] == "/login?erro=invalid_attempt"
    # Erro devolvido pelo provedor e falha na troca do código
    r = await anon.get("/api/auth/oidc/callback", params={"error": "access_denied"})
    assert r.headers["location"] == "/login?erro=provider_access_denied"
    provider.token_status = 400
    _, r = await _finish(anon, provider)
    assert r.headers["location"] == "/login?erro=token_exchange_failed"
    for c in (anon, other):
        await c.aclose()


async def test_unknown_email_needs_an_account_or_auto_create(admin, provider, monkeypatch):
    anon = make_client()
    _, r = await _finish(anon, provider, email="nova@example.org")
    assert r.headers["location"] == "/login?erro=no_account"

    monkeypatch.setattr(get_settings(), "oidc_auto_create", True)
    _, r = await _finish(anon, provider, email="nova@example.org", name="Nova Pessoa")
    assert r.headers["location"] == "/"
    me = (await anon.get("/api/auth/me")).json()
    assert me["email"] == "nova@example.org" and me["full_name"] == "Nova Pessoa"
    assert me["is_admin"] is False
    # Conta sem senha: nem a senha de exemplo nem uma vazia entram por /auth/login
    r = await make_client().post(
        "/api/auth/login", json={"email": "nova@example.org", "password": "revalli-dummy-password"}
    )
    assert r.status_code == 401
    await anon.aclose()


async def test_domains_and_disabled_accounts(admin, provider, monkeypatch):
    anon = make_client()
    monkeypatch.setattr(get_settings(), "oidc_allowed_domains", "lab.org, @outro.org")
    _, r = await _finish(anon, provider)  # admin@example.org
    assert r.headers["location"] == "/login?erro=domain_not_allowed"
    monkeypatch.setattr(get_settings(), "oidc_allowed_domains", "")

    async with SessionLocal() as db:
        await db.execute(
            update(User).where(User.email == "admin@example.org").values(is_active=False)
        )
        await db.commit()
    _, r = await _finish(anon, provider)
    assert r.headers["location"] == "/login?erro=account_disabled"
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        assert len(users) == 1
    await anon.aclose()


async def test_missing_email_verified_is_allowed_only_when_configured(admin, provider, monkeypatch):
    anon = make_client()
    monkeypatch.setattr(get_settings(), "oidc_require_verified_email", False)
    _, r = await _finish(anon, provider, email_verified=None)
    assert r.headers["location"] == "/"
    # Mas "falso" é recusado sempre
    anon2 = make_client()
    _, r = await _finish(anon2, provider, email_verified=False)
    assert r.headers["location"] == "/login?erro=email_not_verified"
    for c in (anon, anon2):
        await c.aclose()


def test_account_without_password_never_verifies():
    assert verify_password("revalli-dummy-password", "") is False
    assert verify_password("x", None) is False
    assert verify_password("x", "!oidc") is False
