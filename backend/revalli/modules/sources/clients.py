"""Clientes das APIs públicas de busca: PubMed (E-utilities), OpenAlex e Europe PMC, além de
SciELO e PePSIC, que são buscas no OpenAlex restritas às revistas dessas coleções, dos preprints
(Europe PMC restrito à fonte PPR), do ERIC, do ClinicalTrials.gov, do arXiv, do DOAJ, do OpenAIRE
e do Semantic Scholar.

Cada fonte sabe contar os resultados de uma busca (com uma amostra, para a pessoa conferir a
string antes de importar) e trazer os registros em lotes, já no formato do importador.
"""

import asyncio
import html
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx
from defusedxml import ElementTree

from revalli.core.config import get_settings
from revalli.modules.imports.normalize import ParsedRecord, normalize_pmid
from revalli.modules.imports.parsers import parse_pubmed_xml
from revalli.modules.records.enrich import abstract_from_index
from revalli.modules.sources import keys
from revalli.modules.sources.fields import Compiled

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
        for k in ("search", "search.exact", "filter")
    )


async def throttle(url: str, params: dict) -> None:
    """Espera o intervalo mínimo entre consultas pesadas ao mesmo servidor. Sem espera nos testes."""
    settings = get_settings()
    if settings.api_delay_seconds <= 0 or not is_heavy(params):
        return
    host = httpx.URL(url).host
    interval = HEAVY_INTERVAL_WITH_KEY if keys.openalex_key() else HEAVY_INTERVAL
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


async def get(
    client: httpx.AsyncClient, url: str, params: dict, headers: dict | None = None
) -> httpx.Response:
    """GET com nova tentativa quando a base pede calma (429) ou falha por instantes (5xx)."""
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        await throttle(url, params)
        resp = None
        try:
            resp = await client.get(url, params=params, headers=headers)
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
    # O que foi corrigido na estratégia antes de enviar (`código` ou `código: detalhe`)
    corrections: list[str] = field(default_factory=list)
    # A estratégia compilada para a base, como foi enviada
    strategy: str = ""


# --- OpenAlex ------------------------------------------------------------------


def openalex_params() -> dict:
    s = get_settings()
    params = {"mailto": s.enrichment_contact_email} if s.enrichment_contact_email else {}
    if key := keys.openalex_key():
        params["api_key"] = key
    return params


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


async def openalex_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    url = get_settings().openalex_url.rstrip("/") + "/works"
    params = {**openalex_params(), "filter": ",".join(strategy.filters), "per-page": 5}
    data = (await get(client, url, params)).json()
    return Preview(
        int((data.get("meta") or {}).get("count") or 0),
        [openalex_work(w) for w in data.get("results") or []],
    )


async def openalex_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    params = {"filter": ",".join(strategy.filters)}
    async for total, works in openalex_pages(client, params, limit):
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


# --- ERIC (educação) -----------------------------------------------------------------

ERIC_PAGE = 200


def eric_record(doc: dict) -> ParsedRecord:
    ident = str(doc.get("id") or "")
    return ParsedRecord(
        title=html.unescape(doc.get("title") or ""),
        abstract=html.unescape(doc.get("description") or ""),
        authors=list(doc.get("author") or []),
        year=doc.get("publicationdateyear"),
        journal=doc.get("source") or "",
        doi=doc.get("doi"),
        url=f"https://eric.ed.gov/?id={ident}" if ident else "",
        keywords=list(doc.get("subject") or []),
        language="; ".join(doc.get("language") or []),
        publication_type="; ".join(doc.get("publicationtype") or []),
        raw={"eric": ident},
    ).clean()


async def eric_page(client: httpx.AsyncClient, query: str, start: int, rows: int) -> dict:
    url = get_settings().eric_url.rstrip("/") + "/"
    resp = await get(client, url, {"search": query, "format": "json", "start": start, "rows": rows})
    return resp.json().get("response") or {}


async def eric_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    data = await eric_page(client, strategy.native, 0, 5)
    return Preview(int(data.get("numFound") or 0), [eric_record(d) for d in data.get("docs") or []])


async def eric_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    seen = 0
    while seen < limit:
        data = await eric_page(client, strategy.native, seen, min(ERIC_PAGE, limit - seen))
        docs = data.get("docs") or []
        if not docs:
            return
        seen += len(docs)
        yield int(data.get("numFound") or 0), [eric_record(d) for d in docs]
        await pause()


# --- ClinicalTrials.gov (registro de ensaios) ----------------------------------------

CT_FIELDS = (
    "NCTId|BriefTitle|OfficialTitle|BriefSummary|Condition|Keyword|StartDate|"
    "StudyFirstPostDate|LeadSponsorName|StudyType|OverallStatus"
)
CT_PAGE = 500


def clinicaltrials_record(study: dict) -> ParsedRecord:
    p = study.get("protocolSection") or {}
    ident = p.get("identificationModule") or {}
    cond = p.get("conditionsModule") or {}
    status = p.get("statusModule") or {}
    nct = ident.get("nctId") or ""
    start = (status.get("startDateStruct") or {}).get("date") or (
        (status.get("studyFirstPostDateStruct") or {}).get("date") or ""
    )
    sponsor = ((p.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name")
    return ParsedRecord(
        title=ident.get("briefTitle") or ident.get("officialTitle") or "",
        abstract=(p.get("descriptionModule") or {}).get("briefSummary") or "",
        authors=[sponsor] if sponsor else [],
        year=int(start[:4]) if start[:4].isdigit() else None,
        journal="ClinicalTrials.gov",
        url=f"https://clinicaltrials.gov/study/{nct}" if nct else "",
        keywords=[*(cond.get("conditions") or []), *(cond.get("keywords") or [])],
        publication_type=f"Trial registry ({(p.get('designModule') or {}).get('studyType', '')})".replace(
            " ()", ""
        ),
        raw={"nct": nct},
    ).clean()


async def clinicaltrials_page(
    client: httpx.AsyncClient, query: str, size: int, token: str | None
) -> dict:
    url = get_settings().clinicaltrials_url.rstrip("/") + "/studies"
    params = {"query.term": query, "pageSize": size, "countTotal": "true", "fields": CT_FIELDS}
    if token:
        params["pageToken"] = token
    return (await get(client, url, params)).json()


async def clinicaltrials_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    data = await clinicaltrials_page(client, strategy.native, 5, None)
    return Preview(
        int(data.get("totalCount") or 0),
        [clinicaltrials_record(s) for s in data.get("studies") or []],
    )


async def clinicaltrials_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    token, seen = None, 0
    while seen < limit:
        data = await clinicaltrials_page(client, strategy.native, min(CT_PAGE, limit - seen), token)
        studies = data.get("studies") or []
        if not studies:
            return
        seen += len(studies)
        yield int(data.get("totalCount") or 0), [clinicaltrials_record(s) for s in studies]
        token = data.get("nextPageToken")
        if not token:
            return
        await pause()


# --- arXiv ----------------------------------------------------------------------------

ARXIV_PAGE = 200
# O arXiv pede, no máximo, uma requisição a cada 3 segundos
ARXIV_INTERVAL = 3.0
_ATOM = "{http://www.w3.org/2005/Atom}"
_OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def _text(node, tag: str) -> str:
    found = node.find(tag)
    return " ".join((found.text or "").split()) if found is not None else ""


def arxiv_entry(entry) -> ParsedRecord:
    link = ""
    for ln in entry.findall(f"{_ATOM}link"):
        if ln.get("rel") == "alternate":
            link = ln.get("href") or ""
    published = _text(entry, f"{_ATOM}published")
    return ParsedRecord(
        title=_text(entry, f"{_ATOM}title"),
        abstract=_text(entry, f"{_ATOM}summary"),
        authors=[_text(a, f"{_ATOM}name") for a in entry.findall(f"{_ATOM}author")],
        year=int(published[:4]) if published[:4].isdigit() else None,
        journal=_text(entry, f"{_ARXIV}journal_ref") or "arXiv",
        doi=_text(entry, f"{_ARXIV}doi") or None,
        url=link,
        keywords=[c.get("term") or "" for c in entry.findall(f"{_ATOM}category")],
        publication_type="Preprint",
        raw={"arxiv": _text(entry, f"{_ATOM}id").rsplit("/abs/", 1)[-1]},
    ).clean()


async def arxiv_page(
    client: httpx.AsyncClient, query: str, start: int, size: int
) -> tuple[int, list[ParsedRecord]]:
    url = get_settings().arxiv_url.rstrip("/") + "/query"
    resp = await get(client, url, {"search_query": query, "start": start, "max_results": size})
    try:
        root = ElementTree.fromstring(resp.content)
    except Exception as exc:  # defusedxml levanta vários tipos
        raise SourceError("arxiv_invalid_answer") from exc
    total = int(_text(root, f"{_OPENSEARCH}totalResults") or 0)
    records = []
    for entry in root.findall(f"{_ATOM}entry"):
        if "/api/errors" in _text(entry, f"{_ATOM}id"):
            raise SourceError(_text(entry, f"{_ATOM}summary")[:300] or "arxiv_error")
        records.append(arxiv_entry(entry))
    return total, records


async def arxiv_wait() -> None:
    if get_settings().api_delay_seconds > 0:
        await asyncio.sleep(ARXIV_INTERVAL)


async def arxiv_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    total, records = await arxiv_page(client, strategy.native, 0, 5)
    return Preview(total, records)


async def arxiv_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    seen = 0
    while seen < limit:
        total, records = await arxiv_page(
            client, strategy.native, seen, min(ARXIV_PAGE, limit - seen)
        )
        if not records:
            return
        seen += len(records)
        yield total, records
        if seen >= total:
            return
        await arxiv_wait()


# --- DOAJ (revistas de acesso aberto) -------------------------------------------------

DOAJ_PAGE = 100


def doaj_record(item: dict) -> ParsedRecord:
    b = item.get("bibjson") or {}
    journal = b.get("journal") or {}
    ids = {i.get("type"): i.get("id") for i in b.get("identifier") or [] if isinstance(i, dict)}
    first, last = str(b.get("start_page") or ""), str(b.get("end_page") or "")
    link = next((ln.get("url") for ln in b.get("link") or [] if ln.get("type") == "fulltext"), "")
    year = str(b.get("year") or "")
    return ParsedRecord(
        title=b.get("title") or "",
        abstract=b.get("abstract") or "",
        authors=[a.get("name", "") for a in b.get("author") or []],
        year=int(year) if year.isdigit() else None,
        journal=journal.get("title") or "",
        volume=str(journal.get("volume") or ""),
        issue=str(journal.get("number") or ""),
        pages=f"{first}-{last}" if first and last and first != last else first,
        doi=ids.get("doi"),
        url=link or "",
        keywords=list(b.get("keywords") or []),
        language="; ".join(journal.get("language") or []),
        raw={"doaj": item.get("id") or ""},
    ).clean()


async def doaj_page(client: httpx.AsyncClient, query: str, page: int, size: int) -> dict:
    # A consulta vai no caminho da URL; o DOAJ recusa curingas, que já saíram da estratégia
    url = f"{get_settings().doaj_url.rstrip('/')}/search/articles/{quote(query, safe='')}"
    return (await get(client, url, {"page": page, "pageSize": size})).json()


async def doaj_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    data = await doaj_page(client, strategy.native, 1, 5)
    return Preview(int(data.get("total") or 0), [doaj_record(i) for i in data.get("results") or []])


async def doaj_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    page, seen = 1, 0
    while seen < limit:
        data = await doaj_page(client, strategy.native, page, min(DOAJ_PAGE, limit - seen))
        items = data.get("results") or []
        if not items:
            return
        seen += len(items)
        yield int(data.get("total") or 0), [doaj_record(i) for i in items]
        page += 1
        await pause()


# --- OpenAIRE (repositórios, literatura cinza, teses) -----------------------------------

OPENAIRE_PAGE = 100


def openaire_params(strategy: Compiled) -> dict:
    """Cada filtro da estratégia é `parâmetro=valor`; só publicações."""
    params = {"type": "publication"}
    for item in strategy.filters:
        key, _, value = item.partition("=")
        params[key] = value
    return params


def openaire_record(item: dict) -> ParsedRecord:
    pids = {p.get("scheme"): p.get("value") for p in item.get("pids") or [] if isinstance(p, dict)}
    container = item.get("container") or {}
    date = str(item.get("publicationDate") or "")
    descriptions = item.get("descriptions") or []
    subjects = [(s.get("subject") or {}).get("value", "") for s in item.get("subjects") or [] if s]
    first, last = str(container.get("sp") or ""), str(container.get("ep") or "")
    return ParsedRecord(
        title=item.get("mainTitle") or "",
        abstract=descriptions[0] if descriptions else "",
        authors=[a.get("fullName", "") for a in item.get("authors") or []],
        year=int(date[:4]) if date[:4].isdigit() else None,
        journal=container.get("name") or "",
        volume=str(container.get("vol") or ""),
        issue=str(container.get("iss") or ""),
        pages=f"{first}-{last}" if first and last and first != last else first,
        doi=pids.get("doi"),
        pmid=pids.get("pmid"),
        keywords=[k for k in subjects if k],
        language=((item.get("language") or {}).get("label") or ""),
        publication_type=item.get("type") or "",
        raw={"openaire": item.get("id") or ""},
    ).clean()


async def openaire_page(
    client: httpx.AsyncClient, strategy: Compiled, size: int, cursor: str
) -> dict:
    url = get_settings().openaire_url.rstrip("/") + "/researchProducts"
    params = {**openaire_params(strategy), "pageSize": size, "cursor": cursor}
    return (await get(client, url, params)).json()


async def openaire_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    data = await openaire_page(client, strategy, 5, "*")
    return Preview(
        int((data.get("header") or {}).get("numFound") or 0),
        [openaire_record(i) for i in data.get("results") or []],
    )


async def openaire_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    cursor, seen = "*", 0
    while cursor and seen < limit:
        data = await openaire_page(client, strategy, min(OPENAIRE_PAGE, limit - seen), cursor)
        items = data.get("results") or []
        if not items:
            return
        seen += len(items)
        header = data.get("header") or {}
        yield int(header.get("numFound") or 0), [openaire_record(i) for i in items]
        cursor = header.get("nextCursor") or ""
        await pause()


# --- Semantic Scholar -------------------------------------------------------------------

S2_FIELDS = "title,abstract,year,authors,venue,externalIds,url,publicationTypes,fieldsOfStudy"
S2_PREVIEW_FIELDS = "title,year,authors,venue,externalIds"


def semanticscholar_record(paper: dict) -> ParsedRecord:
    ext = paper.get("externalIds") or {}
    return ParsedRecord(
        title=paper.get("title") or "",
        abstract=paper.get("abstract") or "",
        authors=[a.get("name", "") for a in paper.get("authors") or []],
        year=paper.get("year"),
        journal=paper.get("venue") or "",
        doi=ext.get("DOI"),
        pmid=str(ext["PubMed"]) if ext.get("PubMed") else None,
        url=paper.get("url") or "",
        keywords=list(paper.get("fieldsOfStudy") or []),
        publication_type="; ".join(paper.get("publicationTypes") or []),
        raw={"semanticscholar": paper.get("paperId") or ""},
    ).clean()


def semanticscholar_params(strategy: Compiled, fields: str) -> dict:
    params = {"fields": fields}
    for item in strategy.filters:
        key, _, value = item.partition("=")
        params[key] = value
    return params


async def semanticscholar_page(
    client: httpx.AsyncClient, strategy: Compiled, fields: str, token: str | None
) -> dict:
    s = get_settings()
    url = s.semantic_scholar_url.rstrip("/") + "/paper/search/bulk"
    params = semanticscholar_params(strategy, fields)
    if token:
        params["token"] = token
    headers = {"x-api-key": s.semantic_scholar_api_key} if s.semantic_scholar_api_key else None
    try:
        return (await get(client, url, params, headers)).json()
    except SourceError as exc:
        if "http 429" in str(exc) and not s.semantic_scholar_api_key:
            raise SourceError(f"semantic_scholar_key_needed: {exc}") from exc
        raise


async def semanticscholar_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
    data = await semanticscholar_page(client, strategy, S2_PREVIEW_FIELDS, None)
    papers = data.get("data") or []
    return Preview(int(data.get("total") or 0), [semanticscholar_record(p) for p in papers[:5]])


async def semanticscholar_fetch(
    client: httpx.AsyncClient, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    token, seen = None, 0
    while seen < limit:
        data = await semanticscholar_page(client, strategy, S2_FIELDS, token)
        papers = (data.get("data") or [])[: limit - seen]
        if not papers:
            return
        seen += len(papers)
        yield int(data.get("total") or 0), [semanticscholar_record(p) for p in papers]
        token = data.get("token")
        if not token:
            return
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


def _collection_filter(strategy: Compiled, issn_filter: str) -> str:
    return ",".join([*strategy.filters, issn_filter])


async def collection_preview(
    client: httpx.AsyncClient, collection: str, strategy: Compiled
) -> Preview:
    url = get_settings().openalex_url.rstrip("/") + "/works"
    total, sample = 0, []
    for flt in _issn_filters(await collection_issns(client, collection)):
        params = {
            **openalex_params(),
            "filter": _collection_filter(strategy, flt),
            "per-page": 5,
        }
        data = (await get(client, url, params)).json()
        total += int((data.get("meta") or {}).get("count") or 0)
        if len(sample) < 5:
            sample += [openalex_work(w) for w in data.get("results") or []][: 5 - len(sample)]
        await pause()
    return Preview(total, sample)


async def collection_fetch(
    client: httpx.AsyncClient, collection: str, strategy: Compiled, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    """Um lote de revistas por vez. O total acumula as contagens de cada lote; ao atingir o
    limite, os lotes restantes só são contados, para o total informado ser o da base inteira."""
    url = get_settings().openalex_url.rstrip("/") + "/works"
    total = seen = 0
    for flt in _issn_filters(await collection_issns(client, collection)):
        params = {"filter": _collection_filter(strategy, flt)}
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
    async def preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
        return await collection_preview(client, collection, strategy)

    def fetch(client: httpx.AsyncClient, strategy: Compiled, limit: int):
        return collection_fetch(client, collection, strategy, limit)

    return (label, preview, fetch)


def _text_source(label: str, preview, fetch):
    """PubMed e Europe PMC recebem a estratégia como texto já compilada."""

    async def run_preview(client: httpx.AsyncClient, strategy: Compiled) -> Preview:
        return await preview(client, strategy.native)

    def run_fetch(client: httpx.AsyncClient, strategy: Compiled, limit: int):
        return fetch(client, strategy.native, limit)

    return (label, run_preview, run_fetch)


SOURCES = {
    "pubmed": _text_source("PubMed", pubmed_preview, pubmed_fetch),
    "openalex": ("OpenAlex", openalex_preview, openalex_fetch),
    "europepmc": _text_source("Europe PMC", europepmc_preview, europepmc_fetch),
    "preprints": _text_source("Preprints (Europe PMC)", europepmc_preview, europepmc_fetch),
    "eric": ("ERIC", eric_preview, eric_fetch),
    "clinicaltrials": ("ClinicalTrials.gov", clinicaltrials_preview, clinicaltrials_fetch),
    "arxiv": ("arXiv", arxiv_preview, arxiv_fetch),
    "doaj": ("DOAJ", doaj_preview, doaj_fetch),
    "openaire": ("OpenAIRE", openaire_preview, openaire_fetch),
    "semanticscholar": (
        "Semantic Scholar",
        semanticscholar_preview,
        semanticscholar_fetch,
    ),
    "scielo": _collection_source("SciELO (via OpenAlex)", "scl"),
    "pepsic": _collection_source("PePSIC (via OpenAlex)", "psi"),
}
