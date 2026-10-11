"""Login único por OpenID Connect (fluxo de código com PKCE).

A configuração vem do ambiente (OIDC_*). O ReValli confia no provedor para dizer quem a pessoa é:
o ID token é validado (assinatura, emissor, público, validade e nonce) e a conta é achada pelo
e-mail, que o provedor precisa declarar como verificado. Contas novas só são criadas com
OIDC_AUTO_CREATE, nunca como administradoras."""

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt

from revalli.core.config import Settings, get_settings
from revalli.modules.ai.crypto import decrypt, encrypt

STATE_COOKIE = "revalli_oidc"
STATE_TTL = 600
ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]
_DISCOVERY_TTL = 3600

# Permite trocar o transporte nos testes (sem rede)
_transport: httpx.AsyncBaseTransport | None = None
_cache: dict[str, tuple[float, dict]] = {}


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport
    _cache.clear()


class OIDCError(Exception):
    """O código vira o parâmetro de erro na volta para a tela de entrada."""


def enabled(s: Settings | None = None) -> bool:
    s = s or get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_client_secret)


def redirect_uri(s: Settings | None = None) -> str:
    return (s or get_settings()).public_url.rstrip("/") + "/api/auth/oidc/callback"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=20, transport=_transport, follow_redirects=False)


async def _get_json(url: str) -> dict:
    cached = _cache.get(url)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        async with _client() as c:
            resp = await c.get(url)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OIDCError("provider_unavailable") from exc
    _cache[url] = (time.monotonic() + _DISCOVERY_TTL, data)
    return data


async def discovery(s: Settings | None = None) -> dict:
    s = s or get_settings()
    issuer = s.oidc_issuer.rstrip("/")
    data = await _get_json(issuer + "/.well-known/openid-configuration")
    if str(data.get("issuer", "")).rstrip("/") != issuer:
        raise OIDCError("issuer_mismatch")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not data.get(key):
            raise OIDCError("provider_unavailable")
    return data


# --- Estado da tentativa (cookie cifrado) -----------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass
class Attempt:
    state: str
    nonce: str
    verifier: str

    def seal(self) -> str:
        payload = {
            "s": self.state,
            "n": self.nonce,
            "v": self.verifier,
            "e": time.time() + STATE_TTL,
        }
        return encrypt(json.dumps(payload))

    @classmethod
    def open(cls, sealed: str | None) -> "Attempt":
        raw = decrypt(sealed or "")
        try:
            data = json.loads(raw)
            if float(data["e"]) < time.time():
                raise OIDCError("expired_attempt")
            return cls(data["s"], data["n"], data["v"])
        except (ValueError, KeyError, TypeError) as exc:
            raise OIDCError("invalid_attempt") from exc


async def start(s: Settings | None = None) -> tuple[str, Attempt]:
    """Endereço do provedor para onde mandar a pessoa, e o estado a guardar no cookie."""
    s = s or get_settings()
    disc = await discovery(s)
    attempt = Attempt(
        state=secrets.token_urlsafe(24),
        nonce=secrets.token_urlsafe(24),
        verifier=secrets.token_urlsafe(48),
    )
    challenge = _b64(hashlib.sha256(attempt.verifier.encode()).digest())
    query = urlencode(
        {
            "response_type": "code",
            "client_id": s.oidc_client_id,
            "redirect_uri": redirect_uri(s),
            "scope": s.oidc_scopes,
            "state": attempt.state,
            "nonce": attempt.nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    sep = "&" if "?" in disc["authorization_endpoint"] else "?"
    return disc["authorization_endpoint"] + sep + query, attempt


# --- Volta do provedor ------------------------------------------------------------


@dataclass
class Identity:
    email: str
    name: str


async def _signing_key(disc: dict, token: str):
    header = jwt.get_unverified_header(token)
    jwks = (await _get_json(disc["jwks_uri"])).get("keys") or []
    kid = header.get("kid")
    candidates = [k for k in jwks if kid is None or k.get("kid") == kid]
    if not candidates:
        # As chaves podem ter girado: busca de novo uma vez
        _cache.pop(disc["jwks_uri"], None)
        jwks = (await _get_json(disc["jwks_uri"])).get("keys") or []
        candidates = [k for k in jwks if kid is None or k.get("kid") == kid]
    if not candidates:
        raise OIDCError("unknown_signing_key")
    return jwt.PyJWK(candidates[0]).key


async def complete(code: str, attempt: Attempt, s: Settings | None = None) -> Identity:
    s = s or get_settings()
    disc = await discovery(s)
    try:
        async with _client() as c:
            resp = await c.post(
                disc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri(s),
                    "client_id": s.oidc_client_id,
                    "client_secret": s.oidc_client_secret,
                    "code_verifier": attempt.verifier,
                },
                headers={"Accept": "application/json"},
            )
        resp.raise_for_status()
        id_token = resp.json().get("id_token")
    except (httpx.HTTPError, ValueError) as exc:
        raise OIDCError("token_exchange_failed") from exc
    if not id_token:
        raise OIDCError("token_exchange_failed")
    try:
        key = await _signing_key(disc, id_token)
        claims = jwt.decode(
            id_token,
            key,
            algorithms=ALGORITHMS,
            audience=s.oidc_client_id,
            issuer=disc["issuer"],
            leeway=60,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise OIDCError("invalid_id_token") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), attempt.nonce):
        raise OIDCError("nonce_mismatch")
    email = str(claims.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise OIDCError("no_email")
    verified = claims.get("email_verified")
    if verified is False or (s.oidc_require_verified_email and verified is not True):
        raise OIDCError("email_not_verified")
    domains = {
        d.strip().lower().lstrip("@") for d in s.oidc_allowed_domains.split(",") if d.strip()
    }
    if domains and email.rsplit("@", 1)[1] not in domains:
        raise OIDCError("domain_not_allowed")
    name = str(claims.get("name") or claims.get("preferred_username") or email.split("@")[0])
    return Identity(email=email, name=name[:200])
