from collections.abc import Callable

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from revalli.core.config import get_settings
from revalli.models import Job
from revalli.modules.watches import service
from revalli.modules.watches.models import Watch


async def dispatch_due(send: Callable[[str], object]) -> int:
    """Um job por atualização vencida. Adia o próximo horário já aqui, para que uma passada
    seguinte do agendador não crie o mesmo job de novo enquanto este ainda está na fila."""
    import revalli.models  # noqa: F401  (registra as tabelas)

    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            sent: list[str] = []
            for wid in await service.due_watch_ids(db):
                watch = await db.get(Watch, wid)
                service.schedule_next(watch)
                job = Job(
                    project_id=watch.project_id, kind="watch_run", params={"watch_id": str(wid)}
                )
                db.add(job)
                await db.flush()
                sent.append(str(job.id))
            await db.commit()
    finally:
        await engine.dispose()
    for job_id in sent:
        send(job_id)
    return len(sent)
