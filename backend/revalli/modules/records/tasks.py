from sqlalchemy.ext.asyncio import AsyncSession

from revalli.modules.records.dedup import run_dedup
from revalli.modules.records.enrich import enrich_project
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job


@handler("dedup")
async def dedup_job(db: AsyncSession, job: Job) -> dict:
    return await run_dedup(db, job.project_id)


@handler("enrich")
async def enrich_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    stats = await enrich_project(db, job.project_id, progress=progress)
    # O enriquecimento pode trazer DOIs novos, então recalcula as duplicatas
    stats["dedup"] = await run_dedup(db, job.project_id)
    return stats
