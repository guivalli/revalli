"""Atualizações periódicas: repete uma busca (ou relê um arquivo numa URL) e importa só o novo."""

import uuid
from collections.abc import Callable
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core import safefetch
from revalli.core.config import get_settings
from revalli.core.db import utcnow
from revalli.models import Record
from revalli.modules.ai.crypto import decrypt
from revalli.modules.imports.normalize import ParsedRecord, normalize_title
from revalli.modules.imports.parsers import ImportFormatError, parse_file
from revalli.modules.sources import clients, keys
from revalli.modules.sources.fields import compile_strategy
from revalli.modules.sources.service import save_search
from revalli.modules.watches.models import Watch

# Permite trocar o transporte nos testes (sem rede)
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


MAX_FEED_BYTES = 100 * 1024 * 1024
MIN_TITLE_KEY = 20  # títulos curtos demais não bastam para dizer que dois registros são o mesmo


class Known:
    """Identificadores do que o projeto já tem, para não importar de novo a cada rodada."""

    def __init__(self) -> None:
        self.dois: set[str] = set()
        self.pmids: set[str] = set()
        self.titles: set[str] = set()

    def add(self, doi: str | None, pmid: str | None, title: str) -> None:
        if doi:
            self.dois.add(doi)
        if pmid:
            self.pmids.add(pmid)
        key = normalize_title(title)
        if len(key) >= MIN_TITLE_KEY:
            self.titles.add(key)

    def has(self, p: ParsedRecord) -> bool:
        if (p.doi and p.doi in self.dois) or (p.pmid and p.pmid in self.pmids):
            return True
        key = normalize_title(p.title)
        return len(key) >= MIN_TITLE_KEY and key in self.titles


async def known_records(db: AsyncSession, project_id: uuid.UUID) -> Known:
    known = Known()
    rows = await db.execute(
        select(Record.doi, Record.pmid, Record.title).where(Record.project_id == project_id)
    )
    for doi, pmid, title in rows.all():
        known.add(doi, pmid, title or "")
    return known


def only_new(records: list[ParsedRecord], known: Known) -> list[ParsedRecord]:
    out: list[ParsedRecord] = []
    for p in records:
        if p.is_empty or known.has(p):
            continue
        known.add(p.doi, p.pmid, p.title)  # repetidos dentro do próprio lote também saem
        out.append(p)
    return out


async def _fetch_search(watch: Watch, progress) -> tuple[str, int, list[ParsedRecord]]:
    name, _, fetch = clients.SOURCES[watch.source]
    # A estratégia salva é texto; é corrigida para a base do mesmo jeito que na busca
    strategy = compile_strategy(watch.source, watch.query)
    limit = get_settings().api_search_max
    found: list[ParsedRecord] = []
    total = 0
    async with clients.http_client() as c:
        async for total, batch in fetch(c, strategy, limit):
            found.extend(r for r in batch if not r.is_empty)
            if progress:
                progress(len(found), min(total, limit))
    return name, total, found[:limit]


async def _fetch_feed(watch: Watch) -> tuple[str, int, list[ParsedRecord]]:
    secret = decrypt(watch.secret_enc)
    headers = {"Authorization": secret} if secret else None
    async with httpx.AsyncClient(
        headers={"User-Agent": "ReValli (self-hosted literature review tool)"},
        transport=_transport,
    ) as c:
        got = await safefetch.get_bytes(
            c, watch.url, max_bytes=MAX_FEED_BYTES, secret_headers=headers
        )
    filename = urlsplit(got.url).path.rsplit("/", 1)[-1]
    try:
        _, records = parse_file(filename, got.data)
    except ImportFormatError as exc:
        raise safefetch.FetchError("unknown_format") from exc
    host = urlsplit(watch.url).hostname or ""
    return f"Biblioteca externa ({host})", len(records), records


def schedule_next(watch: Watch, *, failed: bool = False) -> None:
    delay = timedelta(days=1) if failed else timedelta(days=watch.every_days)
    watch.next_run_at = utcnow() + delay


async def run_watch(
    db: AsyncSession, watch: Watch, progress: Callable[[int, int], None] | None = None
) -> dict:
    await keys.load(db)
    try:
        if watch.kind == "api_search":
            name, total, records = await _fetch_search(watch, progress)
        else:
            name, total, records = await _fetch_feed(watch)
    except (clients.SourceError, safefetch.FetchError) as exc:
        watch.last_run_at = utcnow()
        watch.last_status, watch.last_error, watch.last_new = "error", str(exc)[:500], 0
        schedule_next(watch, failed=True)
        await db.commit()
        return {"error": str(exc)[:500]}

    known = await known_records(db, watch.project_id)
    new = only_new(records, known)
    search_id = None
    if new:
        search = await save_search(
            db,
            watch.project_id,
            watch.created_by_id,
            source=f"{name} (atualização)",
            query=watch.query or watch.url,
            method="database",
            records=new,
            reported_count=total,
            notes=f"Atualização automática: {len(new)} novos de {len(records)} encontrados.",
        )
        search_id = str(search.id)
    watch.last_run_at = utcnow()
    watch.last_status, watch.last_error = "ok", ""
    watch.last_new, watch.last_found = len(new), len(records)
    watch.total_new += len(new)
    schedule_next(watch)
    await db.commit()
    return {"new": len(new), "found": len(records), "search_id": search_id}


# --- Agendador -------------------------------------------------------------------


async def due_watch_ids(db: AsyncSession) -> list[uuid.UUID]:
    rows = await db.execute(
        select(Watch.id).where(
            Watch.enabled, Watch.next_run_at.is_not(None), Watch.next_run_at <= utcnow()
        )
    )
    return list(rows.scalars())
