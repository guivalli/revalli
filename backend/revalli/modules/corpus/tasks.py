from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import Project
from revalli.modules.corpus.service import index_project
from revalli.modules.records.jobs import handler
from revalli.modules.records.models import Job


@handler("corpus_index")
async def corpus_index_job(db: AsyncSession, job: Job) -> dict:
    def progress(done: int, total: int) -> None:
        job.progress, job.total = done, total

    project = await db.get(Project, job.project_id)
    return await index_project(db, project, progress=progress)
