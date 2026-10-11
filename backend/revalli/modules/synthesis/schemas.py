import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CodeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    description: str = Field(default="", max_length=5000)
    color: str = Field(default="", max_length=20, pattern=r"^(#[0-9a-fA-F]{6})?$")


class CodePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    color: str | None = Field(default=None, max_length=20, pattern=r"^(#[0-9a-fA-F]{6})?$")
    # Mover na árvore: null leva para a raiz; omitido mantém
    parent_id: uuid.UUID | None = None
    move: bool = False
    position: int | None = Field(default=None, ge=0)


class CodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    description: str
    color: str
    position: int
    excerpts: int = 0


class MergeIn(BaseModel):
    into: uuid.UUID


class ExcerptIn(BaseModel):
    record_id: uuid.UUID
    text: str = Field(min_length=1, max_length=20_000)
    file_id: uuid.UUID | None = None
    page: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=10_000)
    code_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class ExcerptPatch(BaseModel):
    note: str | None = Field(default=None, max_length=10_000)
    code_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=50)


class ExcerptOut(BaseModel):
    id: uuid.UUID
    record_id: uuid.UUID
    study: str
    file_id: uuid.UUID | None
    # Relatório (registro) a que o PDF pertence, para abrir o arquivo certo
    file_record_id: uuid.UUID | None = None
    page: int | None
    text: str
    note: str
    code_ids: list[uuid.UUID]
    user_id: uuid.UUID | None
    user_name: str
    created_at: datetime


class CodingUnit(BaseModel):
    record_id: uuid.UUID
    label: str
    report_ids: list[uuid.UUID]
    title: str
    year: int | None
    excerpts: int
    has_pdf: bool


class Matrix(BaseModel):
    units: list[CodingUnit]
    # code_id -> record_id -> número de trechos
    cells: dict[str, dict[str, int]]


ChecklistKind = Literal["prisma2020", "prisma_scr"]
ItemStatus = Literal["pending", "done", "na"]


class ChecklistEntryIn(BaseModel):
    status: ItemStatus = "pending"
    location: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=5000)


class ChecklistEntryOut(ChecklistEntryIn):
    item: str
    updated_at: datetime | None = None


class ChecklistOut(BaseModel):
    checklist: ChecklistKind
    entries: list[ChecklistEntryOut]
    # Dados do projeto que ajudam a preencher os itens de métodos e resultados
    facts: dict
