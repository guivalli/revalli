import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from revalli.modules.records.dedup import run_dedup
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job
from revalli.modules.watches import service
from revalli.modules.watches.models import Watch


@handler("watch_run")
async def watch_run_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    watch = await db.get(Watch, uuid.UUID((job.params or {})["watch_id"]))
    if watch is None:
        return {"error": "watch_not_found"}
    stats = await service.run_watch(db, watch, progress)
    if stats.get("new"):
        stats["dedup"] = await run_dedup(db, watch.project_id)
    return stats
