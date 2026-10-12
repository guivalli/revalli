import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin, utcnow


class SearchAssistantChat(IdMixin, TimestampMixin, Base):
    """Conversa de uma pessoa com o assistente de busca num projeto (uma por pessoa e projeto)."""

    __tablename__ = "search_assistant_chats"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_assistant_chat_owner"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Lista de {role, content, strategies, model}
    messages: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
