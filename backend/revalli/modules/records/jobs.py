"""Execução de tarefas em segundo plano.

A API cria um Job e o despacha para o worker (Celery). Nos testes, ou com
JOBS_INLINE=true, a tarefa roda na própria requisição.
"""

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from revalli.core.config import get_settings
from revalli.core.db import utcnow
from revalli.modules.records.models import Job, JobStatus

JobHandler = Callable[[AsyncSession, Job], Awaitable[dict]]
HANDLERS: dict[str, JobHandler] = {}


def handler(kind: str):
    def register(fn: JobHandler) -> JobHandler:
        HANDLERS[kind] = fn
        return fn

    return register


async def create_job(
    db: AsyncSession, project_id: uuid.UUID, kind: str, params: dict | None = None
) -> Job:
    """Cria um job; se já houver um igual na fila (ainda não iniciado), reaproveita."""
    params = params or {}
    queued = (
        (
            await db.execute(
                select(Job).where(
                    Job.project_id == project_id, Job.kind == kind, Job.status == JobStatus.queued
                )
            )
        )
        .scalars()
        .all()
    )
    same = next((j for j in queued if (j.params or {}) == params), None)
    if same is not None and not get_settings().jobs_inline:
        return same
    job = Job(project_id=project_id, kind=kind, params=params)
    db.add(job)
    await db.commit()
    return job


async def execute(db: AsyncSession, job_id: uuid.UUID) -> None:
    # Garante que os handlers foram registrados
    from revalli.modules.ai import tasks as ai_tasks  # noqa: F401
    from revalli.modules.records import tasks  # noqa: F401

    # Reivindica o job de forma atômica para que duas execuções não rodem o mesmo
    claimed = await db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.queued)
        .values(status=JobStatus.running)
        .returning(Job.id)
    )
    got_it = claimed.first() is not None
    await db.commit()
    if not got_it:
        return
    job = await db.get(Job, job_id, populate_existing=True)
    try:
        job.result = await HANDLERS[job.kind](db, job)
        job.status = JobStatus.done
    except Exception as exc:  # registra a falha para a interface mostrar
        await db.rollback()
        job = await db.get(Job, job_id)
        job.status = JobStatus.failed
        job.error = f"{type(exc).__name__}: {exc}"[:2000]
    job.finished_at = utcnow()
    await db.commit()


async def execute_isolated(job_id: uuid.UUID) -> None:
    """Roda um job com engine própria (usado pelo worker, que abre um loop por tarefa)."""
    import revalli.models  # noqa: F401  (registra todas as tabelas no metadata)

    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            await execute(db, job_id)
    finally:
        await engine.dispose()


async def dispatch(db: AsyncSession, job: Job, queue: str = "default") -> None:
    if get_settings().jobs_inline:
        await execute(db, job.id)
        await db.refresh(job)
        return
    from revalli.workers.celery_app import run_job

    run_job.apply_async(args=[str(job.id)], queue=queue)
