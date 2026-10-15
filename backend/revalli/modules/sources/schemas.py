import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from revalli.modules.sources.fields import FIELDS

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


class RowIn(BaseModel):
    """Uma linha do construtor de busca: operador com a linha anterior, termo e campo."""

    op: Literal["AND", "OR", "NOT"] = "AND"
    field: Literal[FIELDS] = "title_abstract"  # type: ignore[valid-type]
    term: str = Field(default="", max_length=5_000)


class QueryIn(BaseModel):
    source: SourceName
    # Texto livre ou linhas do construtor; as linhas valem mais
    query: str = Field(default="", max_length=20_000)
    rows: list[RowIn] | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def _needs_terms(self):
        if not self.query.strip() and not any(r.term.strip() for r in self.rows or []):
            raise ValueError("query_empty")
        return self


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
    # Correções feitas na estratégia para a base entendê-la
    corrections: list[str] = Field(default_factory=list)
    # A estratégia como foi enviada à base (a que fica salva na busca importada)
    strategy: str = ""


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


class Strategy(BaseModel):
    base: str
    query: str
    notes: list[str]


class AssistMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    # Só nas respostas da IA: o que ela propôs e com qual modelo
    strategies: list[Strategy] = Field(default_factory=list, max_length=15)
    model: str = Field(default="", max_length=200)


class AssistIn(BaseModel):
    messages: list[AssistMessage] = Field(min_length=1, max_length=30)


class AssistOut(BaseModel):
    reply: str
    strategies: list[Strategy]
    model: str


class TranslateOut(BaseModel):
    query: str
    notes: list[str]
    model: str


class SourcesSettingsIn(BaseModel):
    """Vazio mantém a chave salva; `clear_openalex_key` apaga."""

    openalex_api_key: str = Field(default="", max_length=200)
    clear_openalex_key: bool = False


class SourcesSettingsOut(BaseModel):
    openalex_key_set: bool
    openalex_key_hint: str
    # De onde vem a chave em uso: "ui" (salva na interface), "env" (OPENALEX_API_KEY) ou "none"
    openalex_key_source: Literal["ui", "env", "none"]


class AssistChat(BaseModel):
    messages: list[AssistMessage]


class SourceFields(BaseModel):
    fields: list[str]
    # Falso quando a base só combina campos diferentes com E (OpenAlex, SciELO, PePSIC)
    or_across_fields: bool
