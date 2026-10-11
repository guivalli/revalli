from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project
from revalli.modules.ai.active import embed_project
from revalli.modules.ai.service import run_screening
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job
from revalli.modules.screening.models import Phase


@handler("ai_screen")
async def ai_screen_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    project = await db.get(Project, job.project_id)
    p = job.params or {}
    return await run_screening(
        db,
        project,
        Phase(p.get("phase", "title_abstract")),
        p.get("scope", "pending"),
        p.get("limit"),
        progress=progress,
    )


@handler("ai_embed")
async def ai_embed_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    project = await db.get(Project, job.project_id)
    return await embed_project(db, project, progress=progress)
