import uuid
from typing import Literal

from pydantic import BaseModel, Field

SourceName = Literal["pubmed", "openalex", "europepmc", "scielo", "pepsic"]
Target = Literal[
    "pubmed",
    "openalex",
    "europepmc",
    "scopus",
    "wos",
    "embase",
    "cinahl",
    "psycinfo",
    "cochrane",
    "bvs",
    "scielo",
    "capes",
    "pepsic",
]


class QueryIn(BaseModel):
    source: SourceName
    query: str = Field(min_length=1, max_length=20_000)


class SearchIn(QueryIn):
    limit: int = Field(default=5000, ge=1, le=100_000)


class SampleRecord(BaseModel):
    title: str
    authors: list[str]
    year: int | None
    journal: str
    doi: str | None
    pmid: str | None


class PreviewOut(BaseModel):
    count: int
    max: int
    sample: list[SampleRecord]
    translation: str = ""
    warnings: list[str] = Field(default_factory=list)


class SnowballIn(BaseModel):
    direction: Literal["backward", "forward", "both"] = "both"
    # Vazio: usa os incluídos na fase de texto completo
    record_ids: list[uuid.UUID] = Field(default_factory=list, max_length=2000)


class SnowballInfo(BaseModel):
    included: int
    enabled: bool


class TranslateIn(BaseModel):
    query: str = Field(min_length=1, max_length=20_000)
    target: Target


class AssistMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class AssistIn(BaseModel):
    messages: list[AssistMessage] = Field(min_length=1, max_length=30)


class Strategy(BaseModel):
    base: str
    query: str
    notes: list[str]


class AssistOut(BaseModel):
    reply: str
    strategies: list[Strategy]
    model: str


class TranslateOut(BaseModel):
    query: str
    notes: list[str]
    model: str
