"""Clientes das APIs públicas de busca: PubMed (E-utilities), OpenAlex e Europe PMC, além de
SciELO e PePSIC, que são buscas no OpenAlex restritas às revistas dessas coleções.

Cada fonte sabe contar os resultados de uma busca (com uma amostra, para a pessoa conferir a
string antes de importar) e trazer os registros em lotes, já no formato do importador.
"""

import asyncio
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from revalli.core.config import get_settings
from revalli.modules.imports.normalize import ParsedRecord, normalize_pmid
from revalli.modules.imports.parsers import parse_pubmed_xml
from revalli.modules.records.enrich import abstract_from_index

# Permite trocar o transporte nos testes (sem rede)
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


class SourceError(Exception):
    """A base recusou a busca ou não respondeu."""


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=60,
        transport=_transport,
        headers={"User-Agent": "ReValli (self-hosted literature review tool)"},
        follow_redirects=True,
    )


async def pause() -> None:
    delay = get_settings().api_delay_seconds
    if delay > 0:
        await asyncio.sleep(delay)


RETRY_STATUS = {429, 502, 503, 504}
MAX_ATTEMPTS = 5
MAX_WAIT = 30.0
# O OpenAlex limita consultas com mais de 5 operadores booleanos a 1 por segundo (5 por segundo
# com chave de API). Espaçar as chamadas evita o 429 em vez de depender de tentar de novo.
HEAVY_OPERATORS = 5
HEAVY_INTERVAL = 1.1
HEAVY_INTERVAL_WITH_KEY = 0.25
_BOOLEAN = re.compile(r"\b(?:AND|OR|NOT)\b")
_next_heavy: dict[str, float] = {}


def is_heavy(params: dict) -> bool:
    return any(
        len(_BOOLEAN.findall(str(params.get(k) or ""))) > HEAVY_OPERATORS
        for k in ("search", "search.exact")
    )


async def throttle(url: str, params: dict) -> None:
    """Espera o intervalo mínimo entre consultas pesadas ao mesmo servidor. Sem espera nos testes."""
    settings = get_settings()
    if settings.api_delay_seconds <= 0 or not is_heavy(params):
        return
    host = httpx.URL(url).host
    interval = HEAVY_INTERVAL_WITH_KEY if settings.openalex_api_key else HEAVY_INTERVAL
    wait = _next_heavy.get(host, 0.0) - time.monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    _next_heavy[host] = time.monotonic() + interval


def retry_after_seconds(resp: httpx.Response | None) -> float:
    if resp is None:
        return 0.0
    header = resp.headers.get("retry-after", "")
    if header.isdigit():
        return float(header)
    try:
        return float(resp.json().get("retryAfter") or 0)
    except (ValueError, AttributeError, TypeError):
        return 0.0


async def backoff(attempt: int, resp: httpx.Response | None) -> None:
    """Espera antes de tentar de novo; respeita Retry-After. Sem espera nos testes (delay 0)."""
    if get_settings().api_delay_seconds <= 0:
        return
    await asyncio.sleep(min(max(retry_after_seconds(resp), 1.0) * attempt, 20.0))


async def get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    """GET com nova tentativa quando a base pede calma (429) ou falha por instantes (5xx)."""
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        await throttle(url, params)
        resp = None
        try:
            resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            last = f"connection: {type(exc).__name__}"
        else:
            if resp.status_code < 400:
                return resp
            last = f"http {resp.status_code}: {resp.text[:700]}"
            # Esperas longas (orçamento diário esgotado) não adiantam: falha na hora
            if resp.status_code not in RETRY_STATUS or retry_after_seconds(resp) > MAX_WAIT:
                raise SourceError(last)
        if attempt < MAX_ATTEMPTS - 1:
            await backoff(attempt + 1, resp)
    raise SourceError(last)


@dataclass
class Preview:
    count: int
    sample: list[ParsedRecord]
    # Como a base interpretou a estratégia e o que ela descartou (só o PubMed informa)
    translation: str = ""
    warnings: list[str] = field(default_factory=list)


# --- OpenAlex ------------------------------------------------------------------


def openalex_params() -> dict:
    s = get_settings()
    params = {"mailto": s.enrichment_contact_email} if s.enrichment_contact_email else {}
    if s.openalex_api_key:
        params["api_key"] = s.openalex_api_key
    return params


_QUOTED = re.compile(r'"([^"]*)"')


def adapt_query(query: str) -> str:
    """O OpenAlex recusa curingas dentro de frases entre aspas ("efeito* adverso*"). A frase
    vira as palavras ligadas por AND, o que é um pouco mais amplo mas é aceito."""

    def unquote(m: re.Match) -> str:
        phrase = m.group(1)
        if "*" not in phrase and "?" not in phrase:
            return m.group(0)
        words = phrase.split()
        return words[0] if len(words) == 1 else "(" + " AND ".join(words) + ")"

    return _QUOTED.sub(unquote, query)


def search_param(query: str) -> dict:
    """Curingas (* ou ?) só funcionam na busca exata do OpenAlex, que não radicaliza as palavras."""
    query = adapt_query(query)
    exact = "*" in query or "?" in query
    return {"search.exact" if exact else "search": query}


def short_openalex_id(value: str | None) -> str:
    return (value or "").rsplit("/", 1)[-1]


def openalex_work(work: dict) -> ParsedRecord:
    ids = work.get("ids") or {}
    biblio = work.get("biblio") or {}
    source = ((work.get("primary_location") or {}).get("source")) or {}
    first, last = biblio.get("first_page") or "", biblio.get("last_page") or ""
    keywords = [k.get("display_name", "") for k in work.get("keywords") or []]
    oa_id = short_openalex_id(work.get("id"))
    return ParsedRecord(
        title=work.get("title") or work.get("display_name") or "",
        abstract=abstract_from_index(work.get("abstract_inverted_index")),
        authors=[
            (a.get("author") or {}).get("display_name", "") for a in work.get("authorships") or []
        ],
        year=work.get("publication_year"),
        journal=source.get("display_name") or "",
        volume=biblio.get("volume") or "",
        issue=biblio.get("issue") or "",
        pages=f"{first}-{last}" if first and last and first != last else first,
        doi=work.get("doi") or ids.get("doi"),
        pmid=normalize_pmid(short_openalex_id(ids.get("pmid"))),
        url=work.get("doi") or work.get("id") or "",
        keywords=[k for k in keywords if k],
        language=work.get("language") or "",
        publication_type=work.get("type") or "",
        raw={"openalex": oa_id},
    ).clean()


async def openalex_pages(
    client: httpx.AsyncClient, params: dict, limit: int
) -> AsyncIterator[tuple[int, list[dict]]]:
    """Percorre os resultados com cursor; devolve (total, lote de works)."""
    url = get_settings().openalex_url.rstrip("/") + "/works"
    cursor, seen = "*", 0
    while cursor and seen < limit:
        resp = await get(
            client,
            url,
            {**openalex_params(), **params, "per-page": min(200, limit - seen), "cursor": cursor},
        )
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return
        seen += len(results)
        yield int((data.get("meta") or {}).get("count") or 0), results
        cursor = (data.get("meta") or {}).get("next_cursor")
        await pause()


async def openalex_preview(client: httpx.AsyncClient, query: str) -> Preview:
    url = get_settings().openalex_url.rstrip("/") + "/works"
    resp = await get(client, url, {**openalex_params(), **search_param(query), "per-page": 5})
    data = resp.json()
    adapted = adapt_query(query)
    return Preview(
        int((data.get("meta") or {}).get("count") or 0),
        [openalex_work(w) for w in data.get("results") or []],
        translation=adapted if adapted != query else "",
    )


async def openalex_fetch(
    client: httpx.AsyncClient, query: str, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    async for total, works in openalex_pages(client, search_param(query), limit):
        yield total, [openalex_work(w) for w in works]


# --- PubMed --------------------------------------------------------------------


def pubmed_params() -> dict:
    s = get_settings()
    params = {"db": "pubmed", "tool": "revalli"}
    if s.enrichment_contact_email:
        params["email"] = s.enrichment_contact_email
    if s.ncbi_api_key:
        params["api_key"] = s.ncbi_api_key
    return params


async def pubmed_search(client: httpx.AsyncClient, query: str, retmax: int, history: bool):
    url = get_settings().pubmed_url.rstrip("/") + "/esearch.fcgi"
    params = {**pubmed_params(), "term": query, "retmode": "json", "retmax": retmax}
    if history:
        params["usehistory"] = "y"
    data = (await get(client, url, params)).json().get("esearchresult") or {}
    if "ERROR" in data:
        raise SourceError(str(data["ERROR"])[:200])
    return data


def pubmed_warnings(data: dict) -> list[str]:
    """Frases ou campos que o PubMed não reconheceu e ignorou; a busca roda sem eles."""
    out: list[str] = []
    warn, err = data.get("warninglist") or {}, data.get("errorlist") or {}
    for part in (
        err.get("phrasesnotfound"),
        err.get("fieldsnotfound"),
        warn.get("phrasesignored"),
        warn.get("quotedphrasesnotfound"),
        warn.get("outputmessages"),
    ):
        out.extend(str(x) for x in part or [] if x)
    return list(dict.fromkeys(out))


async def pubmed_efetch(client: httpx.AsyncClient, params: dict) -> list[ParsedRecord]:
    url = get_settings().pubmed_url.rstrip("/") + "/efetch.fcgi"
    resp = await get(client, url, {**pubmed_params(), **params, "retmode": "xml"})
    return [r.clean() for r in parse_pubmed_xml(resp.text)]


async def pubmed_preview(client: httpx.AsyncClient, query: str) -> Preview:
    data = await pubmed_search(client, query, 5, history=False)
    ids = data.get("idlist") or []
    sample = []
    if ids:
        await pause()
        sample = await pubmed_efetch(client, {"id": ",".join(ids)})
    return Preview(
        int(data.get("count") or 0),
        sample,
        translation=str(data.get("querytranslation") or ""),
        warnings=pubmed_warnings(data),
    )


async def pubmed_fetch(
    client: httpx.AsyncClient, query: str, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    data = await pubmed_search(client, query, 0, history=True)
    total = int(data.get("count") or 0)
    env, key = data.get("webenv"), data.get("querykey")
    step = 200
    for start in range(0, min(total, limit), step):
        await pause()
        batch = await pubmed_efetch(
            client,
            {
                "WebEnv": env,
                "query_key": key,
                "retstart": start,
                "retmax": min(step, limit - start),
            },
        )
        yield total, batch


# --- Europe PMC ----------------------------------------------------------------


def europepmc_record(item: dict) -> ParsedRecord:
    journal = (item.get("journalInfo") or {}).get("journal") or {}
    info = item.get("journalInfo") or {}
    authors = [
        a.get("fullName") or " ".join(filter(None, [a.get("lastName"), a.get("initials")]))
        for a in (item.get("authorList") or {}).get("author") or []
    ]
    if not authors and item.get("authorString"):
        authors = [a.strip() for a in item["authorString"].rstrip(".").split(",")]
    year = item.get("pubYear") or info.get("yearOfPublication")
    return ParsedRecord(
        title=item.get("title") or "",
        abstract=item.get("abstractText") or "",
        authors=authors,
        year=int(year) if str(year or "").isdigit() else None,
        journal=journal.get("title") or item.get("journalTitle") or "",
        volume=str(info.get("volume") or item.get("journalVolume") or ""),
        issue=str(info.get("issue") or item.get("issue") or ""),
        pages=item.get("pageInfo") or "",
        doi=item.get("doi"),
        pmid=item.get("pmid"),
        keywords=(item.get("keywordList") or {}).get("keyword") or [],
        language=item.get("language") or "",
        publication_type="; ".join((item.get("pubTypeList") or {}).get("pubType") or []),
        raw={"europepmc": f"{item.get('source', '')}:{item.get('id', '')}"},
    ).clean()


async def europepmc_page(client: httpx.AsyncClient, query: str, size: int, cursor: str):
    url = get_settings().europepmc_url.rstrip("/") + "/search"
    resp = await get(
        client,
        url,
        {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": size,
            "cursorMark": cursor,
        },
    )
    return resp.json()


async def europepmc_preview(client: httpx.AsyncClient, query: str) -> Preview:
    data = await europepmc_page(client, query, 5, "*")
    items = (data.get("resultList") or {}).get("result") or []
    return Preview(int(data.get("hitCount") or 0), [europepmc_record(i) for i in items])


async def europepmc_fetch(
    client: httpx.AsyncClient, query: str, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    cursor, seen = "*", 0
    while seen < limit:
        data = await europepmc_page(client, query, min(1000, limit - seen), cursor)
        items = (data.get("resultList") or {}).get("result") or []
        if not items:
            return
        seen += len(items)
        yield int(data.get("hitCount") or 0), [europepmc_record(i) for i in items]
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            return
        cursor = nxt
        await pause()


# --- SciELO e PePSIC (OpenAlex restrito às revistas da coleção) ---------------------

# O OpenAlex aceita até 50 valores por filtro; a coleção SciELO Brasil tem cerca de 430 revistas
ISSN_CHUNK = 50
_COLLECTION_TTL = 24 * 3600
_collections: dict[str, tuple[float, list[str]]] = {}


async def collection_issns(client: httpx.AsyncClient, collection: str) -> list[str]:
    """ISSNs das revistas de uma coleção do SciELO (scl = Brasil, psi = PePSIC), via ArticleMeta."""
    cached = _collections.get(collection)
    if cached and time.monotonic() - cached[0] < _COLLECTION_TTL:
        return cached[1]
    url = get_settings().articlemeta_url.rstrip("/") + "/journal/identifiers/"
    issns: list[str] = []
    offset = 0
    while True:
        resp = await get(client, url, {"collection": collection, "limit": 1000, "offset": offset})
        objects = resp.json().get("objects") or []
        issns += [o["code"] for o in objects if o.get("code")]
        if len(objects) < 1000:
            break
        offset += 1000
    issns = sorted(set(issns))
    if not issns:
        raise SourceError(f"empty_collection: {collection}")
    _collections[collection] = (time.monotonic(), issns)
    return issns


def _issn_filters(issns: list[str]) -> list[str]:
    return [
        "primary_location.source.issn:" + "|".join(issns[n : n + ISSN_CHUNK])
        for n in range(0, len(issns), ISSN_CHUNK)
    ]


async def collection_preview(client: httpx.AsyncClient, collection: str, query: str) -> Preview:
    url = get_settings().openalex_url.rstrip("/") + "/works"
    total, sample = 0, []
    for flt in _issn_filters(await collection_issns(client, collection)):
        resp = await get(
            client,
            url,
            {**openalex_params(), **search_param(query), "filter": flt, "per-page": 5},
        )
        data = resp.json()
        total += int((data.get("meta") or {}).get("count") or 0)
        if len(sample) < 5:
            sample += [openalex_work(w) for w in data.get("results") or []][: 5 - len(sample)]
        await pause()
    adapted = adapt_query(query)
    return Preview(total, sample, translation=adapted if adapted != query else "")


async def collection_fetch(
    client: httpx.AsyncClient, collection: str, query: str, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    """Um lote de revistas por vez. O total acumula as contagens de cada lote; ao atingir o
    limite, os lotes restantes só são contados, para o total informado ser o da base inteira."""
    url = get_settings().openalex_url.rstrip("/") + "/works"
    total = seen = 0
    for flt in _issn_filters(await collection_issns(client, collection)):
        params = {**search_param(query), "filter": flt}
        if seen >= limit:
            resp = await get(client, url, {**openalex_params(), **params, "per-page": 1})
            total += int((resp.json().get("meta") or {}).get("count") or 0)
            await pause()
            continue
        chunk_total = 0
        async for chunk_total, works in openalex_pages(client, params, limit - seen):
            seen += len(works)
            yield total + chunk_total, [openalex_work(w) for w in works]
        total += chunk_total
    yield total, []


def _collection_source(label: str, collection: str):
    async def preview(client: httpx.AsyncClient, query: str) -> Preview:
        return await collection_preview(client, collection, query)

    def fetch(client: httpx.AsyncClient, query: str, limit: int):
        return collection_fetch(client, collection, query, limit)

    return (label, preview, fetch)


SOURCES = {
    "pubmed": ("PubMed", pubmed_preview, pubmed_fetch),
    "openalex": ("OpenAlex", openalex_preview, openalex_fetch),
    "europepmc": ("Europe PMC", europepmc_preview, europepmc_fetch),
    "scielo": _collection_source("SciELO (via OpenAlex)", "scl"),
    "pepsic": _collection_source("PePSIC (via OpenAlex)", "psi"),
}
