"""PDFs dos registros: anexar, casar arquivos de um ZIP e buscar versões de acesso aberto."""

import io
import ipaddress
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath

import httpx
from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.models import Project, Record
from revalli.modules.fulltext import storage
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
    data: bytes,
    user_id: uuid.UUID | None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    records = await candidate_records(db, project)
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PDFError("invalid_zip") from exc
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
                db, project.id, m.record, content, name, source="zip", user_id=user_id, info=info
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


def _public_url(url: str) -> bool:
    """Recusa endereços internos: a URL vem de uma base externa e não deve alcançar a rede local."""
    try:
        u = httpx.URL(url)
    except httpx.InvalidURL:
        return False
    if u.scheme not in ("http", "https") or not u.host:
        return False
    host = u.host.lower()
    if (
        host == "localhost"
        or host.endswith((".local", ".internal", ".localhost"))
        or "." not in host
    ):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


async def _download(client: httpx.AsyncClient, url: str) -> bytes | None:
    if not _public_url(url):
        return None
    limit = max_pdf_bytes()
    try:
        async with client.stream("GET", url, follow_redirects=True, timeout=60) as resp:
            if resp.status_code != 200:
                return None
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    return None
                chunks.append(chunk)
    except httpx.HTTPError:
        return None
    data = b"".join(chunks)
    return data if data[:1024].lstrip().startswith(b"%PDF-") else None


async def find_open_access(
    db: AsyncSession,
    project: Project,
    client: httpx.AsyncClient | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
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
        if r.id not in with_pdf and r.doi
    ]
    stats = {"checked": len(records), "found": 0, "downloaded": 0}
    params = (
        {"mailto": settings.enrichment_contact_email} if settings.enrichment_contact_email else {}
    )
    own = client is None
    client = client or httpx.AsyncClient(
        base_url=settings.openalex_url,
        timeout=30,
        headers={"User-Agent": "ReValli (self-hosted literature review tool)"},
    )
    try:
        by_doi = {r.doi: r for r in records}
        dois = list(by_doi)
        done = 0
        for i in range(0, len(dois), 50):
            chunk = dois[i : i + 50]
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
            for work in resp.json().get("results", []):
                rec = by_doi.get(normalize_doi(work.get("doi")))
                urls = _pdf_urls(work)
                if rec is None or not urls:
                    continue
                stats["found"] += 1
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
                            f"{rec.doi.replace('/', '_')}.pdf",
                            source="open_access",
                            source_url=url,
                        )
                    except PDFError:
                        continue
                    stats["downloaded"] += 1
                    await db.commit()
                    break
            done += len(chunk)
            if progress:
                progress(done, len(records))
    finally:
        if own:
            await client.aclose()
    return stats
