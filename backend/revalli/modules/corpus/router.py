import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.db import get_db
from revalli.core.deps import current_user, get_membership, require_lead
from revalli.models import User
from revalli.modules.ai.client import AIError
from revalli.modules.ai.router import _ai_error
from revalli.modules.ai.service import project_ai
from revalli.modules.corpus import service
from revalli.modules.corpus.models import CorpusMessage
from revalli.modules.corpus.schemas import AskIn, CorpusStatus, MessageOut
from revalli.modules.records.jobs import create_job, dispatch
from revalli.modules.records.schemas import JobOut

router = APIRouter(prefix="/projects/{project_id}/corpus", tags=["corpus"])

HISTORY = 50


@router.get("/status", response_model=CorpusStatus)
async def status(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    project, _ = await get_membership(db, project_id, user)
    return await service.status(db, project)


@router.post("/index", response_model=JobOut, status_code=202)
async def index(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Divide o texto dos PDFs em trechos (e calcula os embeddings, se houver modelo)."""
    project = await require_lead(db, project_id, user)
    emb = await service.embeddings_model(db, project_ai(project).local_only)
    job = await create_job(db, project_id, "corpus_index")
    await dispatch(db, job, queue="gpu" if emb and emb.provider.is_local else "remote")
    return job


@router.post("/ask", response_model=MessageOut)
async def ask(
    project_id: uuid.UUID,
    body: AskIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    project, _ = await get_membership(db, project_id, user)
    if not project_ai(project).enabled:
        raise HTTPException(409, "ai_disabled")
    if (await service.status(db, project))["chunks"] == 0:
        raise HTTPException(409, "corpus_not_indexed")
    try:
        return await service.ask(db, project, user, body.question, body.scope, body.follow_up)
    except AIError as exc:
        raise _ai_error(exc) from exc
    except service.CorpusError as exc:
        raise HTTPException(409, f"ai_{exc}") from exc


@router.get("/messages", response_model=list[MessageOut])
async def messages(
    project_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Histórico pessoal: cada pessoa vê só as próprias perguntas."""
    await get_membership(db, project_id, user)
    rows = (
        (
            await db.execute(
                select(CorpusMessage)
                .where(CorpusMessage.project_id == project_id, CorpusMessage.user_id == user.id)
                .order_by(CorpusMessage.created_at.desc())
                .limit(HISTORY)
            )
        )
        .scalars()
        .all()
    )
    return list(reversed(rows))


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(
    project_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_membership(db, project_id, user)
    msg = await db.get(CorpusMessage, message_id)
    if msg is None or msg.project_id != project_id or msg.user_id != user.id:
        raise HTTPException(404, "message_not_found")
    await db.delete(msg)
    await db.commit()
