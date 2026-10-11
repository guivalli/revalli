"""Prompts da triagem. Ficam em inglês porque os modelos seguem melhor instruções em inglês;
os critérios e os textos dos registros vão no idioma em que foram escritos."""

import hashlib

from revalli.models import Project, Record
from revalli.modules.screening.schemas import ScreeningSettings

SYSTEM = """You are a careful reviewer screening records for a {review_type} literature review.
Decide whether the record should be included based ONLY on the eligibility criteria below.

Rules:
- Screening must favour recall: if the title and abstract do not give enough information to
  exclude with confidence, answer "maybe" (or "include" when it looks relevant).
- Exclude only when at least one exclusion criterion is clearly met or an inclusion criterion
  is clearly violated.
- Do not use knowledge about the paper beyond what is written in the record.
- Answer with a single JSON object and nothing else, in this format:
{{"decision": "include" | "exclude" | "maybe",
  "confidence": number between 0 and 1,
  "justification": "one or two sentences, in {language}",
  "criteria": [{{"criterion": "short name of the criterion", "status": "met" | "violated" | "unclear"}}]}}

Review title: {title}

Inclusion criteria:
{inclusion}

Exclusion criteria:
{exclusion}
{extra}"""

RECORD = """Title: {title}
Year: {year}
Journal: {journal}
Publication type: {ptype}
Language: {language}
Keywords: {keywords}

Abstract:
{abstract}"""


def build_messages(
    project: Project,
    settings: ScreeningSettings,
    record: Record,
    extra_instructions: str = "",
    language: str = "Portuguese",
) -> list[dict]:
    extra = (
        f"\nAdditional instructions from the review team:\n{extra_instructions}\n"
        if extra_instructions.strip()
        else ""
    )
    system = SYSTEM.format(
        review_type=project.review_type or "systematic",
        title=project.title,
        inclusion=settings.inclusion_criteria.strip() or "(not provided)",
        exclusion=settings.exclusion_criteria.strip() or "(not provided)",
        extra=extra,
        language=language,
    )
    user = RECORD.format(
        title=record.title or "(no title)",
        year=record.year or "unknown",
        journal=record.journal or "unknown",
        ptype=record.publication_type or "unknown",
        language=record.language or "unknown",
        keywords="; ".join(record.keywords) or "none",
        abstract=record.abstract.strip() or "(no abstract available)",
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def prompt_hash(messages: list[dict]) -> str:
    h = hashlib.sha256()
    for m in messages:
        h.update(m["role"].encode())
        h.update(b"\0")
        h.update(m["content"].encode())
        h.update(b"\0")
    return h.hexdigest()


def estimate_tokens(messages: list[dict]) -> int:
    # Aproximação de 4 caracteres por token, suficiente para a estimativa de custo
    return sum(len(m["content"]) for m in messages) // 4 + 8
