"""Detecção de duplicatas dentro de um projeto.

Regras:
1. Mesmo DOI ou mesmo PMID: duplicata confirmada automaticamente
   (a menos que os títulos sejam muito diferentes, aí vai para revisão).
2. Título parecido (>= 92), ano igual ou vizinho e mesmo sobrenome do primeiro autor:
   vai para revisão manual. Se o título for praticamente idêntico (>= 98), com mesmo ano
   e mesmo autor, é confirmada automaticamente.
3. Pares marcados como "não é duplicata" nunca são agrupados de novo.
4. Grupos já confirmados por alguém são mantidos; registros novos que casarem com eles
   entram no grupo.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz, process
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.modules.imports.normalize import first_author_key, normalize_title
from revalli.modules.records.models import DuplicateGroup, DuplicateStatus, NotDuplicate, Record

TITLE_REVIEW = 92
TITLE_AUTO = 98
DOI_TITLE_SANITY = 70


@dataclass
class _Rec:
    id: uuid.UUID
    doi: str | None
    pmid: str | None
    title: str
    year: int | None
    author: str
    completeness: tuple
    group_id: uuid.UUID | None


class _UnionFind:
    def __init__(self):
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _completeness(r: Record) -> tuple:
    # Prefere o registro mais completo; em empate, o mais antigo
    return (
        bool(r.abstract),
        bool(r.doi),
        bool(r.pmid),
        len(r.abstract or ""),
        len(r.authors or []),
        -r.created_at.timestamp(),
    )


def find_edges(
    recs: list[_Rec], blocked: set[frozenset]
) -> list[tuple[uuid.UUID, uuid.UUID, str, int, bool]]:
    """Retorna pares (a, b, método, score, automático)."""
    edges = []

    def ok(a: _Rec, b: _Rec) -> bool:
        return frozenset((a.id, b.id)) not in blocked

    for key in ("doi", "pmid"):
        buckets: dict[str, list[_Rec]] = defaultdict(list)
        for r in recs:
            value = getattr(r, key)
            if value:
                buckets[value].append(r)
        for group in buckets.values():
            for i in range(1, len(group)):
                a, b = group[0], group[i]
                if not ok(a, b):
                    continue
                score = int(fuzz.token_sort_ratio(a.title, b.title)) if a.title and b.title else 100
                edges.append((a.id, b.id, key, score, score >= DOI_TITLE_SANITY))

    by_year: dict[int | None, list[int]] = defaultdict(list)
    for idx, r in enumerate(recs):
        if r.title and len(r.title) >= 10:
            by_year[r.year].append(idx)

    # Compara cada ano com ele mesmo e com o seguinte; registros sem ano, com todos
    blocks: list[tuple[list[int], list[int]]] = []
    for y in sorted(k for k in by_year if k is not None):
        blocks.append((by_year[y], by_year[y] + by_year.get(y + 1, [])))
    if by_year.get(None):
        blocks.append((by_year[None], [i for js in by_year.values() for i in js]))

    seen: set[tuple[int, int]] = set()
    for queries, choices in blocks:
        matrix = process.cdist(
            [recs[i].title for i in queries],
            [recs[j].title for j in choices],
            scorer=fuzz.token_sort_ratio,
            score_cutoff=TITLE_REVIEW,
            dtype=np.uint8,
            workers=-1,
        )
        for qi, cj in zip(*np.nonzero(matrix), strict=True):
            i, j = queries[qi], choices[cj]
            if i == j:
                continue
            pair = (min(i, j), max(i, j))
            if pair in seen:
                continue
            seen.add(pair)
            r, other = recs[pair[0]], recs[pair[1]]
            score = int(matrix[qi, cj])
            if r.doi and other.doi and r.doi != other.doi:
                continue
            if r.pmid and other.pmid and r.pmid != other.pmid:
                continue
            if r.author and other.author and r.author != other.author:
                continue
            if not ok(r, other):
                continue
            auto = (
                score >= TITLE_AUTO
                and r.year is not None
                and r.year == other.year
                and bool(r.author)
                and r.author == other.author
                and len(r.title) >= 30
            )
            edges.append((r.id, other.id, "title", score, auto))
    return edges


async def run_dedup(db: AsyncSession, project_id: uuid.UUID) -> dict:
    rows = (await db.execute(select(Record).where(Record.project_id == project_id))).scalars().all()
    groups = {
        g.id: g
        for g in (
            await db.execute(select(DuplicateGroup).where(DuplicateGroup.project_id == project_id))
        ).scalars()
    }
    # Grupos confirmados que perderam membros (ex.: busca apagada) são desfeitos ou ajustados
    group_members: dict = defaultdict(list)
    for r in rows:
        if r.duplicate_group_id:
            group_members[r.duplicate_group_id].append(r)
    for gid, g in list(groups.items()):
        if g.status != DuplicateStatus.confirmed:
            continue
        mem = group_members.get(gid, [])
        if len(mem) < 2:
            for r in mem:
                r.duplicate_group_id = None
            await db.delete(g)
            del groups[gid]
        elif g.primary_record_id not in {r.id for r in mem}:
            g.primary_record_id = max(mem, key=_completeness).id
    await db.flush()
    confirmed = {gid for gid, g in groups.items() if g.status == DuplicateStatus.confirmed}
    blocked = {
        frozenset((n.record_a_id, n.record_b_id))
        for n in (
            await db.execute(select(NotDuplicate).where(NotDuplicate.project_id == project_id))
        ).scalars()
    }

    recs = [
        _Rec(
            id=r.id,
            doi=r.doi,
            pmid=r.pmid,
            title=normalize_title(r.title or ""),
            year=r.year,
            author=first_author_key(r.authors or []),
            completeness=_completeness(r),
            group_id=r.duplicate_group_id if r.duplicate_group_id in confirmed else None,
        )
        for r in rows
    ]
    by_id = {r.id: r for r in recs}
    orm = {r.id: r for r in rows}

    uf = _UnionFind()
    # Grupos confirmados continuam juntos
    members: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for r in recs:
        if r.group_id:
            members[r.group_id].append(r.id)
    for ids in members.values():
        for other in ids[1:]:
            uf.union(ids[0], other)

    edges_found = find_edges(recs, blocked)
    for a, b, *_ in edges_found:
        uf.union(a, b)

    components: dict = defaultdict(list)
    for r in recs:
        components[uf.find(r.id)].append(r.id)
    edges_by_comp: dict = defaultdict(list)
    for e in edges_found:
        edges_by_comp[uf.find(e[0])].append(e)

    # Remove os grupos pendentes antigos; eles serão recalculados
    pending_ids = [gid for gid in groups if gid not in confirmed]
    if pending_ids:
        pending_set = set(pending_ids)
        for r in rows:
            if r.duplicate_group_id in pending_set:
                r.duplicate_group_id = None
        await db.execute(delete(DuplicateGroup).where(DuplicateGroup.id.in_(pending_ids)))

    stats = {"groups_auto": 0, "groups_pending": 0, "records": len(recs)}
    for root, ids in components.items():
        if len(ids) < 2:
            continue
        edges = edges_by_comp.get(root, [])
        existing = {by_id[i].group_id for i in ids if by_id[i].group_id}
        new_ids = [i for i in ids if by_id[i].group_id is None]
        all_auto = all(e[4] for e in edges)
        if existing:
            # Junta tudo no primeiro grupo confirmado; se algo novo não for automático, volta para revisão
            gid = sorted(existing, key=str)[0]
            group = groups[gid]
            for other_gid in existing - {gid}:
                for r in rows:
                    if r.duplicate_group_id == other_gid:
                        r.duplicate_group_id = gid
                await db.delete(groups[other_gid])
            if new_ids:
                for i in new_ids:
                    orm[i].duplicate_group_id = gid
                if not all_auto:
                    group.status = DuplicateStatus.pending
                    group.resolved_at = None
                    group.resolved_by_id = None
            continue
        method = (
            "doi"
            if any(e[2] == "doi" for e in edges)
            else ("pmid" if any(e[2] == "pmid" for e in edges) else "title")
        )
        primary = max(ids, key=lambda i: by_id[i].completeness)
        group = DuplicateGroup(
            project_id=project_id,
            status=DuplicateStatus.confirmed if all_auto else DuplicateStatus.pending,
            method=method,
            score=min((e[3] for e in edges), default=100),
            primary_record_id=primary,
        )
        db.add(group)
        await db.flush()
        for i in ids:
            orm[i].duplicate_group_id = group.id
        stats["groups_auto" if all_auto else "groups_pending"] += 1
    await db.commit()
    return stats
