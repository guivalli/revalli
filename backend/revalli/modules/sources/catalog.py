"""Catálogo das bases que o ReValli conhece e os pacotes por área do conhecimento.

Cada projeto escolhe quais bases usa (`Project.settings["databases"]`). A escolha enxuga a
lista da busca direta, os alvos da tradução e o que o assistente de busca propõe. Quem nunca
escolheu fica com `DEFAULT_ENABLED`: as bases de antes do seletor mais as de busca direta novas,
para que todas apareçam na lista sem ninguém precisar marcar nada.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Database:
    id: str
    # Tem busca direta pela API; as demais entram por arquivo, com a estratégia traduzida
    direct: bool


DATABASES = (
    Database("pubmed", True),
    Database("europepmc", True),
    Database("openalex", True),
    Database("preprints", True),
    Database("clinicaltrials", True),
    Database("eric", True),
    Database("arxiv", True),
    Database("doaj", True),
    Database("openaire", True),
    Database("semanticscholar", True),
    Database("scielo", True),
    Database("pepsic", True),
    Database("scopus", False),
    Database("wos", False),
    Database("embase", False),
    Database("cinahl", False),
    Database("psycinfo", False),
    Database("cochrane", False),
    Database("bvs", False),
    Database("capes", False),
    Database("sportdiscus", False),
    Database("pedro", False),
    Database("econlit", False),
    Database("ieee", False),
    Database("acm", False),
)
IDS = tuple(d.id for d in DATABASES)

DEFAULT_ENABLED = (
    "pubmed",
    "openalex",
    "europepmc",
    "preprints",
    "clinicaltrials",
    "eric",
    "arxiv",
    "doaj",
    "openaire",
    "semanticscholar",
    "scopus",
    "wos",
    "embase",
    "cinahl",
    "psycinfo",
    "cochrane",
    "bvs",
    "scielo",
    "capes",
    "pepsic",
)

# Conjuntos típicos de cada área: um clique marca todos
PACKS: dict[str, tuple[str, ...]] = {
    "health": ("pubmed", "embase", "cochrane", "clinicaltrials", "scopus", "wos", "preprints"),
    "rehab": ("pubmed", "cinahl", "pedro", "sportdiscus", "cochrane", "bvs", "scielo"),
    "psychology": ("pubmed", "psycinfo", "pepsic", "eric", "scielo", "bvs", "preprints"),
    "education": ("eric", "scopus", "wos", "scielo", "capes", "openalex", "doaj"),
    "social": ("openalex", "scopus", "wos", "econlit", "scielo", "capes", "doaj", "openaire"),
    "computing": ("ieee", "acm", "scopus", "arxiv", "semanticscholar", "openalex"),
}


def enabled(settings: dict | None) -> list[str]:
    """As bases do projeto, na ordem do catálogo; as desconhecidas são ignoradas."""
    saved = ((settings or {}).get("databases") or {}).get("enabled")
    if not isinstance(saved, list):
        return list(DEFAULT_ENABLED)
    chosen = [d for d in IDS if d in saved]
    return chosen or list(DEFAULT_ENABLED)
