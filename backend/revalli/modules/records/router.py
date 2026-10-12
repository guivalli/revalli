import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import Text, and_, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db, utcnow
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import DuplicateGroup, Job, NotDuplicate, Record, Search, User
from revalli.modules.imports.parsers import FORMATS, ImportFormatError, parse_file
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.models import ACTIVE_STATUSES, DuplicateStatus, JobStatus
from revalli.modules.records.schemas import (
    ConfirmIn,
    DuplicateGroupOut,
    DuplicatePage,
    ImportResult,
    JobOut,
    RecordOut,
    RecordPage,
    SearchOut,
    SearchPatch,
    SourceCount,
    SplitIn,
    Summary,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["records"])


def _is_dup_expr():
    """Registro que está num grupo confirmado e não é o principal."""
    return and_(
        DuplicateGroup.status == DuplicateStatus.confirmed,
        DuplicateGroup.primary_record_id != Record.id,
    )


def _record_out(r: Record, is_dup: bool) -> RecordOut:
    out = RecordOut.model_validate(r)
    out.is_duplicate = bool(is_dup)
    out.citation = (r.raw or {}).get("citation")
    return out


# --- Importação e buscas ------------------------------------------------------


@router.post("/imports", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def import_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    source: str = Form(..., min_length=1, max_length=200),
    query: str = Form("", max_length=50_000),
    searched_on: date | None = Form(None),
    reported_count: int | None = Form(None, ge=0),
    notes: str = Form("", max_length=20_000),
    file_format: str | None = Form(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    limit = get_settings().max_import_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
    if file_format and file_format not in FORMATS:
        raise HTTPException(422, "unknown_format")
    try:
        fmt, parsed = parse_file(file.filename or "", data, file_format or None)
    except ImportFormatError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # arquivo corrompido ou num formato inesperado
        raise HTTPException(422, "unreadable_file") from exc
    if not parsed:
        raise HTTPException(422, "no_records_found")

    search = Search(
        project_id=project_id,
        source=source.strip(),
        query=query,
        searched_on=searched_on,
        reported_count=reported_count,
        notes=notes,
        file_name=(file.filename or "")[:500],
        file_format=fmt,
        imported_count=len(parsed),
        created_by_id=user.id,
    )
    db.add(search)
    await db.flush()
    db.add_all(
        Record(
            project_id=project_id,
            search_id=search.id,
            title=p.title,
            abstract=p.abstract,
            authors=p.authors,
            year=p.year,
            journal=p.journal,
            volume=p.volume,
            issue=p.issue,
            pages=p.pages,
            doi=p.doi,
            pmid=p.pmid,
            url=p.url,
            keywords=p.keywords,
            language=p.language,
            publication_type=p.publication_type,
            raw=p.raw,
        )
        for p in parsed
    )
    await db.commit()
    job = await create_job(db, project_id, "dedup")
    await dispatch(db, job)
    return ImportResult(
        search=SearchOut.model_validate(search), imported=len(parsed), job_id=job.id
    )


@router.get("/searches", response_model=list[SearchOut])
async def list_searches(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    rows = await db.execute(
        select(Search).where(Search.project_id == project_id).order_by(Search.created_at)
    )
    return rows.scalars().all()


@router.patch("/searches/{search_id}", response_model=SearchOut)
async def update_search(
    project_id: uuid.UUID,
    search_id: uuid.UUID,
    body: SearchPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    search = await db.get(Search, search_id)
    if search is None or search.project_id != project_id:
        raise HTTPException(404, "search_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "source" and value is None:
            continue
        setattr(search, field, value.strip() if field == "source" else value)
    await db.commit()
    return search


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search(
    project_id: uuid.UUID,
    search_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apaga a busca e todos os registros importados dela."""
    await require_lead(db, project_id, user)
    search = await db.get(Search, search_id)
    if search is None or search.project_id != project_id:
        raise HTTPException(404, "search_not_found")
    await db.execute(delete(Record).where(Record.search_id == search_id))
    await db.delete(search)
    await db.commit()
    job = await create_job(db, project_id, "dedup")
    await dispatch(db, job)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Registros -----------------------------------------------------------------


@router.get("/records", response_model=RecordPage)
async def list_records(
    project_id: uuid.UUID,
    q: str = "",
    filter: str = Query("all", pattern="^(all|unique|duplicates|missing_abstract)$"),
    search_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    is_dup = func.coalesce(_is_dup_expr(), False).label("is_dup")
    stmt = (
        select(Record, is_dup)
        .outerjoin(DuplicateGroup, DuplicateGroup.id == Record.duplicate_group_id)
        .where(Record.project_id == project_id)
    )
    if search_id:
        stmt = stmt.where(Record.search_id == search_id)
    if filter == "unique":
        stmt = stmt.where(~func.coalesce(_is_dup_expr(), False))
    elif filter == "duplicates":
        stmt = stmt.where(func.coalesce(_is_dup_expr(), False))
    elif filter == "missing_abstract":
        stmt = stmt.where(Record.abstract == "", ~func.coalesce(_is_dup_expr(), False))
    if q.strip():
        term = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(
            or_(
                Record.title.ilike(term),
                Record.abstract.ilike(term),
                cast(Record.authors, Text).ilike(term),
                Record.journal.ilike(term),
                Record.doi.ilike(term),
            )
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Record.created_at, Record.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return RecordPage(
        items=[_record_out(r, d) for r, d in rows], total=total, page=page, page_size=page_size
    )


@router.get("/records/{record_id}", response_model=RecordOut)
async def get_record(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    row = (
        await db.execute(
            select(Record, func.coalesce(_is_dup_expr(), False))
            .outerjoin(DuplicateGroup, DuplicateGroup.id == Record.duplicate_group_id)
            .where(Record.id == record_id, Record.project_id == project_id)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "record_not_found")
    return _record_out(*row)


@router.get("/summary", response_model=Summary)
async def summary(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await get_membership(db, project_id, user)
    is_dup = func.coalesce(_is_dup_expr(), False)
    base = (
        select(Record.id, Record.abstract, Record.search_id, is_dup.label("dup"))
        .outerjoin(DuplicateGroup, DuplicateGroup.id == Record.duplicate_group_id)
        .where(Record.project_id == project_id)
        .subquery()
    )
    total, dups, missing = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(base.c.dup),
                func.count().filter(and_(~base.c.dup, base.c.abstract == "")),
            ).select_from(base)
        )
    ).one()
    pending = (
        await db.execute(
            select(func.count())
            .select_from(DuplicateGroup)
            .where(
                DuplicateGroup.project_id == project_id,
                DuplicateGroup.status == DuplicateStatus.pending,
            )
        )
    ).scalar_one()
    by_source = (
        await db.execute(
            select(Search.source, func.count(Record.id))
            .join(Record, Record.search_id == Search.id)
            .where(Search.project_id == project_id)
            .group_by(Search.source)
            .order_by(Search.source)
        )
    ).all()
    return Summary(
        records_total=total,
        duplicates_removed=dups,
        records_unique=total - dups,
        pending_groups=pending,
        missing_abstract=missing,
        by_source=[SourceCount(source=s, records=n) for s, n in by_source],
    )


# --- Duplicatas ----------------------------------------------------------------


async def _group_out(db: AsyncSession, group: DuplicateGroup) -> DuplicateGroupOut:
    recs = (
        (
            await db.execute(
                select(Record)
                .where(Record.duplicate_group_id == group.id)
                .order_by(Record.created_at)
            )
        )
        .scalars()
        .all()
    )
    confirmed = group.status == DuplicateStatus.confirmed
    return DuplicateGroupOut(
        id=group.id,
        status=group.status,
        method=group.method,
        score=group.score,
        primary_record_id=group.primary_record_id,
        records=[_record_out(r, confirmed and r.id != group.primary_record_id) for r in recs],
    )


async def _get_group(db: AsyncSession, project_id: uuid.UUID, group_id: uuid.UUID):
    group = await db.get(DuplicateGroup, group_id)
    if group is None or group.project_id != project_id:
        raise HTTPException(404, "group_not_found")
    return group


@router.get("/duplicates", response_model=DuplicatePage)
async def list_duplicates(
    project_id: uuid.UUID,
    status_: str = Query("pending", alias="status", pattern="^(pending|confirmed)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    where = (DuplicateGroup.project_id == project_id, DuplicateGroup.status == status_)
    total = (
        await db.execute(select(func.count()).select_from(DuplicateGroup).where(*where))
    ).scalar_one()
    groups = (
        (
            await db.execute(
                select(DuplicateGroup)
                .where(*where)
                .order_by(DuplicateGroup.score.desc(), DuplicateGroup.created_at)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return DuplicatePage(items=[await _group_out(db, g) for g in groups], total=total)


@router.post("/duplicates/{group_id}/confirm", response_model=DuplicateGroupOut)
async def confirm_group(
    project_id: uuid.UUID,
    group_id: uuid.UUID,
    body: ConfirmIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_lead(db, project_id, user)
    group = await _get_group(db, project_id, group_id)
    member = await db.get(Record, body.primary_record_id)
    if member is None or member.duplicate_group_id != group.id:
        raise HTTPException(422, "primary_not_in_group")
    group.status = DuplicateStatus.confirmed
    group.primary_record_id = member.id
    group.resolved_by_id = user.id
    group.resolved_at = utcnow()
    await db.commit()
    return await _group_out(db, group)


async def _mark_not_duplicates(
    db: AsyncSession, project_id: uuid.UUID, ids_a: list[uuid.UUID], ids_b: list[uuid.UUID]
) -> None:
    pairs = {tuple(sorted((a, b), key=str)) for a in ids_a for b in ids_b if a != b}
    existing = {
        (n.record_a_id, n.record_b_id)
        for n in (
            await db.execute(
                select(NotDuplicate).where(
                    NotDuplicate.project_id == project_id,
                    NotDuplicate.record_a_id.in_([p[0] for p in pairs] or [None]),
                )
            )
        ).scalars()
    }
    db.add_all(
        NotDuplicate(project_id=project_id, record_a_id=a, record_b_id=b)
        for a, b in pairs
        if (a, b) not in existing
    )


@router.post("/duplicates/{group_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_group(
    project_id: uuid.UUID,
    group_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Nenhum registro do grupo é duplicata dos outros."""
    await require_lead(db, project_id, user)
    group = await _get_group(db, project_id, group_id)
    ids = list(
        (await db.execute(select(Record.id).where(Record.duplicate_group_id == group.id))).scalars()
    )
    await _mark_not_duplicates(db, project_id, ids, ids)
    for r in (await db.execute(select(Record).where(Record.id.in_(ids)))).scalars():
        r.duplicate_group_id = None
    await db.delete(group)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/duplicates/{group_id}/split", response_model=DuplicateGroupOut | None)
async def split_record(
    project_id: uuid.UUID,
    group_id: uuid.UUID,
    body: SplitIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tira um registro do grupo (ele não é duplicata dos demais)."""
    await require_lead(db, project_id, user)
    group = await _get_group(db, project_id, group_id)
    rec = await db.get(Record, body.record_id)
    if rec is None or rec.duplicate_group_id != group.id:
        raise HTTPException(422, "record_not_in_group")
    others = list(
        (
            await db.execute(
                select(Record).where(Record.duplicate_group_id == group.id, Record.id != rec.id)
            )
        ).scalars()
    )
    await _mark_not_duplicates(db, project_id, [rec.id], [o.id for o in others])
    rec.duplicate_group_id = None
    if len(others) < 2:
        for o in others:
            o.duplicate_group_id = None
        await db.delete(group)
        await db.commit()
        return None
    if group.primary_record_id == rec.id:
        group.primary_record_id = others[0].id
    await db.commit()
    return await _group_out(db, group)


# --- Tarefas -------------------------------------------------------------------


@router.post("/dedup", response_model=JobOut, status_code=202)
async def start_dedup(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_lead(db, project_id, user)
    job = await create_job(db, project_id, "dedup")
    await dispatch(db, job)
    return job


@router.post("/enrich", response_model=JobOut, status_code=202)
async def start_enrich(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_lead(db, project_id, user)
    if not get_settings().enrichment_enabled:
        raise HTTPException(409, "enrichment_disabled")
    running = (
        await db.execute(
            select(Job.id).where(
                Job.project_id == project_id,
                Job.kind == "enrich",
                Job.status.in_(ACTIVE_STATUSES),
            )
        )
    ).first()
    if running:
        raise HTTPException(409, "already_running")
    job = await create_job(db, project_id, "enrich")
    await dispatch(db, job, queue="remote")
    return job


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    project_id: uuid.UUID,
    active: bool = False,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    stmt = select(Job).where(Job.project_id == project_id)
    if active:
        stmt = stmt.where(Job.status.in_(ACTIVE_STATUSES))
    rows = await db.execute(stmt.order_by(Job.created_at.desc()).limit(20))
    return rows.scalars().all()


# Tarefas que sabem parar no meio e guardar o que já fizeram
CANCELLABLE = {"ai_screen"}


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pede para a tarefa parar. Na fila, cancela na hora; rodando, para no próximo registro."""
    await require_lead(db, project_id, user)
    job = await db.get(Job, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(404, "job_not_found")
    if job.kind not in CANCELLABLE:
        raise HTTPException(409, "not_cancellable")
    if job.status == JobStatus.queued:
        job.status = JobStatus.cancelled
        job.finished_at = utcnow()
    elif job.status == JobStatus.running:
        job.status = JobStatus.cancelling
    await db.commit()
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    job = await db.get(Job, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(404, "job_not_found")
    return job
