import uuid

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class AIProvider(IdMixin, TimestampMixin, Base):
    """Um serviço que fala o protocolo de chat compatível com OpenAI (local ou remoto)."""

    __tablename__ = "ai_providers"

    name: Mapped[str] = mapped_column(String(100))
    # Preset usado na interface (ollama, openai, anthropic, google, openrouter, custom)
    kind: Mapped[str] = mapped_column(String(30), default="custom")
    base_url: Mapped[str] = mapped_column(String(500))
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    api_key_hint: Mapped[str] = mapped_column(String(10), default="")
    # Local = roda no próprio servidor; projetos "só local" só usam estes
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)


class InstanceSetting(Base):
    """Configurações da instalação, uma linha por chave."""

    __tablename__ = "instance_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)


class AISuggestion(IdMixin, TimestampMixin, Base):
    """Resposta do modelo para um registro. Serve de cache: o mesmo prompt não é pago duas vezes."""

    __tablename__ = "ai_suggestions"
    __table_args__ = (UniqueConstraint("record_id", "phase", "model_key", "prompt_hash"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), index=True
    )
    phase: Mapped[str] = mapped_column(String(20))
    model_key: Mapped[str] = mapped_column(String(300))
    prompt_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    justification: Mapped[str] = mapped_column(Text, default="")
    criteria: Mapped[list] = mapped_column(JSONB, default=list)
    # Até 4 etiquetas sugeridas para o registro
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # Motivo principal da exclusão, num rótulo curto (vazio quando a IA não exclui)
    exclusion_reason: Mapped[str] = mapped_column(String(200), default="", server_default="")


class AIUsage(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_providers.id", ondelete="SET NULL"), nullable=True
    )
    model: Mapped[str] = mapped_column(String(200))
    task: Mapped[str] = mapped_column(String(30))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class RecordEmbedding(Base):
    """Vetor do título e resumo, guardado como float32 cru (aprendizado ativo)."""

    __tablename__ = "record_embeddings"

    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), primary_key=True
    )
    model_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    text_hash: Mapped[str] = mapped_column(String(64))
    vector: Mapped[bytes] = mapped_column(LargeBinary)
