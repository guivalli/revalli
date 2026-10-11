import asyncio
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project
from revalli.modules.fulltext.service import find_open_access, import_zip
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job


def _uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _progress(job: Job):
    def update(done: int, total: int) -> None:
        job.progress, job.total = done, total

    return update


@handler("pdf_zip")
async def pdf_zip_job(db: AsyncSession, job: Job) -> dict:
    path = Path(job.params["path"])
    try:
        project = await db.get(Project, job.project_id)
        return await import_zip(
            db,
            project,
            await asyncio.to_thread(path.read_bytes),
            _uuid(job.params.get("user_id")),
            progress=_progress(job),
        )
    finally:
        await asyncio.to_thread(path.unlink, missing_ok=True)


@handler("pdf_oa")
async def pdf_oa_job(db: AsyncSession, job: Job) -> dict:
    project = await db.get(Project, job.project_id)
    return await find_open_access(db, project, progress=_progress(job))
