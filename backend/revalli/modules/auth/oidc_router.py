from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db
from revalli.core.deps import start_session
from revalli.models import User
from revalli.modules.auth import oidc

router = APIRouter(prefix="/auth/oidc", tags=["auth"])

# Contas criadas pelo login único não têm senha: este valor nunca é um hash válido
NO_PASSWORD = "!oidc"


class OIDCConfig(BaseModel):
    enabled: bool
    label: str = ""


@router.get("/config", response_model=OIDCConfig)
async def config():
    s = get_settings()
    return OIDCConfig(enabled=oidc.enabled(s), label=s.oidc_button_label)


def _back(error: str, response: RedirectResponse | None = None) -> RedirectResponse:
    out = response or RedirectResponse("/login?erro=" + quote(error), status_code=303)
    out.delete_cookie(oidc.STATE_COOKIE, path="/api/auth/oidc")
    return out


@router.get("/login")
async def login():
    s = get_settings()
    if not oidc.enabled(s):
        return JSONResponse({"detail": "oidc_disabled"}, status_code=404)
    try:
        url, attempt = await oidc.start(s)
    except oidc.OIDCError as exc:
        return _back(str(exc))
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        oidc.STATE_COOKIE,
        attempt.seal(),
        max_age=oidc.STATE_TTL,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",  # a volta do provedor é uma navegação de nível superior
        path="/api/auth/oidc",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    if not oidc.enabled(s):
        return JSONResponse({"detail": "oidc_disabled"}, status_code=404)
    if error:
        return _back("provider_" + error[:40])
    try:
        attempt = oidc.Attempt.open(request.cookies.get(oidc.STATE_COOKIE))
        if not code or state != attempt.state:
            raise oidc.OIDCError("state_mismatch")
        who = await oidc.complete(code, attempt, s)
    except oidc.OIDCError as exc:
        return _back(str(exc))

    user = (await db.execute(select(User).where(User.email == who.email))).scalar_one_or_none()
    if user is None:
        if not s.oidc_auto_create:
            return _back("no_account")
        user = User(email=who.email, full_name=who.name, password_hash=NO_PASSWORD, is_admin=False)
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:  # outra aba criou a mesma conta agora
            await db.rollback()
            user = (await db.execute(select(User).where(User.email == who.email))).scalar_one()
    if not user.is_active or user.is_bot:
        return _back("account_disabled")

    response = RedirectResponse("/", status_code=303)
    await start_session(db, response, user)
    return _back("", response)
