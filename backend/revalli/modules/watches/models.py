import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class Watch(IdMixin, TimestampMixin, Base):
    """Busca que se repete sozinha (revisão viva) ou fonte externa de referências sincronizada.

    Cada execução traz só o que o projeto ainda não tem e registra uma nova busca."""

    __tablename__ = "watches"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    # api_search: consulta a uma base; feed_url: arquivo (RIS, BibTeX, CSL JSON...) numa URL
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20), default="")
    query: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    # Cabeçalho de autorização da URL (cifrado); vazio = sem autenticação
    secret_enc: Mapped[str] = mapped_column(Text, default="")
    every_days: Mapped[int] = mapped_column(Integer, default=7)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # ok, error ou vazio (nunca rodou)
    last_status: Mapped[str] = mapped_column(String(10), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_new: Mapped[int] = mapped_column(Integer, default=0)
    last_found: Mapped[int] = mapped_column(Integer, default=0)
    total_new: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
