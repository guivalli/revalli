import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class MetaAnalysis(IdMixin, TimestampMixin, Base):
    """Uma meta-análise de um desfecho, com os dados de cada estudo em JSON."""

    __tablename__ = "meta_analyses"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(Text, default="")
    # MD, SMD, RR, OR, RD ou GENERIC
    measure: Mapped[str] = mapped_column(String(10))
    # random ou fixed
    model: Mapped[str] = mapped_column(String(10), default="random")
    label1: Mapped[str] = mapped_column(String(100), default="")
    label2: Mapped[str] = mapped_column(String(100), default="")
    # Em desfechos como mortalidade, valores menores favorecem a intervenção
    lower_favours_1: Mapped[bool] = mapped_column(default=True)
    rows: Mapped[list] = mapped_column(JSONB, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)


class GradeRow(IdMixin, TimestampMixin, Base):
    """Uma linha da tabela de resumo dos achados (GRADE)."""

    __tablename__ = "grade_rows"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meta_analyses.id", ondelete="SET NULL"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String(300))
    # rct ou observational
    design: Mapped[str] = mapped_column(String(20), default="rct")
    studies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effect: Mapped[str] = mapped_column(Text, default="")
    domains: Mapped[dict] = mapped_column(JSONB, default=dict)
    # critical, important ou limited
    importance: Mapped[str] = mapped_column(String(20), default="critical")
    comments: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
