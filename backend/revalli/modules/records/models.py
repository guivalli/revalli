import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class Search(IdMixin, TimestampMixin, Base):
    """Uma busca em uma base de dados e o arquivo importado dela (registro no padrão PRISMA-S)."""

    __tablename__ = "searches"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(200))
    query: Mapped[str] = mapped_column(Text, default="")
    searched_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str] = mapped_column(String(500), default="")
    file_format: Mapped[str] = mapped_column(String(20), default="")
    reported_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    # database: busca em base de dados; citation_backward/citation_forward: snowballing.
    # O PRISMA 2020 separa as bases dos "outros métodos" na identificação.
    method: Mapped[str] = mapped_column(String(30), default="database", server_default="database")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Record(IdMixin, TimestampMixin, Base):
    """Uma referência bibliográfica importada."""

    __tablename__ = "records"
    __table_args__ = (
        Index("ix_records_project_doi", "project_id", "doi"),
        Index("ix_records_project_pmid", "project_id", "pmid"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    search_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("searches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(Text, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal: Mapped[str] = mapped_column(Text, default="")
    volume: Mapped[str] = mapped_column(String(50), default="")
    issue: Mapped[str] = mapped_column(String(50), default="")
    pages: Mapped[str] = mapped_column(String(50), default="")
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pmid: Mapped[str | None] = mapped_column(String(20), nullable=True)
    url: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    language: Mapped[str] = mapped_column(String(50), default="")
    publication_type: Mapped[str] = mapped_column(String(200), default="")
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Campos preenchidos pelo enriquecimento de metadados (ex.: {"abstract": "openalex"})
    enriched: Mapped[dict] = mapped_column(JSONB, default=dict)
    duplicate_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("duplicate_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )


class DuplicateStatus(enum.StrEnum):
    pending = "pending"
    confirmed = "confirmed"


class DuplicateGroup(IdMixin, TimestampMixin, Base):
    __tablename__ = "duplicate_groups"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=DuplicateStatus.pending)
    method: Mapped[str] = mapped_column(String(20))  # doi, pmid, title
    score: Mapped[int] = mapped_column(Integer, default=100)
    # O registro que fica; os demais do grupo contam como duplicatas removidas
    primary_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("records.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotDuplicate(TimestampMixin, Base):
    """Par de registros marcado como 'não é duplicata', respeitado nas próximas execuções."""

    __tablename__ = "not_duplicates"
    __table_args__ = (UniqueConstraint("record_a_id", "record_b_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    record_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    record_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))


class JobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(IdMixin, TimestampMixin, Base):
    """Tarefa em segundo plano, para a interface acompanhar o progresso."""

    __tablename__ = "jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.queued)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
