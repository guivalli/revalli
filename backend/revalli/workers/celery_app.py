from celery import Celery

from revalli.core.config import get_settings

settings = get_settings()

celery_app = Celery("revalli", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    # Filas previstas: "gpu" (modelos locais, concorrência baixa) e "remote" (APIs externas)
    task_routes={},
    timezone="UTC",
)


@celery_app.task(name="revalli.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="revalli.run_job")
def run_job(job_id: str) -> None:
    import asyncio
    import uuid

    from revalli.modules.records.jobs import execute_isolated

    asyncio.run(execute_isolated(uuid.UUID(job_id)))
