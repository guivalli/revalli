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
  "criteria": [{{"criterion": "short name of the criterion", "status": "met" | "violated" | "unclear"}}]{tags_format}{reason_format}}}

Review title: {title}

Inclusion criteria:
{inclusion}

Exclusion criteria:
{exclusion}
{extra}{tags}{reason}"""

TAGS_FORMAT = ',\n  "tags": ["up to 4 short tags"]'

REASON_FORMAT = (
    ',\n  "exclusion_reason": "when excluding, the main reason as a short label; else empty"'
)

REASON_RULE = """
Exclusion reason: when you answer "exclude", name the main reason with a short label (up to 6
words) written in {language}, never in another language. Use the same wording for the same kind
of reason, so that similar records get the same label.
"""

TAGS_WITH_VOCABULARY = """
Tags: besides the decision, choose up to 4 tags that describe the record. Use the exact
names from this list:
{vocabulary}
If none of them fits, you may add at most 1 short tag of your own (1 to 3 words, in {language},
plain words, no underscores).
"""

TAGS_FREE = """
Tags: besides the decision, give up to 4 short tags (1 to 3 words, in {language}) that describe
the record, such as its population, intervention, design or theme. Prefer tags that could be
reused across many records. Use plain words, no underscores.
"""

RECORD = """Title: {title}
Year: {year}
Journal: {journal}
Publication type: {ptype}
Language: {language}
Keywords: {keywords}

Abstract:
{abstract}"""


def _items_block(settings: ScreeningSettings, kind: str) -> str:
    lines = []
    for n, item in enumerate((i for i in settings.criteria_items if i.kind == kind), 1):
        line = f"{n}. {item.name}"
        if item.definition:
            line += f": {item.definition}"
        if item.examples:
            line += f" (examples: {'; '.join(item.examples)})"
        lines.append(line)
    return "\n".join(lines)


def criteria_texts(settings: ScreeningSettings) -> tuple[str, str]:
    """Critérios para o prompt: a lista detalhada aprovada, se houver, senão o texto livre."""
    if settings.criteria_items:
        return (
            _items_block(settings, "include") or "(not provided)",
            _items_block(settings, "exclude") or "(not provided)",
        )
    return (
        settings.inclusion_criteria.strip() or "(not provided)",
        settings.exclusion_criteria.strip() or "(not provided)",
    )


def _tags_block(settings: ScreeningSettings, language: str) -> str:
    if not settings.tag_vocabulary:
        return TAGS_FREE.format(language=language)
    vocab = "\n".join(
        f"- {t.name}: {t.description}" if t.description else f"- {t.name}"
        for t in settings.tag_vocabulary
    )
    return TAGS_WITH_VOCABULARY.format(vocabulary=vocab, language=language)


def build_messages(
    project: Project,
    settings: ScreeningSettings,
    record: Record,
    extra_instructions: str = "",
    language: str = "Portuguese",
    suggest_tags: bool = False,
    suggest_reasons: bool = False,
) -> list[dict]:
    extra = (
        f"\nAdditional instructions from the review team:\n{extra_instructions}\n"
        if extra_instructions.strip()
        else ""
    )
    inclusion, exclusion = criteria_texts(settings)
    system = SYSTEM.format(
        review_type=project.review_type or "systematic",
        title=project.title,
        inclusion=inclusion,
        exclusion=exclusion,
        extra=extra,
        language=language,
        tags_format=TAGS_FORMAT if suggest_tags else "",
        tags=_tags_block(settings, language) if suggest_tags else "",
        reason_format=REASON_FORMAT if suggest_reasons else "",
        reason=REASON_RULE.format(language=language) if suggest_reasons else "",
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


# --- Organizar critérios e sugerir etiquetas ---------------------------------------

CRITERIA_SYSTEM = """You help a research team turn the eligibility criteria of a {review_type}
literature review into a precise protocol that a screener can apply to a title and abstract.

Tasks:
1. Split the criteria the team wrote into atomic items, one condition each. Keep the team's
   intent; never add requirements they did not state.
2. For each item write a short name, an operational definition (how to decide from a title and
   abstract) and up to 3 examples or borderline cases (what counts and what does not).
3. List what is ambiguous or missing as questions for the team, at most 6. Do not guess.
   If the team already answered earlier questions, use the answers and do not ask again.

Answer with a single JSON object and nothing else, in this format:
{{"summary": "one or two sentences describing the review question",
  "items": [{{"kind": "include" | "exclude", "name": "...", "definition": "...",
              "examples": ["..."]}}],
  "questions": ["..."]}}
Write everything in {language}."""

CRITERIA_USER = """Review title: {title}
Description: {description}

Inclusion criteria, as written by the team:
{inclusion}

Exclusion criteria, as written by the team:
{exclusion}
{answers}"""

TAGS_SYSTEM = """You help a research team organise the records of a {review_type} literature
review with a small, reusable set of tags (themes, populations, interventions, designs).

You receive the review title, the tags the team already has and a sample of records.
Propose between 6 and 15 tags. Each tag has a short name (1 to 3 words) and a one-sentence
description that tells a screener when to use it. Do not repeat tags the team already has,
except to write the description of one of theirs that has none: in that case use its exact name.
Tags must be mutually distinguishable and cover the sample, not a single record.
Write names as plain words with normal capitalisation and correct accents (for example
"Ensaio clínico randomizado"), never as code-like identifiers with underscores.

Answer with a single JSON object and nothing else, in this format:
{{"tags": [{{"name": "...", "description": "..."}}]}}
Write everything in {language}."""

TAGS_USER = """Review title: {title}

Tags the team already has:
{existing}

Sample of records:
{records}"""


def build_criteria_messages(
    project: Project,
    inclusion: str,
    exclusion: str,
    answers: str = "",
    language: str = "Portuguese",
) -> list[dict]:
    extra = (
        f"\nThe team's answers to earlier questions:\n{answers.strip()}\n"
        if answers.strip()
        else ""
    )
    if not (inclusion.strip() or exclusion.strip()):
        extra += (
            "\nThe team has not written any criteria yet. Propose a reasonable first draft of "
            "inclusion AND exclusion criteria from the review title and description (at least 3 "
            "of each when the topic allows: population or context, concept or exposure, "
            "outcome, study design, language, period), and use the questions to ask what you "
            "could not infer.\n"
        )
    system = CRITERIA_SYSTEM.format(
        review_type=project.review_type or "systematic", language=language
    )
    user = CRITERIA_USER.format(
        title=project.title,
        description=project.description.strip() or "(none)",
        inclusion=inclusion.strip() or "(not provided)",
        exclusion=exclusion.strip() or "(not provided)",
        answers=extra,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_tags_messages(
    project: Project,
    existing: list[tuple[str, str]],
    records: list[Record],
    language: str = "Portuguese",
) -> list[dict]:
    system = TAGS_SYSTEM.format(review_type=project.review_type or "systematic", language=language)
    have = (
        "\n".join(f"- {n}: {d}" if d else f"- {n}" for n, d in existing) if existing else "(none)"
    )
    sample = "\n\n".join(
        f"[{i}] {r.title or '(no title)'}\n{(r.abstract or '').strip()[:600]}"
        for i, r in enumerate(records, 1)
    )
    user = TAGS_USER.format(title=project.title, existing=have, records=sample)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


REASONS_SYSTEM = """You help a research team organise the reasons for excluding records in a
{review_type} literature review.

You receive raw exclusion reasons written by a screening assistant, each with how many records
have it, and the reasons the team already uses. Group the raw reasons into the smallest set of
clear categories (usually 3 to 8). For each group give:
- "label": a short label (up to 6 words, in {language});
- "existing": the exact label of one of the team's existing reasons when the group means the same
  thing, otherwise null;
- "members": the raw reasons of the group, copied exactly.
Every raw reason must appear in exactly one group. Do not merge reasons that a reviewer would
want to count separately.

Answer with a single JSON object and nothing else, in this format:
{{"groups": [{{"label": "...", "existing": null, "members": ["..."]}}]}}"""

REASONS_USER = """Review title: {title}

Reasons the team already uses:
{existing}

Raw exclusion reasons (with record counts):
{raw}"""


def build_reasons_messages(
    project: Project,
    raw: list[tuple[str, int]],
    existing: list[str],
    language: str = "Portuguese",
) -> list[dict]:
    system = REASONS_SYSTEM.format(
        review_type=project.review_type or "systematic", language=language
    )
    user = REASONS_USER.format(
        title=project.title,
        existing="\n".join(f"- {e}" for e in existing) if existing else "(none)",
        raw="\n".join(f"- {label} ({n})" for label, n in raw),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
