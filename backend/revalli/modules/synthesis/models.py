import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin, utcnow


class Code(IdMixin, TimestampMixin, Base):
    """Código (tema ou categoria) da síntese qualitativa. Códigos formam uma árvore."""

    __tablename__ = "codes"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("codes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(20), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Excerpt(IdMixin, TimestampMixin, Base):
    """Trecho de um estudo incluído, marcado com um ou mais códigos.

    O estudo é representado pelo registro do relatório principal, como na extração."""

    __tablename__ = "excerpts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("record_files.id", ondelete="SET NULL"), nullable=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ExcerptCode(Base):
    __tablename__ = "excerpt_codes"

    excerpt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("excerpts.id", ondelete="CASCADE"), primary_key=True
    )
    code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("codes.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class ChecklistEntry(Base):
    """Onde cada item de um checklist de relato (PRISMA 2020, PRISMA-ScR) foi atendido."""

    __tablename__ = "checklist_entries"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    checklist: Mapped[str] = mapped_column(String(20), primary_key=True)
    item: Mapped[str] = mapped_column(String(10), primary_key=True)
    # pending, done ou na (não se aplica)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    location: Mapped[str] = mapped_column(String(300), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
