"""Clientes das APIs públicas de busca: PubMed (E-utilities), OpenAlex e Europe PMC.

Cada fonte sabe contar os resultados de uma busca (com uma amostra, para a pessoa conferir a
string antes de importar) e trazer os registros em lotes, já no formato do importador.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

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


async def get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    try:
        resp = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise SourceError(f"connection: {type(exc).__name__}") from exc
    if resp.status_code >= 400:
        raise SourceError(f"http {resp.status_code}: {resp.text[:200]}")
    return resp


@dataclass
class Preview:
    count: int
    sample: list[ParsedRecord]


# --- OpenAlex ------------------------------------------------------------------


def openalex_params() -> dict:
    email = get_settings().enrichment_contact_email
    return {"mailto": email} if email else {}


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
    resp = await get(client, url, {**openalex_params(), "search": query, "per-page": 5})
    data = resp.json()
    return Preview(
        int((data.get("meta") or {}).get("count") or 0),
        [openalex_work(w) for w in data.get("results") or []],
    )


async def openalex_fetch(
    client: httpx.AsyncClient, query: str, limit: int
) -> AsyncIterator[tuple[int, list[ParsedRecord]]]:
    async for total, works in openalex_pages(client, {"search": query}, limit):
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
    return Preview(int(data.get("count") or 0), sample)


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


SOURCES = {
    "pubmed": ("PubMed", pubmed_preview, pubmed_fetch),
    "openalex": ("OpenAlex", openalex_preview, openalex_fetch),
    "europepmc": ("Europe PMC", europepmc_preview, europepmc_fetch),
}
