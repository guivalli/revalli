import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # Vazio = todos os projetos da pessoa
    project_id: uuid.UUID | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    project_id: uuid.UUID | None
    scope: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class TokenCreated(TokenOut):
    # O valor completo só aparece nesta resposta
    token: str
