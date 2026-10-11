import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project
from revalli.modules.extraction import ai
from revalli.modules.extraction.models import ExtractionForm
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job


@handler("ai_extract")
async def ai_extract_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    p = job.params or {}
    project = await db.get(Project, job.project_id)
    form = await db.get(ExtractionForm, uuid.UUID(p["form_id"]))
    ids = [uuid.UUID(x) for x in p.get("record_ids") or []] or None
    return await ai.run(db, project, form, ids, bool(p.get("overwrite")), progress=progress)
