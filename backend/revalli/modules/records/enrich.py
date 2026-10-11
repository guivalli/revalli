"""Completa metadados faltantes (resumo, DOI, PMID, ano) usando a API pública do OpenAlex.

Só preenche campos vazios; nunca sobrescreve o que veio da base original.
"""

import uuid
from collections.abc import Callable

import httpx
from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.modules.imports.normalize import normalize_doi, normalize_pmid, normalize_title
from revalli.modules.records.models import Record

BATCH = 50
TITLE_MATCH = 95


def abstract_from_index(index: dict | None) -> str:
    if not index:
        return ""
    positions = [(pos, word) for word, poss in index.items() for pos in poss]
    return " ".join(word for _, word in sorted(positions))


def _apply(record: Record, work: dict) -> list[str]:
    filled = []
    ids = work.get("ids") or {}
    abstract = abstract_from_index(work.get("abstract_inverted_index"))
    if not record.abstract and abstract:
        record.abstract = abstract
        filled.append("abstract")
    doi = normalize_doi(work.get("doi") or ids.get("doi"))
    if not record.doi and doi:
        record.doi = doi
        filled.append("doi")
    pmid = normalize_pmid((ids.get("pmid") or "").rsplit("/", 1)[-1])
    if not record.pmid and pmid:
        record.pmid = pmid
        filled.append("pmid")
    if not record.year and work.get("publication_year"):
        record.year = work["publication_year"]
        filled.append("year")
    if filled:
        record.enriched = {**(record.enriched or {}), **dict.fromkeys(filled, "openalex")}
    return filled


async def enrich_project(
    db: AsyncSession,
    project_id: uuid.UUID,
    client: httpx.AsyncClient | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    settings = get_settings()
    if not settings.enrichment_enabled:
        return {"skipped": "disabled"}
    records = (
        (
            await db.execute(
                select(Record).where(
                    Record.project_id == project_id,
                    or_(Record.abstract == "", Record.doi.is_(None)),
                )
            )
        )
        .scalars()
        .all()
    )
    params = (
        {"mailto": settings.enrichment_contact_email} if settings.enrichment_contact_email else {}
    )
    own_client = client is None
    client = client or httpx.AsyncClient(base_url=settings.openalex_url, timeout=30)
    stats = {"checked": len(records), "updated": 0, "fields": 0}
    try:
        by_doi = {r.doi: r for r in records if r.doi}
        by_pmid = {r.pmid: r for r in records if r.pmid and not r.doi}
        done = 0
        for key, mapping, prefix in (("doi", by_doi, "https://doi.org/"), ("pmid", by_pmid, "")):
            values = list(mapping)
            for i in range(0, len(values), BATCH):
                chunk = values[i : i + BATCH]
                flt = f"{key}:" + "|".join(prefix + v for v in chunk)
                resp = await client.get(
                    "/works", params={**params, "filter": flt, "per-page": BATCH}
                )
                resp.raise_for_status()
                for work in resp.json().get("results", []):
                    ids = work.get("ids") or {}
                    match_key = (
                        normalize_doi(work.get("doi"))
                        if key == "doi"
                        else normalize_pmid((ids.get("pmid") or "").rsplit("/", 1)[-1])
                    )
                    rec = mapping.get(match_key)
                    if rec is not None:
                        n = len(_apply(rec, work))
                        stats["fields"] += n
                        stats["updated"] += 1 if n else 0
                done += len(chunk)
                if progress:
                    progress(done, len(records))

        # Sem DOI nem PMID: busca pelo título e só aceita casamento quase exato
        for rec in [r for r in records if not r.doi and not r.pmid and r.title]:
            resp = await client.get(
                "/works", params={**params, "search": rec.title[:300], "per-page": 3}
            )
            resp.raise_for_status()
            target = normalize_title(rec.title)
            for work in resp.json().get("results", []):
                score = fuzz.token_sort_ratio(target, normalize_title(work.get("title") or ""))
                year_ok = (
                    not rec.year
                    or not work.get("publication_year")
                    or abs(rec.year - work["publication_year"]) <= 1
                )
                if score >= TITLE_MATCH and year_ok:
                    n = len(_apply(rec, work))
                    stats["fields"] += n
                    stats["updated"] += 1 if n else 0
                    break
            done += 1
            if progress:
                progress(done, len(records))
        await db.commit()
    finally:
        if own_client:
            await client.aclose()
    return stats
