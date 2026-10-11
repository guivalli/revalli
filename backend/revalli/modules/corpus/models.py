import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin, utcnow


class Chunk(IdMixin, TimestampMixin, Base):
    """Trecho de uma página de PDF, a unidade que a conversa com o corpus recupera e cita."""

    __tablename__ = "corpus_chunks"
    __table_args__ = (Index("ix_corpus_chunks_tsv", "tsv", postgresql_using="gin"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("record_files.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer)
    # Ordem do trecho dentro do arquivo
    ord: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    # Índice de texto (config "simple": serve para qualquer idioma)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)


class ChunkEmbedding(Base):
    """Vetor de um trecho, em float32 cru, por modelo de embeddings."""

    __tablename__ = "corpus_chunk_embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corpus_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    vector: Mapped[bytes] = mapped_column(LargeBinary)


class CorpusMessage(IdMixin, Base):
    """Uma pergunta e a resposta com as fontes, no histórico pessoal de quem perguntou."""

    __tablename__ = "corpus_messages"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    # Fontes citadas: registro, arquivo, página, trecho, se a citação foi verificada
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    # Pelo menos uma citação conferida no texto do PDF
    grounded: Mapped[bool] = mapped_column(Boolean, default=False)
    # False quando o modelo disse que os trechos não respondem à pergunta
    answerable: Mapped[bool] = mapped_column(Boolean, default=True)
    # Números da resposta que não aparecem nos trechos citados
    unsupported_numbers: Mapped[list] = mapped_column(JSONB, default=list)
    # included (estudos incluídos) ou all (todos os PDFs do projeto)
    scope: Mapped[str] = mapped_column(String(10), default="included")
    model: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
