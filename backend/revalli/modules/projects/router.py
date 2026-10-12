import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import Project, ProjectMember, Record, User
from revalli.modules.fulltext import storage
from revalli.modules.projects.models import Role
from revalli.modules.projects.schemas import (
    MemberIn,
    MemberOut,
    MemberPatch,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _out(
    project: Project,
    role: Role | None,
    count: int,
    records: int = 0,
    owner: str = "",
) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    out.my_role = role
    out.member_count = count
    out.record_count = records
    out.owner_name = owner
    return out


async def _extras(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, str]]:
    """Número de referências e nome de quem criou, por projeto."""
    if not ids:
        return {}
    records = dict(
        (
            await db.execute(
                select(Record.project_id, func.count())
                .where(Record.project_id.in_(ids))
                .group_by(Record.project_id)
            )
        ).all()
    )
    owners = dict(
        (
            await db.execute(
                select(Project.id, User.full_name)
                .join(User, User.id == Project.created_by_id)
                .where(Project.id.in_(ids))
            )
        ).all()
    )
    return {i: (records.get(i, 0), owners.get(i, "")) for i in ids}


async def _member_count(db: AsyncSession, project_id: uuid.UUID) -> int:
    q = (
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project_id)
    )
    return (await db.execute(q)).scalar_one()


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    counts = (
        select(ProjectMember.project_id, func.count().label("n"))
        .group_by(ProjectMember.project_id)
        .subquery()
    )
    mine = (
        select(ProjectMember.project_id, ProjectMember.role)
        .where(ProjectMember.user_id == user.id)
        .subquery()
    )
    q = (
        select(Project, mine.c.role, func.coalesce(counts.c.n, 0))
        .outerjoin(mine, mine.c.project_id == Project.id)
        .outerjoin(counts, counts.c.project_id == Project.id)
        .order_by(Project.created_at.desc())
    )
    if not user.is_admin:
        q = q.where(mine.c.role.is_not(None))
    only = getattr(user, "api_token_project_id", None)
    if only is not None:
        q = q.where(Project.id == only)
    rows = (await db.execute(q)).all()
    extras = await _extras(db, [p.id for p, _, _ in rows])
    return [_out(p, Role(r) if r else None, n, *extras[p.id]) for p, r, n in rows]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project = Project(
        title=body.title.strip(),
        description=body.description,
        review_type=body.review_type,
        created_by_id=user.id,
    )
    db.add(project)
    await db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=Role.lead))
    await db.commit()
    return _out(project, Role.lead, 1, 0, user.full_name)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, role = await get_membership(db, project_id, user)
    extra = (await _extras(db, [project_id]))[project_id]
    return _out(project, role, await _member_count(db, project_id), *extra)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await require_lead(db, project_id, user)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(project, field, value.strip() if field == "title" else value)
    await db.commit()
    _, role = await get_membership(db, project_id, user)
    extra = (await _extras(db, [project_id]))[project_id]
    return _out(project, role, await _member_count(db, project_id), *extra)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project = await require_lead(db, project_id, user)
    await db.delete(project)
    await db.commit()
    await asyncio.to_thread(storage.remove_project, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/members", response_model=list[MemberOut])
async def list_members(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = (
        await db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(User.full_name)
        )
    ).all()
    return [
        MemberOut(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=Role(m.role),
            joined_at=m.created_at,
        )
        for m, u in rows
    ]


@router.post("/{project_id}/members", response_model=MemberOut, status_code=201)
async def add_member(
    project_id: uuid.UUID,
    body: MemberIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adiciona alguém que já tem conta. Para quem não tem, use um convite."""
    await require_lead(db, project_id, user)
    target = (
        await db.execute(select(User).where(User.email == body.email.strip().lower()))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    if await db.get(ProjectMember, (project_id, target.id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_member")
    member = ProjectMember(project_id=project_id, user_id=target.id, role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return MemberOut(
        user_id=target.id,
        email=target.email,
        full_name=target.full_name,
        role=body.role,
        joined_at=member.created_at,
    )


async def _ensure_other_lead(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    q = (
        select(func.count())
        .select_from(ProjectMember)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == Role.lead,
            ProjectMember.user_id != user_id,
        )
    )
    if (await db.execute(q)).scalar_one() == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "last_lead")


@router.patch("/{project_id}/members/{user_id}", response_model=MemberOut)
async def update_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    member = await db.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member_not_found")
    if member.role == Role.lead and body.role != Role.lead:
        await _ensure_other_lead(db, project_id, user_id)
    member.role = body.role
    await db.commit()
    target = await db.get(User, user_id)
    return MemberOut(
        user_id=user_id,
        email=target.email,
        full_name=target.full_name,
        role=body.role,
        joined_at=member.created_at,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # Qualquer membro pode sair do projeto; remover outros exige ser líder
    if user_id != user.id:
        await require_lead(db, project_id, user)
    else:
        await get_membership(db, project_id, user)
    member = await db.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member_not_found")
    if member.role == Role.lead:
        await _ensure_other_lead(db, project_id, user_id)
    await db.delete(member)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
