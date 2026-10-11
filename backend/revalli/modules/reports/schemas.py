from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ~4 MB de PNG por figura
MAX_FIGURE_B64 = 6_000_000


class SourceCount(BaseModel):
    source: str
    method: str = "database"
    records: int


class Identification(BaseModel):
    by_source: list[SourceCount]
    other_methods: list[SourceCount] = []
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
    # Estudos (relatórios do mesmo estudo contam uma vez) e relatórios incluídos
    included: int
    included_reports: int


class DocumentIn(BaseModel):
    format: Literal["docx", "pdf"] = "docx"
    lang: Literal["pt-BR", "en"] = "pt-BR"
    sections: list[
        Literal["methods", "results", "appendix_search", "appendix_ai", "appendix_checklist"]
    ] = Field(
        default_factory=lambda: [
            "methods",
            "results",
            "appendix_search",
            "appendix_ai",
            "appendix_checklist",
        ],
        max_length=5,
    )
    # Figuras desenhadas pela interface, em PNG base64: "prisma" e "meta:<id da análise>"
    figures: dict[str, str] = Field(default_factory=dict, max_length=40)
    # Textos dos itens do checklist no idioma do relatório (ficam no i18n da interface)
    checklist_items: dict[str, str] = Field(default_factory=dict, max_length=80)

    @field_validator("figures")
    @classmethod
    def figure_size(cls, v: dict[str, str]) -> dict[str, str]:
        for key, data in v.items():
            if len(key) > 60 or len(data) > MAX_FIGURE_B64:
                raise ValueError("figure_too_large")
        return v

    @field_validator("checklist_items")
    @classmethod
    def item_size(cls, v: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 10 or len(t) > 2000 for k, t in v.items()):
            raise ValueError("checklist_text_too_long")
        return v
