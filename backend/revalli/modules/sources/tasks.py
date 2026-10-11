import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project
from revalli.modules.records.dedup import run_dedup
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job
from revalli.modules.sources import service


def _user(p: dict) -> uuid.UUID | None:
    return uuid.UUID(p["user_id"]) if p.get("user_id") else None


@handler("api_search")
async def api_search_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    p = job.params or {}
    stats = await service.run_api_search(
        db, job.project_id, _user(p), p["source"], p["query"], int(p["limit"]), progress
    )
    stats["dedup"] = await run_dedup(db, job.project_id)
    return stats


@handler("snowball")
async def snowball_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    p = job.params or {}
    project = await db.get(Project, job.project_id)
    ids = [uuid.UUID(x) for x in p.get("record_ids") or []] or None
    stats = await service.run_snowball(db, project, _user(p), p["direction"], ids, progress)
    stats["dedup"] = await run_dedup(db, job.project_id)
    return stats
