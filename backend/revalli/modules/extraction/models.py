import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin, utcnow


class ExtractionForm(IdMixin, TimestampMixin, Base):
    """Formulário de extração de dados ou de risco de viés de um projeto.

    Os campos ficam em JSON (ver ``schemas.FieldDef``). Cada alteração gera uma versão nova,
    guardada em ``FormVersion``; as respostas ficam ligadas ao id de cada campo, então mudar a
    ordem ou o rótulo de um campo não perde nada."""

    __tablename__ = "extraction_forms"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    # extraction ou rob (risco de viés)
    kind: Mapped[str] = mapped_column(String(20), default="extraction")
    # Modelo de origem (rob2, robins_i) ou vazio
    template: Mapped[str] = mapped_column(String(30), default="")
    fields: Mapped[list] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Quantas pessoas extraem cada estudo de forma independente
    extractors: Mapped[int] = mapped_column(Integer, default=2)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class FormVersion(Base):
    __tablename__ = "extraction_form_versions"

    form_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_forms.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    fields: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Extraction(IdMixin, TimestampMixin, Base):
    """Respostas de uma pessoa (ou da IA, ou o consenso) para um estudo num formulário.

    O estudo é representado pelo registro do relatório principal."""

    __tablename__ = "extractions"
    __table_args__ = (
        Index(
            "uq_extractions_unit",
            "form_id",
            "record_id",
            "kind",
            "user_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_forms.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # reviewer, ai ou consensus
    kind: Mapped[str] = mapped_column(String(12), default="reviewer")
    values: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Por campo: {"text", "page", "file_id", "score", "verified"}
    quotes: Mapped[dict] = mapped_column(JSONB, default=dict)
    # draft ou done
    status: Mapped[str] = mapped_column(String(10), default="draft")
    form_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
