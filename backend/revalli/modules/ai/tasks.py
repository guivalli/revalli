from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project
from revalli.modules.ai.active import embed_project
from revalli.modules.ai.protocol import organize_criteria, organize_reasons, suggest_tags
from revalli.modules.ai.service import run_screening
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job, JobStatus
from revalli.modules.screening.models import Phase


@handler("ai_screen")
async def ai_screen_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    async def stop_requested() -> bool:
        # O botão "Parar" muda o status do job; relê do banco entre um registro e outro
        await db.refresh(job, ["status"])
        return job.status == JobStatus.cancelling

    project = await db.get(Project, job.project_id)
    p = job.params or {}
    return await run_screening(
        db,
        project,
        Phase(p.get("phase", "title_abstract")),
        p.get("scope", "pending"),
        p.get("limit"),
        progress=progress,
        force=bool(p.get("force", False)),
        should_stop=stop_requested,
    )


@handler("ai_embed")
async def ai_embed_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    project = await db.get(Project, job.project_id)
    return await embed_project(db, project, progress=progress)


@handler("ai_criteria")
async def ai_criteria_job(db: AsyncSession, job: Job) -> dict:
    project = await db.get(Project, job.project_id)
    p = job.params or {}
    return await organize_criteria(
        db,
        project,
        p.get("inclusion_criteria", ""),
        p.get("exclusion_criteria", ""),
        p.get("answers", ""),
    )


@handler("ai_tags")
async def ai_tags_job(db: AsyncSession, job: Job) -> dict:
    project = await db.get(Project, job.project_id)
    return await suggest_tags(db, project, int((job.params or {}).get("sample", 40)))


@handler("ai_reasons")
async def ai_reasons_job(db: AsyncSession, job: Job) -> dict:
    project = await db.get(Project, job.project_id)
    return await organize_reasons(db, project)
