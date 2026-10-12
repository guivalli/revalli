import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from revalli.modules.screening.schemas import QueueItem

PROVIDER_KINDS = ("ollama", "openai", "anthropic", "google", "openrouter", "custom")


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal[
        "ollama", "openai", "anthropic", "google", "groq", "mistral", "openrouter", "custom"
    ] = "custom"
    base_url: str = Field(min_length=1, max_length=500, pattern=r"^https?://")
    # Vazio mantém a chave atual; use clear_api_key para apagar
    api_key: str = Field(default="", max_length=500)
    clear_api_key: bool = False
    is_local: bool = False
    # Teto de pedidos por minuto (faixas gratuitas); vazio = sem limite
    rpm_limit: int | None = Field(default=None, ge=1, le=1000)


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    base_url: str
    api_key_hint: str
    is_local: bool
    rpm_limit: int | None = None


class TaskModel(BaseModel):
    provider_id: uuid.UUID | None = None
    model: str = Field(default="", max_length=200)
    # Preço em dólares por milhão de tokens (zero para modelos locais)
    price_input: float = Field(default=0, ge=0)
    price_output: float = Field(default=0, ge=0)


class InstanceAISettings(BaseModel):
    screening: TaskModel = TaskModel()
    embeddings: TaskModel = TaskModel()
    extraction: TaskModel = TaskModel()
    # Conversa com o corpus; sem um modelo próprio, usa o da triagem
    chat: TaskModel = TaskModel()


class ProjectAISettings(BaseModel):
    enabled: bool = False
    local_only: bool = False
    mode: Literal["suggest", "second_reviewer"] = "suggest"
    budget_usd: float | None = Field(default=None, ge=0)
    extra_instructions: str = Field(default="", max_length=5000)
    # A IA também sugere até 4 etiquetas por registro
    suggest_tags: bool = True
    # E o motivo principal da exclusão, para agrupar depois
    suggest_reasons: bool = True
    # Quando os revisores veem a sugestão: só depois de decidir (evita ancoragem) ou antes
    reveal_suggestions: Literal["after", "before"] = "after"
    # Ordena a fila pelo que o modelo acha mais provável de ser incluído
    active_learning: bool = False
    # Sugere parar quando tantos registros seguidos forem excluídos
    stop_after_irrelevant: int = Field(default=100, ge=10, le=10_000)


class Criterion(BaseModel):
    criterion: str
    status: Literal["met", "violated", "unclear"]


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: uuid.UUID
    decision: str
    confidence: float | None
    justification: str
    criteria: list[Criterion]
    tags: list[str] = Field(default_factory=list)
    exclusion_reason: str = ""
    model_key: str
    created_at: datetime


class RunIn(BaseModel):
    phase: Literal["title_abstract", "full_text"] = "title_abstract"
    # pending: registros ainda sem decisão; excluded: checa os excluídos por humanos;
    # calibration: amostra já decidida por humanos, para medir a IA
    scope: Literal["pending", "excluded", "calibration"] = "pending"
    limit: int | None = Field(default=None, ge=1, le=100_000)
    # Refaz a análise mesmo onde já há resposta guardada para o mesmo prompt
    force: bool = False


class OrganizeIn(BaseModel):
    inclusion_criteria: str = Field(default="", max_length=20_000)
    exclusion_criteria: str = Field(default="", max_length=20_000)
    # Respostas da equipe às perguntas da rodada anterior
    answers: str = Field(default="", max_length=10_000)


class TagSuggestIn(BaseModel):
    sample: int = Field(default=40, ge=5, le=100)


class ReasonGroupIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    members: list[str] = Field(default_factory=list, max_length=200)


class ApplyReasonsIn(BaseModel):
    groups: list[ReasonGroupIn] = Field(max_length=30)


class Estimate(BaseModel):
    records: int
    cached: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    local: bool
    budget_usd: float | None
    spent_usd: float


class Calibration(BaseModel):
    n: int
    tp: int
    fp: int
    tn: int
    fn: int
    maybe: int
    sensitivity: float | None
    specificity: float | None
    kappa: float | None


class UsageOut(BaseModel):
    spent_usd: float
    input_tokens: int
    output_tokens: int
    calls: int


class FlagOut(BaseModel):
    record: QueueItem
    suggestion: SuggestionOut


class CurvePoint(BaseModel):
    screened: int
    found: int


class Curve(BaseModel):
    total: int
    screened: int
    found: int
    since_last_include: int
    expected_remaining: float | None
    stop_after_irrelevant: int
    should_stop: bool
    prioritized: bool
    points: list[CurvePoint]


class OllamaState(BaseModel):
    """Estado do Ollama do computador. `configured` é falso quando não há auxiliar instalado."""

    configured: bool
    reachable: bool = False
    active: bool = False
    state: str = ""
    enabled: bool = False
    error: str | None = None


class OllamaAction(BaseModel):
    action: Literal["start", "stop"]
