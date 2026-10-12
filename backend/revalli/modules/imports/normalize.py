import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
YEAR_RE = re.compile(r"(1[5-9]\d\d|20\d\d|21\d\d)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACES_RE = re.compile(r"\s+")
# Caracteres de controle C1 (U+0080 a U+009F) são aspas e travessões do Windows-1252 que
# chegaram sem conversão (comum nas exportações da BVS): voltam ao caractere certo ou somem
_C1_TABLE = {cp: bytes([cp]).decode("cp1252", errors="ignore") or None for cp in range(0x80, 0xA0)}


@dataclass
class ParsedRecord:
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str | None = None
    pmid: str | None = None
    url: str = ""
    keywords: list[str] = field(default_factory=list)
    language: str = ""
    publication_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def clean(self) -> "ParsedRecord":
        self.title = clean_text(self.title).rstrip(".")
        self.abstract = clean_text(self.abstract)
        self.authors = [clean_text(a) for a in self.authors if clean_text(a)]
        self.journal = clean_text(self.journal)
        self.volume = clean_text(self.volume)[:50]
        self.issue = clean_text(self.issue)[:50]
        self.pages = clean_text(self.pages)[:50]
        if re.fullmatch(r"0+(\s*-\s*0+)?", self.pages):
            # Algumas bases preenchem páginas com zeros quando não sabem
            self.pages = ""
        self.doi = normalize_doi(self.doi) or normalize_doi(self.url)
        self.pmid = normalize_pmid(self.pmid)
        self.url = clean_text(self.url)[:2000]
        seen: set[str] = set()
        kws = []
        for k in self.keywords:
            k = clean_text(k)
            if k and k.lower() not in seen:
                seen.add(k.lower())
                kws.append(k)
        self.keywords = kws
        self.language = clean_text(self.language)[:50]
        self.publication_type = clean_text(self.publication_type)[:200]
        return self

    @property
    def is_empty(self) -> bool:
        return not (self.title or self.doi or self.pmid)


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = html.unescape(str(value))
    value = value.translate(_C1_TABLE)
    value = HTML_TAG_RE.sub(" ", value)
    value = unicodedata.normalize("NFC", value)
    return SPACES_RE.sub(" ", value).strip()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    match = DOI_RE.search(value)
    if not match:
        return None
    doi = match.group(0).lower().rstrip(".,;)]}")
    return doi[:255]


def normalize_pmid(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.search(r"\d{1,9}", str(value))
    return digits.group(0) if digits else None


def parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = YEAR_RE.search(str(value))
    return int(match.group(1)) if match else None


def split_keywords(value: str) -> list[str]:
    return [k.strip() for k in re.split(r"[;\n]|,(?=\s)", value) if k.strip()]


def normalize_title(title: str) -> str:
    """Forma canônica do título para comparação: sem acentos, minúsculo, só letras e números."""
    text = unicodedata.normalize("NFKD", title.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return SPACES_RE.sub(" ", text).strip()


def first_author_key(authors: list[str]) -> str:
    """Sobrenome do primeiro autor normalizado ('Silva, J.' ou 'J. Silva' -> 'silva')."""
    if not authors:
        return ""
    first = authors[0]
    last = first.split(",")[0] if "," in first else first.split(" ")[-1]
    return normalize_title(last).replace(" ", "")
