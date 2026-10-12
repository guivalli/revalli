import csv
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import Record, User
from revalli.modules.fulltext import finders, storage, studies
from revalli.modules.fulltext.models import RecordFile, Study
from revalli.modules.fulltext.pdf import PDFError
from revalli.modules.fulltext.schemas import (
    FileOut,
    FilesSummary,
    PendingOut,
    StudyCandidate,
    StudyIn,
    StudyOut,
    StudyPatch,
    StudySuggestion,
)
from revalli.modules.fulltext.service import attach, delete_file, max_pdf_bytes
from revalli.modules.projects.models import Role
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.schemas import JobOut
from revalli.modules.screening.models import Phase
from revalli.modules.screening.service import can_see_others, compute_states
from revalli.modules.sources import keys

router = APIRouter(prefix="/projects/{project_id}", tags=["fulltext"])

UPLOAD_ROLES = {Role.lead, Role.reviewer, Role.arbitrator, Role.extractor}


async def _uploader(db, project_id, user):
    project, role = await get_membership(db, project_id, user)
    if role not in UPLOAD_ROLES and not user.is_admin:
        raise HTTPException(403, "cannot_upload")
    return project


async def _record(db: AsyncSession, project_id: uuid.UUID, record_id: uuid.UUID) -> Record:
    r = await db.get(Record, record_id)
    if r is None or r.project_id != project_id:
        raise HTTPException(404, "record_not_found")
    return r


async def _file(db: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID) -> RecordFile:
    f = await db.get(RecordFile, file_id)
    if f is None or f.project_id != project_id:
        raise HTTPException(404, "file_not_found")
    return f


@router.get("/records/{record_id}/files", response_model=list[FileOut])
async def list_files(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    await _record(db, project_id, record_id)
    rows = await db.execute(
        select(RecordFile)
        .where(RecordFile.record_id == record_id)
        .order_by(RecordFile.is_main.desc(), RecordFile.created_at)
    )
    return rows.scalars().all()


@router.post("/records/{record_id}/files", response_model=FileOut, status_code=201)
async def upload_file(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _uploader(db, project_id, user)
    record = await _record(db, project_id, record_id)
    limit = max_pdf_bytes()
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
    try:
        f = await attach(db, project_id, record, data, file.filename or "", user_id=user.id)
    except PDFError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return f


@router.get("/files/{file_id}/content")
async def file_content(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    f = await _file(db, project_id, file_id)
    path = storage.path_for(project_id, f.sha256)
    if not path.exists():
        raise HTTPException(410, "file_missing")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f.filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/files/{file_id}", status_code=204)
async def remove_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    _, role = await get_membership(db, project_id, user)
    f = await _file(db, project_id, file_id)
    if role != Role.lead and not user.is_admin and f.uploaded_by_id != user.id:
        raise HTTPException(403, "lead_or_uploader_only")
    await delete_file(db, f)


@router.post("/files/{file_id}/main", response_model=FileOut)
async def make_main(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _uploader(db, project_id, user)
    f = await _file(db, project_id, file_id)
    others = await db.execute(select(RecordFile).where(RecordFile.record_id == f.record_id))
    for o in others.scalars():
        o.is_main = o.id == f.id
    await db.commit()
    return f


@router.post("/files/zip", response_model=JobOut, status_code=202)
async def upload_zip(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """ZIP com vários PDFs; cada um é ligado ao registro pelo DOI ou pelo título."""
    await require_lead(db, project_id, user)
    limit = get_settings().max_zip_mb * 1024 * 1024
    tmp = Path(get_settings().data_dir) / "uploads"
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / f"{uuid.uuid4()}.zip"
    size = 0
    with path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
            out.write(chunk)
    job = await create_job(db, project_id, "pdf_zip", {"path": str(path), "user_id": str(user.id)})
    await dispatch(db, job)
    return job


@router.post("/files/open-access", response_model=JobOut, status_code=202)
async def open_access(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_lead(db, project_id, user)
    if not get_settings().enrichment_enabled:
        raise HTTPException(409, "enrichment_disabled")
    job = await create_job(db, project_id, "pdf_oa")
    await dispatch(db, job, queue="remote")
    return job


@router.get("/files/summary", response_model=FilesSummary)
async def summary(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    ids = list(await compute_states(db, project, Phase.full_text))
    row = (
        await db.execute(
            select(
                func.count(func.distinct(RecordFile.record_id)),
                func.count(func.distinct(RecordFile.record_id)).filter(~RecordFile.has_text),
                func.count(func.distinct(RecordFile.record_id)).filter(
                    RecordFile.source == "open_access"
                ),
            ).where(RecordFile.record_id.in_(ids), RecordFile.is_main)
        )
    ).one()
    return FilesSummary(
        records=len(ids), with_pdf=row[0], without_text=row[1], from_open_access=row[2]
    )


async def _pending(db: AsyncSession, project, template: str) -> list[PendingOut]:
    ids = list(await compute_states(db, project, Phase.full_text))
    with_pdf = set(
        (await db.execute(select(RecordFile.record_id).where(RecordFile.record_id.in_(ids))))
        .scalars()
        .all()
    )
    rows = (
        (
            await db.execute(
                select(Record)
                .where(Record.id.in_([i for i in ids if i not in with_pdf]))
                .order_by(Record.year.desc().nulls_last(), Record.title)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for r in rows:
        link = finders.doi_link(r.doi) or r.url
        out.append(
            PendingOut(
                record_id=r.id,
                title=r.title,
                authors=list(r.authors or [])[:3],
                year=r.year,
                journal=r.journal,
                doi=r.doi,
                pmid=r.pmid,
                url=r.url,
                link=link,
                proxy_link=finders.proxy_link(template, link) if template else "",
            )
        )
    return out


@router.get("/files/pending", response_model=list[PendingOut])
async def pending(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Estudos do texto completo ainda sem PDF, com DOI e link para baixar à mão."""
    project, _ = await get_membership(db, project_id, user)
    return await _pending(db, project, await keys.institution_proxy(db))


@router.get("/files/pending.csv")
async def pending_csv(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    rows = await _pending(db, project, await keys.institution_proxy(db))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "authors", "year", "journal", "doi", "pmid", "link", "proxy_link"])

    def safe(value: object) -> str:
        # Texto que vem de bases externas não pode virar fórmula na planilha
        text = str(value)
        return "'" + text if text[:1] in ("=", "+", "-", "@") else text

    for r in rows:
        writer.writerow(
            [
                safe(r.title),
                safe("; ".join(r.authors)),
                r.year or "",
                safe(r.journal),
                r.doi or "",
                r.pmid or "",
                r.link,
                r.proxy_link,
            ]
        )
    return Response(
        # BOM para o Excel abrir os acentos corretamente
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sem-pdf.csv"'},
    )


# --- Estudos com vários relatórios --------------------------------------------------------


async def _study(db: AsyncSession, project_id: uuid.UUID, study_id: uuid.UUID) -> Study:
    s = await db.get(Study, study_id)
    if s is None or s.project_id != project_id:
        raise HTTPException(404, "study_not_found")
    return s


@router.get("/studies", response_model=list[StudyOut])
async def get_studies(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, role = await get_membership(db, project_id, user)
    return await studies.list_studies(db, project, can_see_others(project, role))


@router.get("/studies/suggestions", response_model=list[StudySuggestion])
async def get_study_suggestions(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    return await studies.suggestions(db, project)


@router.get("/studies/candidates", response_model=list[StudyCandidate])
async def get_study_candidates(
    project_id: uuid.UUID,
    q: str = "",
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    return await studies.candidates(db, project, q[:200])


@router.post("/studies", response_model=StudyOut, status_code=201)
async def create_study(
    project_id: uuid.UUID,
    body: StudyIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _uploader(db, project_id, user)
    try:
        study = await studies.group(db, project, body.record_ids, body.label.strip())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return await _study_out(db, project, user, study.id)


@router.patch("/studies/{study_id}", response_model=StudyOut)
async def update_study(
    project_id: uuid.UUID,
    study_id: uuid.UUID,
    body: StudyPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _uploader(db, project_id, user)
    study = await _study(db, project_id, study_id)
    if body.label is not None:
        study.label = body.label.strip()
    if body.primary_record_id is not None:
        try:
            await studies.set_primary(db, study, body.primary_record_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
    await db.commit()
    return await _study_out(db, project, user, study.id)


@router.delete("/studies/{study_id}/reports/{record_id}", status_code=204)
async def remove_report(
    project_id: uuid.UUID,
    study_id: uuid.UUID,
    record_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _uploader(db, project_id, user)
    await studies.ungroup_record(db, await _study(db, project_id, study_id), record_id)
    return Response(status_code=204)


@router.delete("/studies/{study_id}", status_code=204)
async def delete_study(
    project_id: uuid.UUID,
    study_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _uploader(db, project_id, user)
    await db.delete(await _study(db, project_id, study_id))
    await db.commit()
    return Response(status_code=204)


async def _study_out(db: AsyncSession, project, user: User, study_id: uuid.UUID) -> dict:
    _, role = await get_membership(db, project.id, user)
    found = [
        s
        for s in await studies.list_studies(db, project, can_see_others(project, role))
        if s["id"] == study_id
    ]
    if not found:
        # O grupo deixou de existir (ficou com um só relatório)
        raise HTTPException(404, "study_not_found")
    return found[0]
