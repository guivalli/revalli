from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db, utcnow
from revalli.core.deps import (
    current_user,
    end_session,
    get_membership,
    optional_user,
    start_session,
)
from revalli.core.ratelimit import SlidingWindowLimiter
from revalli.core.security import hash_password, hash_token, new_token, verify_password
from revalli.models import Invitation, Project, ProjectMember, User
from revalli.modules.auth.schemas import (
    AcceptInvitationIn,
    InvitationCreated,
    InvitationIn,
    InvitationInfo,
    LoginIn,
    SetupIn,
    SetupStatus,
    UserOut,
)
from revalli.modules.projects.models import Role

router = APIRouter(tags=["auth"])

_settings = get_settings()
login_limiter = SlidingWindowLimiter(_settings.login_max_attempts, _settings.login_window_seconds)


def _norm_email(email: str) -> str:
    return email.strip().lower()


async def _user_count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


@router.get("/setup", response_model=SetupStatus)
async def setup_status(db: AsyncSession = Depends(get_db)):
    return SetupStatus(needs_setup=await _user_count(db) == 0)


@router.post("/setup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def setup(body: SetupIn, response: Response, db: AsyncSession = Depends(get_db)):
    """Cria o primeiro administrador. Só funciona enquanto não existe nenhum usuário."""
    # Trava de transação para que duas requisições simultâneas não criem dois admins
    await db.execute(select(func.pg_advisory_xact_lock(4242)))
    if await _user_count(db) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_set_up")
    user = User(
        email=_norm_email(body.email),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        is_admin=True,
    )
    db.add(user)
    await db.flush()
    await start_session(db, response, user)
    return user


@router.post("/auth/login", response_model=UserOut)
async def login(
    body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    email = _norm_email(body.email)
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{email}"
    if not login_limiter.hit(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not verify_password(body.password, user.password_hash if user else None) or (
        user and not user.is_active
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    login_limiter.reset(key)
    await start_session(db, response, user)
    return user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await end_session(db, request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user


@router.post("/invitations", response_model=InvitationCreated, status_code=201)
async def create_invitation(
    body: InvitationIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Admins convidam para a instância; líderes convidam para o próprio projeto."""
    role: Role | None = None
    if body.project_id is not None:
        _, my_role = await get_membership(db, body.project_id, user)
        if my_role != Role.lead and not user.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "lead_only")
        try:
            role = Role(body.role or Role.reviewer)
        except ValueError as exc:
            raise HTTPException(422, "invalid_role") from exc
    elif not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_only")

    token = new_token()
    inv = Invitation(
        token_hash=hash_token(token),
        email=_norm_email(body.email),
        invited_by_id=user.id,
        project_id=body.project_id,
        role=role,
        expires_at=utcnow() + timedelta(days=_settings.invite_days),
    )
    db.add(inv)
    await db.commit()
    return InvitationCreated(
        id=inv.id,
        email=inv.email,
        invite_url=f"{_settings.public_url.rstrip('/')}/convite/{token}",
        expires_at=inv.expires_at,
    )


async def _valid_invitation(db: AsyncSession, token: str) -> Invitation:
    inv = (
        await db.execute(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if inv is None or inv.accepted_at is not None or inv.expires_at < utcnow():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_invalid")
    return inv


@router.get("/invitations/{token}", response_model=InvitationInfo)
async def invitation_info(token: str, db: AsyncSession = Depends(get_db)):
    inv = await _valid_invitation(db, token)
    project = await db.get(Project, inv.project_id) if inv.project_id else None
    exists = (
        await db.execute(select(User.id).where(User.email == inv.email))
    ).scalar_one_or_none() is not None
    return InvitationInfo(
        email=inv.email,
        project_title=project.title if project else None,
        role=inv.role,
        account_exists=exists,
    )


@router.post("/invitations/{token}/accept", response_model=UserOut)
async def accept_invitation(
    token: str,
    body: AcceptInvitationIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    logged: User | None = Depends(optional_user),
):
    inv = await _valid_invitation(db, token)
    user = (await db.execute(select(User).where(User.email == inv.email))).scalar_one_or_none()

    if user is None:
        if not body.full_name or not body.full_name.strip() or not body.password:
            raise HTTPException(422, "name_and_password_required")
        user = User(
            email=inv.email,
            full_name=body.full_name.strip(),
            password_hash=hash_password(body.password),
        )
        db.add(user)
        await db.flush()
    elif logged is None or logged.id != user.id:
        # Conta já existe: é preciso estar logado nela para aceitar
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "login_required")

    if inv.project_id is not None:
        existing = await db.get(ProjectMember, (inv.project_id, user.id))
        if existing is None:
            db.add(ProjectMember(project_id=inv.project_id, user_id=user.id, role=inv.role))
    inv.accepted_at = utcnow()
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "conflict") from exc

    if logged is None:
        await start_session(db, response, user)
    else:
        await db.commit()
    return user
