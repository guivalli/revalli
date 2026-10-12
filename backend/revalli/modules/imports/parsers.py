"""Leitores dos formatos de exportação das bases bibliográficas.

Cada leitor recebe o texto já decodificado e devolve uma lista de ParsedRecord.
"""

import csv
import io
import json
import re
from collections.abc import Callable

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from defusedxml import ElementTree

from revalli.modules.imports.normalize import ParsedRecord, parse_year, split_keywords


class ImportFormatError(ValueError):
    pass


# --- RIS ---------------------------------------------------------------------

RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  -(?: (.*))?$")


def _ris_entries(text: str) -> list[dict[str, list[str]]]:
    entries: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] | None = None
    last_tag = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m = RIS_LINE.match(line)
        if m:
            tag, value = m.group(1), (m.group(2) or "").strip()
            if tag == "TY":
                current = {}
                entries.append(current)
            if current is None:
                continue
            if tag == "ER":
                current = None
                last_tag = None
                continue
            current.setdefault(tag, []).append(value)
            last_tag = tag
        elif current is not None and last_tag and line.strip():
            # Linha de continuação do campo anterior
            current[last_tag][-1] += " " + line.strip()
    return entries


def _first(entry: dict[str, list[str]], *tags: str) -> str:
    for tag in tags:
        for value in entry.get(tag, []):
            if value:
                return value
    return ""


def parse_ris(text: str) -> list[ParsedRecord]:
    records = []
    for e in _ris_entries(text):
        start, end = _first(e, "SP"), _first(e, "EP")
        keywords = []
        for kw in e.get("KW", []):
            keywords.extend(split_keywords(kw) if ";" in kw else [kw])
        if not keywords:
            # Descritores (DeCS/MeSH) das exportações da BVS
            for mh in e.get("MH", []):
                keywords.extend(split_keywords(mh) if ";" in mh else [mh])
        # A BVS marca resumos de autor com "(AU)" no fim
        abstracts = [re.sub(r"\s*\(AU\)\s*$", "", ab) for ab in e.get("AB", []) or e.get("N2", [])]
        pmid = ""
        for value in e.get("AN", []) + e.get("C2", []) + e.get("M2", []):
            if re.fullmatch(r"\s*(PMID:?\s*)?\d{5,9}\s*", value, re.IGNORECASE):
                pmid = value
                break
        records.append(
            ParsedRecord(
                title=_first(e, "TI", "T1", "CT", "BT"),
                abstract=" ".join(abstracts),
                authors=e.get("AU", []) or e.get("A1", []),
                year=parse_year(_first(e, "PY", "Y1", "DA")),
                journal=_first(e, "JF", "T2", "JO", "JA", "J2"),
                volume=_first(e, "VL"),
                issue=_first(e, "IS"),
                pages=f"{start}-{end}" if start and end else start,
                doi=_first(e, "DO", "DI"),
                pmid=pmid,
                url=_first(e, "UR", "L2"),
                keywords=keywords,
                language=_first(e, "LA"),
                publication_type=_first(e, "TY", "M3"),
                raw={k: v if len(v) > 1 else v[0] for k, v in e.items()},
            )
        )
    return records


# --- PubMed (MEDLINE/.nbib) ----------------------------------------------------

MEDLINE_LINE = re.compile(r"^([A-Z]{2,4})\s*- (.*)$")


def parse_medline(text: str) -> list[ParsedRecord]:
    entries: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] | None = None
    last_tag = None
    for line in text.splitlines():
        m = MEDLINE_LINE.match(line)
        if m:
            tag, value = m.group(1), m.group(2).strip()
            if tag == "PMID" or current is None:
                current = {}
                entries.append(current)
            current.setdefault(tag, []).append(value)
            last_tag = tag
        elif line.startswith("      ") and current is not None and last_tag:
            current[last_tag][-1] += " " + line.strip()
    records = []
    for e in entries:
        doi = ""
        for value in e.get("LID", []) + e.get("AID", []):
            if value.endswith("[doi]"):
                doi = value
                break
        records.append(
            ParsedRecord(
                title=_first(e, "TI", "BTI"),
                abstract=" ".join(e.get("AB", [])),
                authors=e.get("FAU", []) or e.get("AU", []),
                year=parse_year(_first(e, "DP", "DEP")),
                journal=_first(e, "JT", "TA"),
                volume=_first(e, "VI"),
                issue=_first(e, "IP"),
                pages=_first(e, "PG"),
                doi=doi,
                pmid=_first(e, "PMID"),
                keywords=e.get("OT", []) + [m.split("/")[0].lstrip("*") for m in e.get("MH", [])],
                language=_first(e, "LA"),
                publication_type="; ".join(e.get("PT", [])),
                raw={k: v if len(v) > 1 else v[0] for k, v in e.items()},
            )
        )
    return records


# --- PubMed XML ------------------------------------------------------------------


def _text(el) -> str:
    return "".join(el.itertext()) if el is not None else ""


def parse_pubmed_xml(text: str) -> list[ParsedRecord]:
    try:
        root = ElementTree.fromstring(text.encode("utf-8"))
    except Exception as exc:  # defusedxml levanta vários tipos
        raise ImportFormatError("invalid_xml") from exc
    records = []
    for art in root.iter("PubmedArticle"):
        mc = art.find("MedlineCitation")
        article = mc.find("Article") if mc is not None else None
        if article is None:
            continue
        abstract_parts = []
        for ab in article.findall("Abstract/AbstractText"):
            label = ab.get("Label")
            body = _text(ab).strip()
            abstract_parts.append(f"{label}: {body}" if label else body)
        authors = []
        for au in article.findall("AuthorList/Author"):
            if au.find("CollectiveName") is not None:
                authors.append(_text(au.find("CollectiveName")))
            else:
                last, fore = _text(au.find("LastName")), _text(au.find("ForeName"))
                authors.append(f"{last}, {fore}" if fore else last)
        pubdate = article.find("Journal/JournalIssue/PubDate")
        year = (
            parse_year(_text(pubdate.find("Year")) or _text(pubdate.find("MedlineDate")))
            if pubdate is not None
            else None
        )
        doi = ""
        for eid in article.findall("ELocationID"):
            if eid.get("EIdType") == "doi":
                doi = _text(eid)
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi" and not doi:
                doi = _text(aid)
        keywords = [_text(k) for k in mc.findall("KeywordList/Keyword")]
        keywords += [
            _text(m.find("DescriptorName")) for m in mc.findall("MeshHeadingList/MeshHeading")
        ]
        records.append(
            ParsedRecord(
                title=_text(article.find("ArticleTitle")),
                abstract=" ".join(abstract_parts),
                authors=authors,
                year=year,
                journal=_text(article.find("Journal/Title")),
                volume=_text(article.find("Journal/JournalIssue/Volume")),
                issue=_text(article.find("Journal/JournalIssue/Issue")),
                pages=_text(article.find("Pagination/MedlinePgn")),
                doi=doi,
                pmid=_text(mc.find("PMID")),
                keywords=keywords,
                language=_text(article.find("Language")),
                publication_type="; ".join(
                    _text(p) for p in article.findall("PublicationTypeList/PublicationType")
                ),
                raw={"pmid": _text(mc.find("PMID"))},
            )
        )
    return records


# --- BibTeX ----------------------------------------------------------------------


def parse_bibtex(text: str) -> list[ParsedRecord]:
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    parser.customization = convert_to_unicode
    db = bibtexparser.loads(text, parser=parser)
    records = []
    for e in db.entries:

        def clean(key: str, entry=e) -> str:
            return entry.get(key, "").replace("{", "").replace("}", "").strip()

        authors = [a.strip() for a in re.split(r"\s+and\s+", clean("author")) if a.strip()]
        records.append(
            ParsedRecord(
                title=clean("title"),
                abstract=clean("abstract"),
                authors=authors,
                year=parse_year(clean("year")),
                journal=clean("journal") or clean("booktitle"),
                volume=clean("volume"),
                issue=clean("number"),
                pages=clean("pages").replace("--", "-"),
                doi=clean("doi"),
                pmid=clean("pmid"),
                url=clean("url"),
                keywords=split_keywords(clean("keywords")) if clean("keywords") else [],
                language=clean("language"),
                publication_type=e.get("ENTRYTYPE", ""),
                raw=dict(e),
            )
        )
    return records


# --- CSL JSON ----------------------------------------------------------------------


def _csl_year(item: dict) -> int | None:
    parts = (item.get("issued") or item.get("published") or {}).get("date-parts") or [[]]
    first = parts[0][0] if parts and parts[0] else None
    if first is None:
        raw = (item.get("issued") or {}).get("raw") or ""
        return parse_year(str(raw))
    return parse_year(str(first))


def _csl_name(a: dict) -> str:
    if a.get("literal"):
        return str(a["literal"])
    family, given = str(a.get("family") or ""), str(a.get("given") or "")
    return f"{family}, {given}" if family and given else family or given


def parse_csl_json(text: str) -> list[ParsedRecord]:
    """CSL JSON, o formato de intercâmbio que gerenciadores de referências costumam exportar."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ImportFormatError("unknown_format") from exc
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ImportFormatError("unknown_format")
    records = []
    for it in items:
        if not isinstance(it, dict):
            continue
        keywords = it.get("keyword") or it.get("keywords") or ""
        if isinstance(keywords, list):
            keywords = ", ".join(str(k) for k in keywords)
        records.append(
            ParsedRecord(
                title=str(it.get("title") or ""),
                abstract=str(it.get("abstract") or ""),
                authors=[_csl_name(a) for a in it.get("author") or [] if isinstance(a, dict)],
                year=_csl_year(it),
                journal=str(it.get("container-title") or ""),
                volume=str(it.get("volume") or ""),
                issue=str(it.get("issue") or ""),
                pages=str(it.get("page") or "").replace("\u2013", "-"),
                doi=str(it.get("DOI") or ""),
                pmid=str(it.get("PMID") or ""),
                url=str(it.get("URL") or ""),
                keywords=split_keywords(str(keywords)) if keywords else [],
                language=str(it.get("language") or ""),
                publication_type=str(it.get("type") or ""),
                raw={"csl_id": str(it.get("id") or "")},
            )
        )
    return records


# --- Web of Science (texto simples) ------------------------------------------------

WOS_LINE = re.compile(r"^([A-Z][A-Z0-9]) (.*)$")


def parse_wos(text: str) -> list[ParsedRecord]:
    entries: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] | None = None
    last_tag = None
    for line in text.splitlines():
        if line.startswith("ER"):
            current, last_tag = None, None
            continue
        m = WOS_LINE.match(line)
        if m and m.group(1) not in ("FN", "VR", "EF"):
            tag, value = m.group(1), m.group(2).strip()
            if tag == "PT" or current is None:
                current = {}
                entries.append(current)
            current.setdefault(tag, []).append(value)
            last_tag = tag
        elif line.startswith("   ") and current is not None and last_tag:
            # AU e AF trazem um autor por linha; nos demais é continuação de texto
            if last_tag in ("AU", "AF", "DE", "ID", "C1"):
                current[last_tag].append(line.strip())
            else:
                current[last_tag][-1] += " " + line.strip()
    records = []
    for e in entries:
        start, end = _first(e, "BP"), _first(e, "EP")
        records.append(
            ParsedRecord(
                title=_first(e, "TI"),
                abstract=_first(e, "AB"),
                authors=e.get("AF", []) or e.get("AU", []),
                year=parse_year(_first(e, "PY", "EA")),
                journal=_first(e, "SO"),
                volume=_first(e, "VL"),
                issue=_first(e, "IS"),
                pages=f"{start}-{end}" if start and end else start,
                doi=_first(e, "DI"),
                pmid=_first(e, "PM"),
                keywords=split_keywords("; ".join(e.get("DE", []))),
                language=_first(e, "LA"),
                publication_type=_first(e, "DT"),
                raw={k: v if len(v) > 1 else v[0] for k, v in e.items()},
            )
        )
    return records


# --- CSV / TSV ---------------------------------------------------------------------

CSV_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "titulo", "título", "article title", "document title", "ti"),
    "abstract": ("abstract", "resumo", "ab", "abstract note"),
    "authors": ("authors", "author", "autores", "autor", "author full names", "au", "af"),
    "year": ("year", "publication year", "ano", "py", "pubyear", "date", "publication date"),
    "journal": (
        "journal",
        "source title",
        "source",
        "revista",
        "periódico",
        "so",
        "journal/book",
        "publication title",
    ),
    "volume": ("volume", "vl"),
    "issue": ("issue", "number", "número", "is"),
    "pages": ("pages", "páginas", "page", "pg"),
    "doi": ("doi", "di"),
    "pmid": ("pmid", "pubmed id", "pm"),
    "url": ("url", "link"),
    "keywords": ("keywords", "author keywords", "palavras-chave", "de", "manual tags"),
    "language": ("language", "language of original document", "idioma", "la"),
    "publication_type": ("document type", "type", "publication type", "item type", "dt", "pt"),
}


def parse_csv(text: str) -> list[ParsedRecord]:
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel_tab if sample.count("\t") > sample.count(",") else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ImportFormatError("csv_without_header")
    by_lower = {f.strip().lower(): f for f in reader.fieldnames if f}
    mapping: dict[str, str] = {}
    for target, aliases in CSV_ALIASES.items():
        for alias in aliases:
            if alias in by_lower:
                mapping[target] = by_lower[alias]
                break
    if "title" not in mapping:
        raise ImportFormatError("csv_without_title_column")

    def get(row: dict, key: str) -> str:
        col = mapping.get(key)
        return (row.get(col) or "") if col else ""

    records = []
    for row in reader:
        authors_raw = get(row, "authors")
        sep = ";" if ";" in authors_raw else (" and " if " and " in authors_raw else ",")
        authors = (
            [a.strip() for a in authors_raw.split(sep) if a.strip()]
            if sep != ","
            else ([authors_raw.strip()] if authors_raw.strip() else [])
        )
        records.append(
            ParsedRecord(
                title=get(row, "title"),
                abstract=get(row, "abstract"),
                authors=authors,
                year=parse_year(get(row, "year")),
                journal=get(row, "journal"),
                volume=get(row, "volume"),
                issue=get(row, "issue"),
                pages=get(row, "pages"),
                doi=get(row, "doi"),
                pmid=get(row, "pmid"),
                url=get(row, "url"),
                keywords=split_keywords(get(row, "keywords")),
                language=get(row, "language"),
                publication_type=get(row, "publication_type"),
                raw={k: v for k, v in row.items() if k and v},
            )
        )
    return records


# --- Detecção ------------------------------------------------------------------------

FORMATS: dict[str, Callable[[str], list[ParsedRecord]]] = {
    "ris": parse_ris,
    "medline": parse_medline,
    "pubmed_xml": parse_pubmed_xml,
    "bibtex": parse_bibtex,
    "wos": parse_wos,
    "csv": parse_csv,
    "csl": parse_csl_json,
}


def detect_format(filename: str, text: str) -> str:
    head = text.lstrip("﻿ \r\n\t")[:5000]
    name = filename.lower()
    if re.search(r"^TY  -", head, re.MULTILINE):
        return "ris"
    if re.match(r"PMID\s*- ", head):
        return "medline"
    if head.startswith("<") and ("PubmedArticle" in head or name.endswith(".xml")):
        return "pubmed_xml"
    if re.match(r"(FN |PT [A-Z])", head):
        return "wos"
    if re.search(r"^\s*@\w+\s*[{(]", head, re.MULTILINE):
        return "bibtex"
    if head[:1] in ("[", "{") and (name.endswith(".json") or '"title"' in head):
        return "csl"
    if name.endswith((".csv", ".tsv", ".txt")) and ("," in head or "\t" in head or ";" in head):
        return "csv"
    raise ImportFormatError("unknown_format")


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            text = data.decode(encoding)
            if encoding == "utf-16" and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
                continue
            return text
        except UnicodeDecodeError:
            continue
    # Exportações antigas (ex.: bases regionais) costumam vir em Latin-1/Windows-1252
    return data.decode("cp1252", errors="replace")


def parse_file(
    filename: str, data: bytes, fmt: str | None = None
) -> tuple[str, list[ParsedRecord]]:
    text = decode_bytes(data).replace("\r\n", "\n").replace("\r", "\n")
    fmt = fmt or detect_format(filename, text)
    if fmt not in FORMATS:
        raise ImportFormatError("unknown_format")
    records = [r.clean() for r in FORMATS[fmt](text)]
    return fmt, [r for r in records if not r.is_empty]
