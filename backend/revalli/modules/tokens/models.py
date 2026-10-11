import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class ApiToken(IdMixin, TimestampMixin, Base):
    """Chave de acesso à API, só leitura. Age como a pessoa que a criou, com o mesmo cegamento.

    Guarda só o hash; o valor aparece uma única vez, ao criar."""

    __tablename__ = "api_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Vazio = todos os projetos da pessoa
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Primeiros caracteres, para a pessoa reconhecer a chave na lista
    prefix: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(10), default="read")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
