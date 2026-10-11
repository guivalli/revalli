import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FieldType = Literal[
    "section",
    "text",
    "long_text",
    "number",
    "integer",
    "choice",
    "multi",
    "boolean",
    "table",
    # Risco de viés: pergunta sinalizadora e julgamento de domínio
    "signal",
    "judgement",
]
ID = r"^[a-z][a-z0-9_]{0,39}$"


class ColumnDef(BaseModel):
    id: str = Field(pattern=ID)
    label: str = Field(min_length=1, max_length=200)
    type: Literal["text", "number", "integer"] = "text"


class ShowIf(BaseModel):
    """Condição para o campo aparecer: outro campo tem um dos valores listados.
    Com várias condições, todas precisam valer."""

    field: str = Field(pattern=ID)
    values: list[str] = Field(min_length=1)


class FieldDef(BaseModel):
    id: str = Field(pattern=ID)
    label: str = Field(min_length=1, max_length=500)
    type: FieldType
    help: str = Field("", max_length=2000)
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=50)
    columns: list[ColumnDef] = Field(default_factory=list, max_length=20)
    # Linhas fixas de uma tabela (ex.: "Intervenção", "Controle"); vazia = linhas livres
    rows: list[str] = Field(default_factory=list, max_length=50)
    # A IA pode preencher este campo; a dica entra no prompt
    ai: bool = False
    ai_hint: str = Field("", max_length=1000)
    # Risco de viés
    domain: str = Field("", max_length=40)
    algorithm: str = Field("", max_length=40)
    show_if: list[ShowIf] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _check(self):
        if self.type in ("choice", "multi", "signal", "judgement") and not self.options:
            raise ValueError(f"field {self.id}: options required")
        if self.type == "table" and not self.columns:
            raise ValueError(f"field {self.id}: columns required")
        if len({c.id for c in self.columns}) != len(self.columns):
            raise ValueError(f"field {self.id}: duplicate column ids")
        return self


def check_fields(fields: list[FieldDef]) -> list[FieldDef]:
    ids = [f.id for f in fields]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate field ids")
    known = set(ids)
    for f in fields:
        for cond in f.show_if:
            if cond.field not in known:
                raise ValueError(f"field {f.id}: show_if refers to unknown field")
    return fields


class FormIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["extraction", "rob"] = "extraction"
    fields: list[FieldDef] = Field(default_factory=list, max_length=300)
    extractors: int = Field(2, ge=1, le=3)

    @model_validator(mode="after")
    def _fields(self):
        check_fields(self.fields)
        return self


class FormFromTemplate(BaseModel):
    template: Literal["rob2", "robins_i", "study_characteristics"]
    name: str = Field("", max_length=200)
    extractors: int = Field(2, ge=1, le=3)


class FormOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    template: str
    fields: list[FieldDef]
    version: int
    extractors: int
    created_at: datetime


class Quote(BaseModel):
    text: str = Field(max_length=2000)
    page: int | None = None
    file_id: uuid.UUID | None = None
    score: int | None = None
    verified: bool = False


class ExtractionIn(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    quotes: dict[str, Quote] = Field(default_factory=dict)
    status: Literal["draft", "done"] = "draft"


class ExtractionOut(BaseModel):
    id: uuid.UUID
    kind: str
    user_id: uuid.UUID | None
    user_name: str
    values: dict[str, Any]
    quotes: dict[str, Quote]
    status: str
    form_version: int
    updated_at: datetime
    # Julgamentos calculados pelo algoritmo do instrumento (risco de viés)
    suggested: dict[str, str] = Field(default_factory=dict)


class UnitOut(BaseModel):
    record_id: uuid.UUID
    report_ids: list[uuid.UUID]
    label: str
    title: str
    year: int | None
    done: int
    mine: str | None
    has_ai: bool
    consensus: bool
    # pending, in_progress, ready (todas as extrações feitas), conflict, agreed, resolved
    state: str


class UnitDetail(BaseModel):
    unit: UnitOut
    form: FormOut
    mine: ExtractionOut | None
    others: list[ExtractionOut]
    consensus: ExtractionOut | None
    can_see_others: bool
    can_resolve: bool


class FieldComparison(BaseModel):
    field_id: str
    values: dict[str, Any]
    agree: bool


class Comparison(BaseModel):
    extractions: list[ExtractionOut]
    fields: list[FieldComparison]
    agreed_values: dict[str, Any]


class RobRow(BaseModel):
    record_id: uuid.UUID
    label: str
    judgements: dict[str, str | None]


class RobSummary(BaseModel):
    domains: list[dict[str, str]]
    scale: list[str]
    rows: list[RobRow]


class AIRunIn(BaseModel):
    # Vazio = todos os estudos que ainda não têm extração da IA
    record_ids: list[uuid.UUID] = Field(default_factory=list, max_length=2000)
    overwrite: bool = False
