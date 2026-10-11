import uuid
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db, utcnow
from revalli.core.security import hash_token, new_token
from revalli.models import Project, ProjectMember, Session, User
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


async def optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
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
    if project is None:
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
