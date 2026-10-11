import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    query: str
    searched_on: date | None
    notes: str
    file_name: str
    file_format: str
    reported_count: int | None
    imported_count: int
    method: str
    created_at: datetime


class SearchPatch(BaseModel):
    source: str | None = Field(default=None, min_length=1, max_length=200)
    query: str | None = Field(default=None, max_length=50_000)
    searched_on: date | None = None
    notes: str | None = Field(default=None, max_length=20_000)
    reported_count: int | None = Field(default=None, ge=0)


class ImportResult(BaseModel):
    search: SearchOut
    imported: int
    job_id: uuid.UUID | None


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    search_id: uuid.UUID | None
    title: str
    abstract: str
    authors: list[str]
    year: int | None
    journal: str
    volume: str
    issue: str
    pages: str
    doi: str | None
    pmid: str | None
    url: str
    keywords: list[str]
    language: str
    publication_type: str
    enriched: dict
    duplicate_group_id: uuid.UUID | None
    is_duplicate: bool = False
    # Achado por snowballing: direção e registros semente
    citation: dict | None = None


class RecordPage(BaseModel):
    items: list[RecordOut]
    total: int
    page: int
    page_size: int


class DuplicateGroupOut(BaseModel):
    id: uuid.UUID
    status: str
    method: str
    score: int
    primary_record_id: uuid.UUID | None
    records: list[RecordOut]


class DuplicatePage(BaseModel):
    items: list[DuplicateGroupOut]
    total: int


class ConfirmIn(BaseModel):
    primary_record_id: uuid.UUID


class SplitIn(BaseModel):
    record_id: uuid.UUID


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    progress: int
    total: int
    result: dict
    error: str
    created_at: datetime
    finished_at: datetime | None


class SourceCount(BaseModel):
    source: str
    records: int


class Summary(BaseModel):
    records_total: int
    duplicates_removed: int
    records_unique: int
    pending_groups: int
    missing_abstract: int
    by_source: list[SourceCount]
