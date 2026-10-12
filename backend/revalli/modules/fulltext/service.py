"""PDFs dos registros: anexar, casar arquivos de um ZIP e buscar versões de acesso aberto."""

import asyncio
import io
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx
from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core import safefetch
from revalli.core.config import get_settings
from revalli.models import Project, Record
from revalli.modules.fulltext import finders, storage
from revalli.modules.fulltext.models import FilePage, RecordFile
from revalli.modules.fulltext.pdf import PDFError, PDFInfo, read_pdf
from revalli.modules.imports.normalize import normalize_doi, normalize_title
from revalli.modules.screening.models import Phase
from revalli.modules.screening.service import compute_states, eligible_ids_query

TITLE_MATCH = 90
ZIP_MAX_TOTAL = 3 * 1024**3


def max_pdf_bytes() -> int:
    return get_settings().max_pdf_mb * 1024 * 1024


async def attach(
    db: AsyncSession,
    project_id: uuid.UUID,
    record: Record,
    data: bytes,
    filename: str,
    *,
    source: str = "upload",
    source_url: str = "",
    user_id: uuid.UUID | None = None,
    info: PDFInfo | None = None,
) -> RecordFile:
    info = info or read_pdf(data)
    digest = storage.sha256(data)
    same = (
        await db.execute(
            select(RecordFile).where(RecordFile.record_id == record.id, RecordFile.sha256 == digest)
        )
    ).scalar_one_or_none()
    if same is not None:
        return same
    has_main = (
        await db.execute(
            select(func.count()).where(RecordFile.record_id == record.id, RecordFile.is_main)
        )
    ).scalar_one()
    storage.save(project_id, data)
    f = RecordFile(
        project_id=project_id,
        record_id=record.id,
        filename=PurePosixPath(filename or "arquivo.pdf").name[:500],
        sha256=digest,
        size=len(data),
        pages=len(info.pages),
        source=source,
        source_url=source_url[:2000],
        is_main=has_main == 0,
        has_text=info.has_text,
        uploaded_by_id=user_id,
    )
    db.add(f)
    await db.flush()
    db.add_all(FilePage(file_id=f.id, page=i + 1, text=t) for i, t in enumerate(info.pages))
    return f


async def delete_file(db: AsyncSession, f: RecordFile) -> None:
    project_id, digest, record_id, was_main = f.project_id, f.sha256, f.record_id, f.is_main
    await db.delete(f)
    await db.flush()
    used = (
        await db.execute(
            select(func.count()).where(
                RecordFile.project_id == project_id, RecordFile.sha256 == digest
            )
        )
    ).scalar_one()
    if was_main:
        # Promove o arquivo mais antigo restante a principal
        nxt = (
            await db.execute(
                select(RecordFile)
                .where(RecordFile.record_id == record_id)
                .order_by(RecordFile.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if nxt is not None:
            nxt.is_main = True
    await db.commit()
    storage.remove_if_unused(project_id, digest, used > 0)


# --- Casamento de arquivos com registros --------------------------------------------


async def candidate_records(db: AsyncSession, project: Project) -> list[Record]:
    """Registros que podem receber PDF: os da fase de texto completo; se ela estiver vazia,
    todos os registros únicos."""
    ids = list(await compute_states(db, project, Phase.full_text))
    if not ids:
        ids = list(
            (await db.execute(eligible_ids_query(project.id, Phase.title_abstract))).scalars()
        )
    if not ids:
        return []
    return list((await db.execute(select(Record).where(Record.id.in_(ids)))).scalars())


def _doi_from_filename(name: str) -> str | None:
    stem = PurePosixPath(name).stem
    if not stem.startswith("10."):
        return None
    # Barras não existem em nomes de arquivo: "10.1000_abc" ou "10.1000%2Fabc"
    return normalize_doi(stem.replace("%2F", "/").replace("%2f", "/").replace("_", "/", 1))


@dataclass
class Match:
    record: Record | None
    method: str
    score: int = 0


def match_record(records: list[Record], filename: str, info: PDFInfo) -> Match:
    by_doi = {r.doi: r for r in records if r.doi}
    for doi, method in ((info.doi, "doi_text"), (_doi_from_filename(filename), "doi_filename")):
        doi = normalize_doi(doi) if doi else None
        if doi and doi in by_doi:
            return Match(by_doi[doi], method, 100)
    first_page = normalize_title(info.pages[0][:1500]) if info.pages else ""
    probes = [normalize_title(x) for x in (info.title, PurePosixPath(filename).stem) if x]
    best, best_score, best_method = None, 0, ""
    for r in records:
        title = normalize_title(r.title)
        if len(title) < 15:
            continue
        for probe in probes:
            s = int(fuzz.token_set_ratio(title, probe))
            if s > best_score:
                best, best_score, best_method = r, s, "title"
        if first_page and len(title) >= 30:
            s = int(fuzz.partial_ratio(title, first_page))
            if s > best_score:
                best, best_score, best_method = r, s, "title_text"
    if best is not None and best_score >= TITLE_MATCH:
        return Match(best, best_method, best_score)
    return Match(None, "none", best_score)


async def import_zip(
    db: AsyncSession,
    project: Project,
    source: bytes | Path,
    user_id: uuid.UUID | None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """``source`` pode ser o caminho do ZIP no disco, para não carregar arquivos grandes na
    memória de uma vez."""
    records = await candidate_records(db, project)
    try:
        zf = zipfile.ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source)
    except zipfile.BadZipFile as exc:
        raise PDFError("invalid_zip") from exc
    with zf:
        entries = [
            i
            for i in zf.infolist()
            if not i.is_dir()
            and i.filename.lower().endswith(".pdf")
            and not PurePosixPath(i.filename).name.startswith("._")
        ]
        if sum(i.file_size for i in entries) > ZIP_MAX_TOTAL:
            raise PDFError("zip_too_large")
        stats = {"files": len(entries), "matched": 0, "already": 0, "unmatched": [], "invalid": []}
        for n, entry in enumerate(entries, 1):
            name = PurePosixPath(entry.filename).name
            if entry.file_size > max_pdf_bytes():
                stats["invalid"].append(name)
                continue
            content = zf.read(entry)
            try:
                info = read_pdf(content)
            except PDFError:
                stats["invalid"].append(name)
                continue
            m = match_record(records, name, info)
            if m.record is None:
                stats["unmatched"].append(name)
            else:
                before = (
                    await db.execute(
                        select(func.count()).where(
                            RecordFile.record_id == m.record.id,
                            RecordFile.sha256 == storage.sha256(content),
                        )
                    )
                ).scalar_one()
                await attach(
                    db,
                    project.id,
                    m.record,
                    content,
                    name,
                    source="zip",
                    user_id=user_id,
                    info=info,
                )
                stats["already" if before else "matched"] += 1
            await db.commit()
            if progress:
                progress(n, len(entries))
        stats["unmatched"] = stats["unmatched"][:200]
        stats["invalid"] = stats["invalid"][:200]
        return stats


# --- Acesso aberto -----------------------------------------------------------------------


def _pdf_urls(work: dict) -> list[str]:
    urls = []
    for loc in [work.get("best_oa_location") or {}, *(work.get("locations") or [])]:
        url = (loc or {}).get("pdf_url")
        if url and url not in urls:
            urls.append(url)
    return urls


async def _download(client: httpx.AsyncClient, url: str) -> bytes | None:
    """Baixa um PDF de uma URL que veio de uma base externa, sem alcançar a rede interna."""
    try:
        got = await safefetch.get_bytes(client, url, max_bytes=max_pdf_bytes())
    except safefetch.FetchError:
        return None
    return got.data if got.data[:1024].lstrip().startswith(b"%PDF-") else None


async def find_open_access(
    db: AsyncSession,
    project: Project,
    client: httpx.AsyncClient | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Procura e baixa a versão aberta dos estudos do texto completo que ainda não têm PDF.

    Ordem: OpenAlex (em lote, por DOI), Unpaywall, Europe PMC e a página do artigo. O primeiro
    PDF válido vale; o que ninguém achar aparece na lista de pendentes para baixar à mão."""
    settings = get_settings()
    if not settings.enrichment_enabled:
        return {"skipped": "disabled"}
    ids = list(await compute_states(db, project, Phase.full_text))
    with_pdf = set(
        (await db.execute(select(RecordFile.record_id).where(RecordFile.record_id.in_(ids))))
        .scalars()
        .all()
    )
    records = [
        r
        for r in (await db.execute(select(Record).where(Record.id.in_(ids)))).scalars()
        if r.id not in with_pdf and (r.doi or r.pmid or r.url)
    ]
    stats: dict = {"checked": len(records), "found": 0, "downloaded": 0, "by_source": {}}
    params = (
        {"mailto": settings.enrichment_contact_email} if settings.enrichment_contact_email else {}
    )
    own = client is None
    client = client or httpx.AsyncClient(
        base_url=settings.openalex_url,
        timeout=30,
        headers={"User-Agent": "ReValli (self-hosted literature review tool)"},
    )
    total = 2 * len(records)
    done = 0
    got: set[uuid.UUID] = set()
    found: set[uuid.UUID] = set()
    errors: dict[str, int] = {}

    async def take(rec: Record, urls: list[str], label: str) -> bool:
        if urls:
            found.add(rec.id)
        for url in urls[:3]:
            data = await _download(client, url)
            if data is None:
                continue
            try:
                await attach(
                    db,
                    project.id,
                    rec,
                    data,
                    f"{(rec.doi or rec.id.hex).replace('/', '_')}.pdf",
                    source="open_access",
                    source_url=url,
                )
            except PDFError:
                continue
            stats["downloaded"] += 1
            stats["by_source"][label] = stats["by_source"].get(label, 0) + 1
            got.add(rec.id)
            await db.commit()
            return True
        return False

    try:
        # 1) OpenAlex, em lotes de 50 DOIs
        by_doi = {r.doi: r for r in records if r.doi}
        dois = list(by_doi)
        for i in range(0, len(dois), 50):
            chunk = dois[i : i + 50]
            try:
                resp = await client.get(
                    "/works",
                    params={
                        **params,
                        "filter": "doi:" + "|".join(f"https://doi.org/{d}" for d in chunk),
                        "per-page": 50,
                        "select": "doi,best_oa_location,locations",
                    },
                )
                resp.raise_for_status()
                works = resp.json().get("results", [])
            except (httpx.HTTPError, ValueError):
                errors["openalex"] = errors.get("openalex", 0) + 1
                works = []
            for work in works:
                rec = by_doi.get(normalize_doi(work.get("doi")))
                if rec is not None:
                    await take(rec, _pdf_urls(work), "openalex")
            done += len(chunk)
            if progress:
                progress(done, total)

        # 2) Os que sobraram, um a um: Unpaywall, Europe PMC e a página do artigo
        done = len(records)
        for rec in records:
            if rec.id not in got:
                await _chain(rec, take, client, stats, errors)
            done += 1
            if progress:
                progress(done, total)
    finally:
        if own:
            await client.aclose()
    stats["found"] = len(found)
    if errors:
        stats["errors"] = errors
    return stats


async def _chain(rec: Record, take, client: httpx.AsyncClient, stats: dict, errors: dict) -> None:
    landing: list[str] = []

    async def attempt(label: str, call) -> bool:
        try:
            pdfs, pages = await call()
        except PermissionError:
            # Falta o e-mail de contato exigido pelo Unpaywall: avisa uma vez e segue
            stats.setdefault("skipped", [])
            if label not in stats["skipped"]:
                stats["skipped"].append(label)
            return False
        except (httpx.HTTPError, safefetch.FetchError, ValueError, KeyError):
            errors[label] = errors.get(label, 0) + 1
            return False
        landing.extend(pages)
        return await take(rec, pdfs, label)

    if rec.doi:
        if await attempt("unpaywall", lambda: finders.unpaywall(client, rec.doi)):
            return
    if rec.pmid or rec.doi:
        if await attempt("europepmc", lambda: finders.europepmc(client, rec.doi, rec.pmid)):
            return
    candidates = list(dict.fromkeys([rec.url, finders.doi_link(rec.doi), *landing]))
    delay = get_settings().api_delay_seconds
    for page in [c for c in candidates if c][:4]:
        if delay > 0:
            await asyncio.sleep(delay)

        async def from_page(page=page):
            return await finders.article_page(client, page), []

        if await attempt("article_page", from_page):
            return
