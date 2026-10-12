import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WatchIn(BaseModel):
    kind: Literal["api_search", "feed_url"]
    name: str = Field(default="", max_length=200)
    source: Literal["pubmed", "openalex", "europepmc", "scielo", "pepsic", ""] = ""
    query: str = Field(default="", max_length=20_000)
    url: str = Field(default="", max_length=2000, pattern=r"^(https?://.*)?$")
    # Cabeçalho de autorização, por exemplo "Bearer abc"; vazio mantém o atual no PUT
    secret: str = Field(default="", max_length=500)
    clear_secret: bool = False
    every_days: int = Field(default=7, ge=1, le=365)
    enabled: bool = True

    @model_validator(mode="after")
    def _check(self):
        if self.kind == "api_search" and not (self.source and self.query.strip()):
            raise ValueError("source_and_query_required")
        if self.kind == "feed_url" and not self.url:
            raise ValueError("url_required")
        return self


class WatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    name: str
    source: str
    query: str
    url: str
    has_secret: bool = False
    every_days: int
    enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: str
    last_error: str
    last_new: int
    last_found: int
    total_new: int
