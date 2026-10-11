"""Extração por IA com citação literal.

O modelo recebe o texto do PDF com marcadores de página e devolve, para cada campo, o valor e
um trecho copiado do artigo. O trecho é procurado no texto das páginas: se for encontrado com
semelhança alta, a resposta fica marcada como verificada e pode ser destacada no PDF; se não,
fica como "não verificada" para a pessoa conferir."""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import AIUsage, Project
from revalli.modules.ai import client
from revalli.modules.ai.prompts import estimate_tokens
from revalli.modules.ai.service import bot_user, project_ai, resolve, spent
from revalli.modules.extraction import service
from revalli.modules.extraction.models import Extraction, ExtractionForm
from revalli.modules.fulltext.models import FilePage, RecordFile

QUOTE_MIN_SCORE = 90
MAX_DOC_CHARS = 60_000
FIELDS_PER_CALL = 12
OUTPUT_TOKENS_PER_FIELD = 120

SYSTEM = """You extract data from a scientific article for a literature review.
The article text is given with page markers like [[page 3]].

For each requested field, answer with the value reported in the article and a short quote
copied VERBATIM from the text that supports it (one sentence or less, do not paraphrase,
do not fix typos), with the page where the quote is.
If the article does not report the field, use null for value and quote.
Use only the article text. Do not guess.

Field types:
- text/long_text: a string, in the language of the article.
- number/integer: a number without units.
- choice: exactly one of the listed options.
- multi: a list with some of the listed options.
- boolean: true or false.
- table: a list of objects with the listed column ids as keys.
- signal: one of Y (yes), PY (probably yes), PN (probably no), N (no), NI (no information).

Answer with a single JSON object and nothing else:
{"fields": {"<field id>": {"value": ..., "quote": "..." | null, "page": number | null}}}"""


@dataclass
class Page:
    file_id: uuid.UUID
    page: int
    text: str


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def locate_quote(quote: str, pages: list[Page]) -> dict | None:
    """Procura o trecho nas páginas. Devolve página, arquivo e semelhança (0 a 100)."""
    q = _norm(quote)
    if len(q) < 8:
        return None
    best: dict | None = None
    for p in pages:
        text = _norm(p.text)
        if not text:
            continue
        score = 100 if q in text else int(fuzz.partial_ratio(q, text))
        if best is None or score > best["score"]:
            best = {"file_id": str(p.file_id), "page": p.page, "score": score}
            if score == 100:
                break
    return best


async def unit_pages(db: AsyncSession, report_ids: list[uuid.UUID]) -> list[Page]:
    """Páginas dos PDFs dos relatórios do estudo, com o arquivo principal de cada um primeiro."""
    rows = await db.execute(
        select(RecordFile.id, RecordFile.record_id, FilePage.page, FilePage.text)
        .join(FilePage, FilePage.file_id == RecordFile.id)
        .where(RecordFile.record_id.in_(report_ids), RecordFile.has_text)
        .order_by(RecordFile.is_main.desc(), RecordFile.created_at, FilePage.page)
    )
    order = {rid: i for i, rid in enumerate(report_ids)}
    found = sorted(rows.all(), key=lambda r: order.get(r[1], len(order)))  # sort estável
    return [Page(fid, page, text) for fid, _, page, text in found]


def document_text(pages: list[Page], limit: int = MAX_DOC_CHARS) -> str:
    parts, size, last_file = [], 0, None
    for p in pages:
        if p.file_id != last_file:
            if last_file is not None:
                parts.append("\n[[another report of the same study]]\n")
            last_file = p.file_id
        chunk = f"\n[[page {p.page}]]\n{p.text.strip()}\n"
        if size + len(chunk) > limit:
            parts.append("\n[[text truncated]]\n")
            break
        parts.append(chunk)
        size += len(chunk)
    return "".join(parts)


def field_spec(f: dict) -> dict:
    spec = {"id": f["id"], "label": f["label"], "type": f["type"]}
    if f.get("options") and f["type"] != "judgement":
        spec["options"] = f["options"]
    if f.get("columns"):
        spec["columns"] = [
            {"id": c["id"], "label": c["label"], "type": c["type"]} for c in f["columns"]
        ]
    if f.get("rows"):
        spec["rows"] = f["rows"]
    hint = " ".join(x for x in (f.get("help", ""), f.get("ai_hint", "")) if x)
    if hint:
        spec["hint"] = hint
    return spec


def build_messages(fields: list[dict], document: str, title: str, extra: str = "") -> list[dict]:
    system = SYSTEM + (
        f"\n\nAdditional instructions from the review team:\n{extra}" if extra.strip() else ""
    )
    user = (
        f"Article: {title}\n\nFields:\n{json.dumps([field_spec(f) for f in fields], ensure_ascii=False)}"
        f"\n\nArticle text:\n{document}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def ai_fields(form: ExtractionForm) -> list[dict]:
    return [f for f in form.fields if f.get("ai") and f["type"] not in ("section", "judgement")]


def parse_answer(fields: list[dict], data: dict, pages: list[Page]) -> tuple[dict, dict]:
    answers = data.get("fields") if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        raise client.AIError("invalid_answer")
    values, quotes = {}, {}
    for f in fields:
        a = answers.get(f["id"])
        if not isinstance(a, dict):
            continue
        try:
            v = service.clean_value(f, a.get("value"))
        except service.FieldError:
            continue
        if v is None:
            continue
        values[f["id"]] = v
        quote = a.get("quote")
        if isinstance(quote, str) and quote.strip():
            found = locate_quote(quote, pages)
            quotes[f["id"]] = {
                "text": quote.strip()[:2000],
                "page": found["page"] if found else None,
                "file_id": found["file_id"] if found else None,
                "score": found["score"] if found else 0,
                "verified": bool(found and found["score"] >= QUOTE_MIN_SCORE),
            }
    return values, quotes


async def extract_unit(
    db: AsyncSession,
    project: Project,
    form: ExtractionForm,
    unit: service.Unit,
    res,
    bot_id: uuid.UUID,
) -> Extraction | None:
    pages = await unit_pages(db, unit.report_ids)
    if not pages:
        return None
    document = document_text(pages)
    fields = ai_fields(form)
    extra = project_ai(project).extra_instructions
    values, quotes = {}, {}
    for start in range(0, len(fields), FIELDS_PER_CALL):
        batch = fields[start : start + FIELDS_PER_CALL]
        result = await client.chat(
            res.endpoint, build_messages(batch, document, unit.record.title, extra)
        )
        db.add(
            AIUsage(
                project_id=project.id,
                provider_id=res.provider.id,
                model=res.choice.model,
                task="extraction",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=res.cost(result.input_tokens, result.output_tokens),
            )
        )
        v, q = parse_answer(batch, client.parse_json(result.content), pages)
        values |= v
        quotes |= q
    # Respeita a lógica condicional do formulário
    values = service.clean_values(form.fields, values)
    quotes = {k: q for k, q in quotes.items() if k in values}
    ext = next((e for e in unit.extractions if e.kind == "ai"), None)
    if ext is None:
        ext = Extraction(
            project_id=project.id,
            form_id=form.id,
            record_id=unit.record.id,
            kind="ai",
            user_id=bot_id,
        )
        db.add(ext)
    ext.values, ext.quotes, ext.status, ext.form_version = values, quotes, "done", form.version
    return ext


def estimate(form: ExtractionForm, chars: int) -> tuple[int, int]:
    calls = max(1, -(-len(ai_fields(form)) // FIELDS_PER_CALL))
    inp = calls * (estimate_tokens([{"content": SYSTEM}]) + chars // 4 + 400)
    return inp, len(ai_fields(form)) * OUTPUT_TOKENS_PER_FIELD


async def run(
    db: AsyncSession,
    project: Project,
    form: ExtractionForm,
    record_ids: list[uuid.UUID] | None,
    overwrite: bool,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    ai = project_ai(project)
    res = await resolve(db, "extraction", ai.local_only)
    bot = await bot_user(db)
    us = await service.units(db, project)
    if record_ids:
        wanted = set(record_ids)
        us = [u for u in us if u.record.id in wanted]
    exts = await service.load_extractions(db, form, [u.record.id for u in us])
    for u in us:
        u.extractions = exts.get(u.record.id, [])
    todo = [u for u in us if overwrite or not any(e.kind == "ai" for e in u.extractions)]
    stats = {"total": len(todo), "done": 0, "no_pdf": 0, "errors": 0, "stopped": None}
    used = await spent(db, project.id)
    for i, u in enumerate(todo, 1):
        if ai.budget_usd is not None:
            inp, out = estimate(form, MAX_DOC_CHARS)
            if used + res.cost(inp, out) > ai.budget_usd:
                stats["stopped"] = "budget"
                break
        try:
            ext = await extract_unit(db, project, form, u, res, bot.id)
        except client.AIError as exc:
            stats["errors"] += 1
            stats["last_error"] = str(exc)[:300]
            await db.commit()
            continue
        if ext is None:
            stats["no_pdf"] += 1
        else:
            stats["done"] += 1
        await db.commit()
        used = await spent(db, project.id) if res.choice.price_input else used
        if progress:
            progress(i, len(todo))
    return stats
