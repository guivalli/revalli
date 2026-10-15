"""Busca direta nas bases e snowballing de citações pelo OpenAlex.

Os registros trazidos viram uma busca (Search) como as importadas por arquivo, então passam
pela mesma deduplicação, triagem e contagem do PRISMA. O snowballing fica marcado como
"outros métodos" (busca de citações), como pede o PRISMA 2020.
"""

import uuid
from collections.abc import Callable
from datetime import date

import httpx
from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.models import AIUsage, Project, Record, Search, SearchAssistantChat
from revalli.modules.ai import client as ai_client
from revalli.modules.ai.service import project_ai, resolve, spent
from revalli.modules.fulltext.studies import default_label
from revalli.modules.imports.normalize import ParsedRecord, normalize_doi, normalize_title
from revalli.modules.screening.models import Phase
from revalli.modules.screening.service import State, compute_states
from revalli.modules.sources import catalog, clients, keys
from revalli.modules.sources.clients import openalex_pages, openalex_work, short_openalex_id
from revalli.modules.sources.fields import Row, compile_strategy

Progress = Callable[[int, int], None]
BATCH = 50
TITLE_MATCH = 95
SEED_FIELDS = "id,doi,ids,title,display_name,publication_year,referenced_works"


def _record(project_id: uuid.UUID, search_id: uuid.UUID, p: ParsedRecord) -> Record:
    return Record(
        project_id=project_id,
        search_id=search_id,
        title=p.title,
        abstract=p.abstract,
        authors=p.authors,
        year=p.year,
        journal=p.journal,
        volume=p.volume,
        issue=p.issue,
        pages=p.pages,
        doi=p.doi,
        pmid=p.pmid,
        url=p.url,
        keywords=p.keywords,
        language=p.language,
        publication_type=p.publication_type,
        raw=p.raw,
    )


async def save_search(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    *,
    source: str,
    query: str,
    method: str,
    records: list[ParsedRecord],
    reported_count: int | None,
    notes: str = "",
) -> Search:
    search = Search(
        project_id=project_id,
        source=source,
        query=query,
        searched_on=date.today(),
        reported_count=reported_count,
        notes=notes,
        file_name="",
        file_format="api",
        imported_count=len(records),
        method=method,
        created_by_id=user_id,
    )
    db.add(search)
    await db.flush()
    db.add_all(_record(project_id, search.id, p) for p in records)
    await db.commit()
    return search


# --- Busca direta ----------------------------------------------------------------


async def preview(
    db: AsyncSession, source: str, query: str, rows: list[Row] | None = None
) -> clients.Preview:
    await keys.load(db)
    strategy = compile_strategy(source, query, rows)
    _, run_preview, _ = clients.SOURCES[source]
    async with clients.http_client() as c:
        result = await run_preview(c, strategy)
    result.corrections = strategy.corrections
    result.strategy = strategy.native
    # A tradução do PubMed (como ele leu a busca) vale mais que a nossa
    result.translation = result.translation or strategy.shown
    return result


async def run_api_search(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    source: str,
    query: str,
    limit: int,
    progress: Progress | None = None,
    rows: list[Row] | None = None,
) -> dict:
    await keys.load(db)
    strategy = compile_strategy(source, query, rows)
    name, _, fetch = clients.SOURCES[source]
    limit = min(limit, get_settings().api_search_max)
    found: list[ParsedRecord] = []
    total = 0
    async with clients.http_client() as c:
        async for total, batch in fetch(c, strategy, limit):
            found.extend(r for r in batch if not r.is_empty)
            if progress:
                progress(len(found), min(total, limit))
    found = found[:limit]
    search = await save_search(
        db,
        project_id,
        user_id,
        source=name,
        query=strategy.native,
        method="database",
        records=found,
        reported_count=total,
    )
    return {
        "search_id": str(search.id),
        "source": name,
        "found": total,
        "imported": len(found),
        "truncated": total > len(found),
        "corrections": strategy.corrections,
    }


# --- Snowballing -----------------------------------------------------------------


async def included_ids(db: AsyncSession, project: Project) -> list[uuid.UUID]:
    states = await compute_states(db, project, Phase.full_text)
    return [rid for rid, st in states.items() if st.state == State.included]


async def _known(db: AsyncSession, project_id: uuid.UUID) -> tuple[set, set, set]:
    rows = await db.execute(
        select(Record.doi, Record.pmid, Record.raw["openalex"].astext).where(
            Record.project_id == project_id
        )
    )
    dois, pmids, oa = set(), set(), set()
    for doi, pmid, oa_id in rows.all():
        if doi:
            dois.add(doi)
        if pmid:
            pmids.add(pmid)
        if oa_id:
            oa.add(oa_id)
    return dois, pmids, oa


async def _works_by(
    c: httpx.AsyncClient, key: str, values: list[str], fields: str | None = None
) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(values), BATCH):
        chunk = values[i : i + BATCH]
        params = {"filter": f"{key}:" + "|".join(chunk)}
        if fields:
            params["select"] = fields
        async for _, works in openalex_pages(c, params, len(chunk)):
            out.extend(works)
    return out


async def resolve_seeds(c: httpx.AsyncClient, records: list[Record]) -> dict[uuid.UUID, dict]:
    """Acha o work do OpenAlex de cada registro semente (por ID, DOI, PMID ou título)."""
    found: dict[uuid.UUID, dict] = {}
    pending = list(records)

    by_oa = {(r.raw or {}).get("openalex"): r for r in pending if (r.raw or {}).get("openalex")}
    for w in await _works_by(c, "openalex", list(by_oa), SEED_FIELDS):
        rec = by_oa.get(short_openalex_id(w.get("id")))
        if rec is not None:
            found[rec.id] = w
    pending = [r for r in pending if r.id not in found]

    by_doi = {r.doi: r for r in pending if r.doi}
    for w in await _works_by(c, "doi", [f"https://doi.org/{d}" for d in by_doi], SEED_FIELDS):
        rec = by_doi.get(normalize_doi(w.get("doi")))
        if rec is not None:
            found[rec.id] = w
    pending = [r for r in pending if r.id not in found]

    by_pmid = {r.pmid: r for r in pending if r.pmid}
    for w in await _works_by(c, "pmid", list(by_pmid), SEED_FIELDS):
        pmid = short_openalex_id((w.get("ids") or {}).get("pmid"))
        rec = by_pmid.get(pmid)
        if rec is not None:
            found[rec.id] = w
    pending = [r for r in pending if r.id not in found]

    # Sem identificador: só aceita título quase idêntico
    url = get_settings().openalex_url.rstrip("/") + "/works"
    for rec in [r for r in pending if r.title]:
        resp = await clients.get(
            c,
            url,
            {
                **clients.openalex_params(),
                "search": rec.title[:300],
                "per-page": 3,
                "select": SEED_FIELDS,
            },
        )
        target = normalize_title(rec.title)
        for w in resp.json().get("results") or []:
            title = w.get("title") or w.get("display_name") or ""
            if fuzz.token_sort_ratio(target, normalize_title(title)) >= TITLE_MATCH:
                found[rec.id] = w
                break
        await clients.pause()
    return found


async def run_snowball(
    db: AsyncSession,
    project: Project,
    user_id: uuid.UUID | None,
    direction: str,
    seed_ids: list[uuid.UUID] | None,
    progress: Progress | None = None,
) -> dict:
    await keys.load(db)
    if seed_ids is None:
        seed_ids = await included_ids(db, project)
    seeds = list(
        (
            await db.execute(
                select(Record).where(Record.project_id == project.id, Record.id.in_(seed_ids))
            )
        ).scalars()
    )
    limit = get_settings().api_search_max
    dois, pmids, oa_known = await _known(db, project.id)
    stats: dict = {"seeds": len(seeds), "matched": 0, "already_in_project": 0, "searches": []}
    labels = {r.id: default_label(r) for r in seeds}

    async with clients.http_client() as c:
        works = await resolve_seeds(c, seeds)
        stats["matched"] = len(works)
        stats["not_found"] = [labels[r.id] for r in seeds if r.id not in works]
        if progress:
            progress(0, len(works))
        seen: set[str] = set()

        def is_new(w: dict) -> bool:
            oa = short_openalex_id(w.get("id"))
            if oa in seen:
                return False
            seen.add(oa)
            doi = normalize_doi(w.get("doi"))
            pmid = short_openalex_id((w.get("ids") or {}).get("pmid"))
            if oa in oa_known or (doi and doi in dois) or (pmid and pmid in pmids):
                stats["already_in_project"] += 1
                return False
            return True

        # As próprias sementes nunca voltam como achados
        seen |= {short_openalex_id(w.get("id")) for w in works.values()}

        for step in ("backward", "forward") if direction == "both" else (direction,):
            # Para cada work novo, guarda de quais sementes ele veio
            links: dict[str, list[str]] = {}
            new: dict[str, dict] = {}
            if step == "backward":
                for rid, w in works.items():
                    for ref in w.get("referenced_works") or []:
                        links.setdefault(short_openalex_id(ref), []).append(str(rid))
                candidates = [oa for oa in links if oa not in seen]
                for w in await _works_by(c, "openalex", candidates[: limit * 2]):
                    if len(new) < limit and is_new(w):
                        new[short_openalex_id(w.get("id"))] = w
            else:
                for done, (rid, w) in enumerate(works.items(), 1):
                    oa_seed = short_openalex_id(w.get("id"))
                    async for _, citing in openalex_pages(c, {"filter": f"cites:{oa_seed}"}, limit):
                        for cw in citing:
                            oa = short_openalex_id(cw.get("id"))
                            if oa in new:
                                links[oa].append(str(rid))
                            elif len(new) < limit and is_new(cw):
                                new[oa] = cw
                                links[oa] = [str(rid)]
                    if progress:
                        progress(done, len(works))
            records = []
            for oa, w in new.items():
                p = openalex_work(w)
                p.raw["citation"] = {"direction": step, "seeds": links.get(oa, [])}
                if not p.is_empty:
                    records.append(p)
            matched_labels = sorted(labels[rid] for rid in works)
            search = await save_search(
                db,
                project.id,
                user_id,
                source="OpenAlex",
                query=f"{len(matched_labels)}: " + "; ".join(matched_labels),
                method=f"citation_{step}",
                records=records,
                reported_count=None,
            )
            stats["searches"].append(
                {"id": str(search.id), "direction": step, "imported": len(records)}
            )
    return stats


# --- Tradução da string de busca ---------------------------------------------------

TARGETS = {
    "pubmed": "PubMed (MeSH terms with [mh], [tiab] field tags)",
    "openalex": (
        "OpenAlex, searched in title and abstract (plain words, quoted phrases, AND/OR/NOT in "
        "uppercase, parentheses; no field tags such as ti: or ab:, no truncation)"
    ),
    "europepmc": "Europe PMC (TITLE:, ABSTRACT:, TITLE_ABS:, KW:, AUTH: fields; AND/OR/NOT)",
    "scopus": "Scopus (TITLE-ABS-KEY(), W/n proximity, * truncation)",
    "wos": "Web of Science Core Collection (TS=(), NEAR/n proximity, * truncation)",
    "embase": "Embase via Embase.com (Emtree terms with /exp, :ti,ab,kw fields, NEAR/n)",
    "cinahl": "CINAHL via EBSCOhost (MH headings, TI/AB fields, Nn proximity)",
    "psycinfo": "APA PsycInfo via Ovid (exp headings/, .ti,ab. fields, adjN proximity)",
    "cochrane": "Cochrane Library (MeSH descriptor:[] explode all trees, :ti,ab,kw fields)",
    "bvs": "BVS/LILACS (DeCS descriptors with mh:, ti:, ab: fields, multilingual terms)",
    "scielo": (
        "SciELO (searched through OpenAlex, also valid in the SciELO portal search): plain "
        "words, quoted phrases, AND/OR/NOT in uppercase and parentheses; no field tags and no "
        "truncation; add Portuguese and Spanish synonyms because most records are not in English"
    ),
    "capes": (
        "Portal de Periódicos CAPES (subject search): plain words, quoted phrases, AND/OR/NOT in "
        "uppercase, parentheses and * truncation; fields are chosen in the advanced search form, "
        "not written in the query; add Portuguese and Spanish synonyms"
    ),
    "pepsic": (
        "PePSIC, Periódicos Eletrônicos em Psicologia (searched through OpenAlex): plain words, "
        "quoted phrases, AND/OR/NOT in uppercase and parentheses; no field tags and no "
        "truncation; psychology terms, add Portuguese and Spanish synonyms"
    ),
    "eric": (
        "ERIC, Education Resources Information Center (education research): field:term syntax "
        "with title:, description: (abstract), subject: (ERIC thesaurus descriptors), author:, "
        "source: (journal); AND/OR/NOT in uppercase, parentheses, quoted phrases, * truncation; "
        "English terms"
    ),
    "clinicaltrials": (
        "ClinicalTrials.gov (registry of trials, not articles): Essie expressions such as "
        "AREA[Condition](...), AREA[InterventionName](...), AREA[BriefTitle](...); AND, OR and "
        "AND NOT in uppercase and parentheses; search by condition and intervention rather "
        "than by methodology words"
    ),
    "preprints": (
        "Preprints in Europe PMC (PsyArXiv, medRxiv, bioRxiv, Research Square and others): same "
        "syntax as Europe PMC (TITLE:, ABSTRACT:, TITLE_ABS:, KW:, AUTH:); the preprint filter is "
        "added by the tool, so do not write SRC:PPR"
    ),
    "arxiv": (
        "arXiv (physics, mathematics, computer science, statistics, quantitative fields): "
        "ti:, abs:, au:, all: prefixes; AND, OR and ANDNOT in uppercase, parentheses, quoted "
        "phrases; English terms"
    ),
    "doaj": (
        "DOAJ, Directory of Open Access Journals (open access articles in all fields): Lucene "
        "syntax with bibjson.title:, bibjson.abstract:, bibjson.keywords:, bibjson.author.name:, "
        "bibjson.journal.title:; AND, OR and AND NOT in uppercase, parentheses, quoted phrases; "
        "no truncation (* is refused)"
    ),
    "openaire": (
        "OpenAIRE (European repositories, grey literature, theses and articles): plain words, "
        "quoted phrases, AND/OR/NOT in uppercase and parentheses; no field tags and no "
        "truncation; add terms in the languages of the repositories"
    ),
    "semanticscholar": (
        "Semantic Scholar bulk search: + for AND, | for OR, - before a term for NOT, quoted "
        "phrases, parentheses, * suffix truncation; plain terms with no field tags"
    ),
    "sportdiscus": (
        "SPORTDiscus via EBSCOhost (TI, AB, SU, KW field codes, e.g. TI (term) OR AB (term); "
        "SU for subject terms; Nn and Wn proximity; * truncation)"
    ),
    "pedro": (
        "PEDro, Physiotherapy Evidence Database (simple search on abstract and title): plain "
        "words and quoted phrases with AND/OR; keep the strategy short because the interface "
        "has few operators; therapy, problem and body part are chosen in form fields"
    ),
    "econlit": (
        "EconLit via EBSCOhost or Ovid (TI, AB, SU field codes, JEL classification codes, Nn "
        "proximity, * truncation)"
    ),
    "ieee": (
        'IEEE Xplore command search ("Document Title":term, "Abstract":term, "Author '
        'Keywords":term, "All Metadata":term; AND/OR/NOT in uppercase; NEAR/n; * and ? '
        "wildcards)"
    ),
    "acm": (
        "ACM Digital Library advanced search (Title:(...), Abstract:(...), Keyword:(...), "
        "AllField:(...); AND/OR/NOT in uppercase; quoted phrases; * wildcard)"
    ),
}

TRANSLATE_SYSTEM = """You translate literature search strategies between bibliographic databases.
Keep the same concepts, synonyms and boolean logic. Map controlled vocabulary to the target
database's thesaurus when one exists (and say so in the notes when you are not sure the term
exists). Adapt field tags, truncation and proximity operators to the target syntax.
Do not add or remove concepts. Do not add date, language or study-type limits that are not in
the original.
Answer with a single JSON object: {"query": "...", "notes": ["short note", ...]}"""


class TranslationError(Exception):
    pass


async def translate_query(db: AsyncSession, project: Project, query: str, target: str) -> dict:
    ai = project_ai(project)
    res = await resolve(db, "screening", ai.local_only)
    if ai.budget_usd is not None and await spent(db, project.id) >= ai.budget_usd:
        raise TranslationError("budget_exceeded")
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM},
        {
            "role": "user",
            "content": f"Target database: {TARGETS[target]}\n\nOriginal strategy:\n{query}",
        },
    ]
    result = await ai_client.chat(res.endpoint, messages)
    db.add(
        AIUsage(
            project_id=project.id,
            provider_id=res.provider.id,
            model=res.choice.model,
            task="query_translation",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=res.cost(result.input_tokens, result.output_tokens),
        )
    )
    await db.commit()
    data = ai_client.parse_json(result.content)
    translated = data.get("query")
    if not isinstance(translated, str) or not translated.strip():
        raise TranslationError("invalid_answer")
    notes = data.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    return {
        "query": translated.strip(),
        "notes": [str(n) for n in notes if n][:10],
        "model": res.choice.model,
    }


# --- Conversa para montar a estratégia -----------------------------------------------

ASSIST_SYSTEM = """You are an expert health-sciences librarian helping a research team build
database search strategies for a literature review.

How to work:
- Say briefly what you understood (population, concept, outcome, study types, languages). If
  something essential is missing, ask at most 3 short questions, but still propose a first
  strategy from what you understood.
- Build each strategy in concept blocks joined by AND. Usually 2 to 4 blocks, one per concept:
  the population or context, the phenomenon or exposure, the outcome or effect and, when
  relevant, the intervention or study design. Never merge two concepts into one block.
- Inside a block join synonyms, spelling variants and translations with OR. Quote multi-word
  phrases. Use truncation (*) to cover word endings (for example iatrogeni*, effect*,
  interven*). In PubMed, truncated words work in [tiab] but not with [mh].
- Include terms in the languages of the databases (Portuguese, English and Spanish for the
  Latin American ones).
- Write each strategy in the syntax of its database. Databases and their syntax:
{targets}
- Give strategies only for databases in the list above. The team has already chosen these
  databases for the project, so if they name none, give one strategy per listed database.
- Reply to the team in the language they write in. The query text keeps the languages of the
  search terms.

Answer with a single JSON object and nothing else:
{{"reply": "what you understood and your questions",
  "strategies": [{{"base": "one of: {keys}", "query": "...", "notes": ["short note"]}}]}}"""

MAX_STRATEGIES = 30


def parse_assist(data: dict, allowed: tuple[str, ...] | list[str] | None = None) -> dict:
    reply = str(data.get("reply") or "").strip()[:4000]
    strategies, seen = [], set()
    for raw in data.get("strategies") or []:
        if not isinstance(raw, dict):
            continue
        base = str(raw.get("base") or "").strip().lower()
        query = str(raw.get("query") or "").strip()[:20_000]
        if base not in (allowed or TARGETS) or base in seen or not query:
            continue
        seen.add(base)
        notes = raw.get("notes") or []
        if isinstance(notes, str):
            notes = [notes]
        strategies.append(
            {"base": base, "query": query, "notes": [str(n)[:300] for n in notes if n][:5]}
        )
    if not reply and not strategies:
        raise TranslationError("invalid_answer")
    return {"reply": reply, "strategies": strategies[:MAX_STRATEGIES]}


def assist_history(messages: list[dict]) -> list[dict]:
    """O que o modelo vê: o texto de cada turno e, nas respostas dele, as estratégias propostas."""
    out = []
    for m in messages:
        content = m["content"]
        strategies = m.get("strategies") or []
        if m["role"] == "assistant" and strategies:
            lines = "\n".join(f"{s['base']}: {s['query']}" for s in strategies)
            content = f"{content}\n\n{lines}"
        out.append({"role": m["role"], "content": content})
    return out


def _chat_query(project_id: uuid.UUID, user_id: uuid.UUID):
    return select(SearchAssistantChat).where(
        SearchAssistantChat.project_id == project_id, SearchAssistantChat.user_id == user_id
    )


async def load_chat(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    chat = (await db.execute(_chat_query(project_id, user_id))).scalar_one_or_none()
    return list(chat.messages) if chat else []


# Guarda no máximo isto; o próximo pedido (com a mensagem nova) ainda cabe no limite de 30
CHAT_KEEP = 28


async def save_chat(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, messages: list[dict]
) -> None:
    # Descarta as trocas mais antigas, de duas em duas, para a conversa começar por quem pergunta
    while len(messages) > CHAT_KEEP:
        messages = messages[2:]
    chat = (await db.execute(_chat_query(project_id, user_id))).scalar_one_or_none()
    if chat is None:
        db.add(SearchAssistantChat(project_id=project_id, user_id=user_id, messages=messages))
    else:
        chat.messages = messages


async def clear_chat(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(SearchAssistantChat).where(
            SearchAssistantChat.project_id == project_id, SearchAssistantChat.user_id == user_id
        )
    )


async def assist_search(db: AsyncSession, project: Project, history: list[dict]) -> dict:
    ai = project_ai(project)
    res = await resolve(db, "screening", ai.local_only)
    if ai.budget_usd is not None and await spent(db, project.id) >= ai.budget_usd:
        raise TranslationError("budget_exceeded")
    context = f"Review title: {project.title}"
    if project.description.strip():
        context += f"\nReview description: {project.description.strip()}"
    chosen = catalog.enabled(project.settings)
    system = ASSIST_SYSTEM.format(
        targets="\n".join(f"- {k}: {TARGETS[k]}" for k in chosen), keys=", ".join(chosen)
    )
    messages = [
        {"role": "system", "content": f"{system}\n\n{context}"},
        *assist_history(history),
    ]
    result = await ai_client.chat(res.endpoint, messages)
    db.add(
        AIUsage(
            project_id=project.id,
            provider_id=res.provider.id,
            model=res.choice.model,
            task="search_assistant",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=res.cost(result.input_tokens, result.output_tokens),
        )
    )
    await db.commit()
    out = parse_assist(ai_client.parse_json(result.content), chosen)
    return {**out, "model": res.choice.model}
