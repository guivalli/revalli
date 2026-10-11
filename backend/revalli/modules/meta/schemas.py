import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Measure = Literal["MD", "SMD", "RR", "OR", "RD", "HR", "GENERIC"]
Num = float | None


class DataRow(BaseModel):
    """Dados de um estudo. Contínuos: n, média e DP por grupo. Binários: eventos e total.
    HR: razão de riscos e o IC 95%. Genérico: estimativa e erro padrão."""

    id: str = Field(min_length=1, max_length=40)
    record_id: uuid.UUID | None = None
    label: str = Field(min_length=1, max_length=200)
    subgroup: str = Field(default="", max_length=100)
    n1: Num = None
    mean1: Num = None
    sd1: Num = None
    e1: Num = None
    n2: Num = None
    mean2: Num = None
    sd2: Num = None
    e2: Num = None
    hr: Num = None
    hr_lower: Num = None
    hr_upper: Num = None
    yi: Num = None
    sei: Num = None


class AnalysisIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    outcome: str = Field(default="", max_length=2000)
    measure: Measure
    model: Literal["random", "fixed"] = "random"
    label1: str = Field(default="", max_length=100)
    label2: str = Field(default="", max_length=100)
    lower_favours_1: bool = True
    rows: list[DataRow] = Field(default_factory=list, max_length=500)


class AnalysisOut(AnalysisIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class StudyResult(BaseModel):
    id: str
    label: str
    subgroup: str
    yi: float | None
    se: float | None
    # Na escala de apresentação (exponenciada para RR e OR)
    estimate: float | None
    lower: float | None
    upper: float | None
    weight: float | None
    skipped: str | None
    corrected: bool
    participants: int | None


class PooledOut(BaseModel):
    k: int
    estimate: float
    lower: float
    upper: float
    p: float
    z: float
    q: float
    df: int
    p_q: float | None
    i2: float
    tau2: float
    prediction: tuple[float, float] | None
    participants: int | None


class SubgroupOut(BaseModel):
    name: str
    pooled: PooledOut | None


class ResultOut(BaseModel):
    measure: Measure
    model: str
    log_scale: bool
    studies: list[StudyResult]
    pooled: PooledOut | None
    subgroups: list[SubgroupOut]
    subgroup_test: dict | None
    egger: dict | None


GradeRating = Literal[0, -1, -2]


class GradeDomain(BaseModel):
    rating: int = Field(default=0, ge=-2, le=2)
    reason: str = Field(default="", max_length=2000)


class GradeDomains(BaseModel):
    risk_of_bias: GradeDomain = GradeDomain()
    inconsistency: GradeDomain = GradeDomain()
    indirectness: GradeDomain = GradeDomain()
    imprecision: GradeDomain = GradeDomain()
    publication_bias: GradeDomain = GradeDomain()
    large_effect: GradeDomain = GradeDomain()
    dose_response: GradeDomain = GradeDomain()
    confounding: GradeDomain = GradeDomain()


class GradeIn(BaseModel):
    outcome: str = Field(min_length=1, max_length=300)
    analysis_id: uuid.UUID | None = None
    design: Literal["rct", "observational"] = "rct"
    studies: int | None = Field(default=None, ge=0)
    participants: int | None = Field(default=None, ge=0)
    effect: str = Field(default="", max_length=2000)
    domains: GradeDomains = GradeDomains()
    importance: Literal["critical", "important", "limited"] = "critical"
    comments: str = Field(default="", max_length=5000)


class GradeOut(GradeIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    certainty: Literal["high", "moderate", "low", "very_low"]
    # Dados vindos da meta-análise ligada (quando houver)
    auto: dict | None = None
    suggestions: list[str] = []
