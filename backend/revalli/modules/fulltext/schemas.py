import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_id: uuid.UUID
    filename: str
    size: int
    pages: int
    source: str
    source_url: str
    is_main: bool
    has_text: bool
    created_at: datetime


class FilesSummary(BaseModel):
    records: int
    with_pdf: int
    without_text: int
    from_open_access: int


class PendingOut(BaseModel):
    """Estudo do texto completo sem PDF, com o que a pessoa precisa para baixar à mão."""

    record_id: uuid.UUID
    title: str
    authors: list[str]
    year: int | None
    journal: str
    doi: str | None
    pmid: str | None
    url: str
    # https://doi.org/..., ou o endereço do registro quando não há DOI
    link: str
    # O mesmo link aberto pelo proxy da instituição (CAFe, EZproxy), se houver modelo salvo
    proxy_link: str


class StudyRecord(BaseModel):
    id: uuid.UUID
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    is_primary: bool
    state: str | None


class StudyOut(BaseModel):
    id: uuid.UUID
    label: str
    reports: list[StudyRecord]


class StudyIn(BaseModel):
    record_ids: list[uuid.UUID] = Field(min_length=2, max_length=50)
    label: str = Field("", max_length=300)


class StudyPatch(BaseModel):
    label: str | None = Field(None, max_length=300)
    primary_record_id: uuid.UUID | None = None


class StudySuggestion(BaseModel):
    key: str
    records: list[StudyRecord]


class StudyCandidate(BaseModel):
    id: uuid.UUID
    title: str
    authors: list[str]
    year: int | None
    study_id: uuid.UUID | None
