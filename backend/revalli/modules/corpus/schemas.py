import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    # included: estudos incluídos na fase de texto completo; all: todos os PDFs do projeto
    scope: Literal["included", "all"] = "included"
    # Usa a pergunta e a resposta anteriores como contexto (para "e no grupo controle?")
    follow_up: bool = False


class SourceOut(BaseModel):
    n: int
    record_id: uuid.UUID
    file_id: uuid.UUID
    page: int
    title: str
    authors: list[str]
    year: int | None
    excerpt: str
    quote: str
    score: int
    verified: bool


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer: str
    sources: list[SourceOut]
    grounded: bool
    scope: str
    model: str
    created_at: datetime


class CorpusStatus(BaseModel):
    chunks: int
    pending_files: int
    embedded: int
    embeddings_model: str | None
    chat_model: str | None
    enabled: bool
