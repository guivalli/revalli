"""Nomes das bases de uma revisão: o PRISMA agrupa as buscas pelo nome, então dois arquivos com
o mesmo nome viram uma base só. Por isso o nome de uma importação nova é comparado com os que já
existem e a pessoa decide se é a mesma base ou outra."""

import re
import unicodedata

from rapidfuzz import fuzz

SIMILAR = 88


def normalize(name: str) -> str:
    """Sem acento, caixa nem pontuação: "BVS / Lilacs" e "bvs-lilacs" são o mesmo nome."""
    base = unicodedata.normalize("NFKD", name)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", base.lower()).strip()


def similar_source(name: str, existing: list[str]) -> str | None:
    """O nome já usado que é igual ou muito parecido com `name` (o mais parecido), se houver.
    Também vale quando um nome contém o outro por inteiro ("LILACS" e "BVS/Lilacs")."""
    wanted = normalize(name)
    if not wanted:
        return None
    best, best_score = None, 0.0
    for candidate in dict.fromkeys(existing):
        other = normalize(candidate)
        if not other:
            continue
        if other == wanted:
            return candidate
        score = max(fuzz.ratio(wanted, other), fuzz.token_set_ratio(wanted, other))
        if score >= SIMILAR and score > best_score:
            best, best_score = candidate, score
    return best


def same_name(a: str, b: str) -> bool:
    return normalize(a) == normalize(b)
