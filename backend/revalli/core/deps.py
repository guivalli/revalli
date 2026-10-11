import uuid
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db, utcnow
from revalli.core.security import hash_token, new_token
from revalli.models import ApiToken, Project, ProjectMember, Session, User
from revalli.modules.projects.models import Role

SESSION_COOKIE = "revalli_session"


async def start_session(db: AsyncSession, response: Response, user: User) -> None:
    settings = get_settings()
    token = new_token()
    expires = utcnow() + timedelta(days=settings.session_days)
    db.add(Session(token_hash=hash_token(token), user_id=user.id, expires_at=expires))
    # Limpa sessões vencidas do usuário aproveitando a ida ao banco
    await db.execute(
        delete(Session).where(Session.user_id == user.id, Session.expires_at < utcnow())
    )
    await db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


async def end_session(db: AsyncSession, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
        await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


# Uma chave de API só lê, e só nas rotas de projetos e na identificação de quem a usa
TOKEN_PATHS = ("/api/projects", "/api/auth/me")
TOKEN_METHODS = {"GET", "HEAD"}


async def _user_from_api_token(request: Request, db: AsyncSession, value: str) -> User | None:
    row = (
        await db.execute(
            select(ApiToken, User)
            .join(User, User.id == ApiToken.user_id)
            .where(ApiToken.token_hash == hash_token(value))
        )
    ).first()
    if row is None:
        return None
    token, user = row
    now = utcnow()
    if not user.is_active or user.is_bot or (token.expires_at and token.expires_at <= now):
        return None
    path = request.url.path
    if request.method not in TOKEN_METHODS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token_read_only")
    if not any(path == p or path.startswith(p + "/") for p in TOKEN_PATHS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token_scope")
    # Evita uma escrita a cada chamada: registra o uso no máximo uma vez por minuto
    if token.last_used_at is None or now - token.last_used_at > timedelta(seconds=60):
        token.last_used_at = now
        await db.commit()
    # Atributo só da requisição (não é coluna): restringe a chave a um projeto
    user.api_token_project_id = token.project_id  # type: ignore[attr-defined]
    return user


async def optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        # Com o cabeçalho presente, só vale a chave; o cookie não entra como alternativa
        return await _user_from_api_token(request, db, auth[7:].strip())
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    row = await db.execute(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(Session.token_hash == hash_token(token), Session.expires_at > utcnow())
    )
    user = row.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_only")
    return user


async def get_membership(
    db: AsyncSession, project_id: uuid.UUID, user: User
) -> tuple[Project, Role | None]:
    """Retorna o projeto e o papel do usuário. Admins enxergam todos os projetos."""
    project = await db.get(Project, project_id)
    only = getattr(user, "api_token_project_id", None)
    if project is None or (only is not None and only != project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project_not_found")
    member = await db.get(ProjectMember, (project_id, user.id))
    if member is None and not user.is_admin:
        # 404 em vez de 403 para não revelar que o projeto existe
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project_not_found")
    return project, Role(member.role) if member else None


async def require_lead(db: AsyncSession, project_id: uuid.UUID, user: User) -> Project:
    project, role = await get_membership(db, project_id, user)
    if role != Role.lead and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "lead_only")
    return project
