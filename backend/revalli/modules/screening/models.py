import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class Phase(enum.StrEnum):
    title_abstract = "title_abstract"
    full_text = "full_text"


class Decision(enum.StrEnum):
    include = "include"
    exclude = "exclude"
    maybe = "maybe"


class ExclusionReason(IdMixin, TimestampMixin, Base):
    __tablename__ = "exclusion_reasons"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class DecisionEvent(IdMixin, TimestampMixin, Base):
    """Cada decisão é um evento imutável. A decisão atual de alguém é o evento mais recente."""

    __tablename__ = "decision_events"
    __table_args__ = (
        Index("ix_decision_events_lookup", "project_id", "phase", "record_id", "user_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    phase: Mapped[str] = mapped_column(String(20))
    # include, exclude, maybe; ou "undo" para retirar a decisão
    decision: Mapped[str] = mapped_column(String(10))
    reason_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    labels: Mapped[list[str]] = mapped_column(JSONB, default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    # Decisão final dada por líder ou árbitro ao resolver um conflito
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
