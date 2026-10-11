import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from revalli.modules.screening.models import Decision, Phase


def _clean_terms(values: list[str]) -> list[str]:
    seen, out = set(), []
    for v in values:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v[:100])
    return out[:300]


class ScreeningSettings(BaseModel):
    blind: bool = True
    reviewers_title_abstract: int = Field(default=2, ge=1, le=5)
    reviewers_full_text: int = Field(default=2, ge=1, le=5)
    inclusion_criteria: str = Field(default="", max_length=20_000)
    exclusion_criteria: str = Field(default="", max_length=20_000)
    highlight_include: list[str] = Field(default_factory=list)
    highlight_exclude: list[str] = Field(default_factory=list)

    @field_validator("highlight_include", "highlight_exclude")
    @classmethod
    def clean_terms(cls, v: list[str]) -> list[str]:
        return _clean_terms(v)

    def reviewers_for(self, phase: Phase) -> int:
        return (
            self.reviewers_title_abstract
            if phase == Phase.title_abstract
            else self.reviewers_full_text
        )


class ReasonIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class ReasonPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = None
    archived: bool | None = None


class ReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    position: int
    archived: bool


class DecisionIn(BaseModel):
    record_id: uuid.UUID
    decision: Decision | None  # None desfaz a decisão
    reason_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    labels: list[str] = Field(default_factory=list, max_length=30)
    note: str = Field(default="", max_length=10_000)

    @field_validator("labels")
    @classmethod
    def clean_labels(cls, v: list[str]) -> list[str]:
        return _clean_terms(v)


class DecisionOut(BaseModel):
    user_id: uuid.UUID | None
    user_name: str | None = None
    decision: Decision
    reason_ids: list[uuid.UUID]
    labels: list[str]
    note: str
    is_final: bool
    created_at: datetime


class QueueItem(BaseModel):
    id: uuid.UUID
    title: str
    abstract: str
    authors: list[str]
    year: int | None
    journal: str
    doi: str | None
    pmid: str | None
    keywords: list[str]
    publication_type: str
    language: str
    my_decision: DecisionOut | None = None


class Queue(BaseModel):
    items: list[QueueItem]
    remaining: int


class ReviewerProgress(BaseModel):
    user_id: uuid.UUID
    full_name: str
    decided: int
    included: int
    excluded: int
    maybe: int


class Progress(BaseModel):
    phase: Phase
    eligible: int
    included: int
    excluded: int
    conflicts: int
    pending: int
    reviewers_required: int
    blind: bool
    remaining_for_me: int
    reviewers: list[ReviewerProgress]


class ConflictItem(BaseModel):
    record: QueueItem
    decisions: list[DecisionOut]


class ConflictPage(BaseModel):
    items: list[ConflictItem]
    total: int


class ResolveIn(BaseModel):
    record_id: uuid.UUID
    decision: Decision | None  # None reabre o registro
    reason_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=10_000)


class PairAgreement(BaseModel):
    user_a: str
    user_b: str
    n: int
    percent: float | None
    kappa: float | None


class Agreement(BaseModel):
    pairs: list[PairAgreement]


class ScreenedItem(BaseModel):
    record: QueueItem
    state: str
    decisions: list[DecisionOut]


class ScreenedPage(BaseModel):
    items: list[ScreenedItem]
    total: int
