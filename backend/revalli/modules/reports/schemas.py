from pydantic import BaseModel


class SourceCount(BaseModel):
    source: str
    records: int


class Identification(BaseModel):
    by_source: list[SourceCount]
    total: int
    duplicates_removed: int


class ScreeningCounts(BaseModel):
    screened: int
    excluded: int
    pending: int


class Retrieval(BaseModel):
    sought: int
    not_retrieved: int


class ReasonCount(BaseModel):
    reason: str | None
    count: int


class Eligibility(BaseModel):
    assessed: int
    excluded: int
    reasons: list[ReasonCount]
    pending: int


class Prisma(BaseModel):
    identification: Identification
    screening: ScreeningCounts
    retrieval: Retrieval
    eligibility: Eligibility
    included: int
