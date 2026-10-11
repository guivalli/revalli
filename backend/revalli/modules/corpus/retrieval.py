"""Recuperação dos trechos: busca de texto do Postgres e similaridade de embeddings,
combinadas por fusão de posições (RRF)."""

import re
import uuid

import numpy as np

CANDIDATES = 50
RRF_K = 60

STOPWORDS = frozenset(
    """a an and are as at be but by for from has have in into is it its of on or that the their
    this to was were what which who with does did how why when where
    o os as um uma uns umas de da do das dos e em no na nos nas por para com que qual quais
    como quando onde se ao aos foi são ser tem têm""".split()
)


def query_terms(question: str) -> list[str]:
    seen: dict[str, None] = {}
    for tok in re.findall(r"\w+", question.casefold()):
        if len(tok) > 1 and tok not in STOPWORDS and not tok.isdigit():
            seen[tok] = None
    return list(seen)


def tsquery(question: str) -> str:
    """Consulta OR de termos soltos (as palavras vêm só de \\w, então são seguras)."""
    return " | ".join(query_terms(question)[:40])


def rank_vectors(query: np.ndarray, ids: list[uuid.UUID], matrix: np.ndarray, top: int):
    """Ids em ordem decrescente de similaridade de cosseno."""
    if not ids:
        return []
    q = query / (np.linalg.norm(query) or 1.0)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    scores = (matrix / norms[:, None]) @ q
    order = np.argsort(-scores)[:top]
    return [ids[i] for i in order]


def fuse(rankings: list[list[uuid.UUID]]) -> list[uuid.UUID]:
    score: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for pos, cid in enumerate(ranking):
            score[cid] = score.get(cid, 0.0) + 1.0 / (RRF_K + pos + 1)
    return sorted(score, key=lambda c: -score[c])


def pick(
    ranked: list[uuid.UUID],
    record_of: dict[uuid.UUID, uuid.UUID],
    length_of: dict[uuid.UUID, int],
    top_k: int,
    per_record: int,
    max_chars: int,
) -> list[uuid.UUID]:
    """Escolhe os melhores sem deixar um único artigo dominar nem estourar o contexto."""
    chosen: list[uuid.UUID] = []
    per: dict[uuid.UUID, int] = {}
    size = 0
    for cid in ranked:
        rec = record_of[cid]
        if per.get(rec, 0) >= per_record or size + length_of[cid] > max_chars:
            continue
        chosen.append(cid)
        per[rec] = per.get(rec, 0) + 1
        size += length_of[cid]
        if len(chosen) >= top_k:
            break
    return chosen
