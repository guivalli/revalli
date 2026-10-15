"""Campos de busca de cada base e a compilação da estratégia para a sintaxe nativa.

A estratégia chega de duas formas: um texto livre ou linhas (operador, termo, campo), como na
busca avançada das bases. Cada base fala de um jeito:

- PubMed: sufixo de campo em cada termo (`termo[tiab]`); um grupo `(a OR b)[tiab]` NÃO aplica o
  campo ao grupo (a base o ignora em silêncio), então o campo é repetido em cada termo.
- Europe PMC: prefixo (`TITLE_ABS:termo`).
- OpenAlex, SciELO e PePSIC: filtros de campo (`title_and_abstract.search:...`). Filtros se
  combinam só com E; OU vale apenas dentro de um campo.
- ERIC (`title:termo`), arXiv (`ti:termo`, NOT vira ANDNOT) e ClinicalTrials.gov
  (`AREA[BriefTitle]termo`, expressões Essie): prefixo em cada termo. Quando o campo do ReValli
  cobre vários da base (título e resumo), o termo vira `(a:x OR b:x)`.
- Preprints: Europe PMC restrito a `SRC:PPR` (a sintaxe é a do Europe PMC).
- DOAJ: Lucene (`bibjson.title:termo`), sem curinga (a base recusa), NOT vira `AND NOT`.
- OpenAIRE: parâmetros (`mainTitle=`, `description=`, `authorFullName=`, `search=`) que se
  combinam só com E; dentro de um parâmetro valem AND/OR/NOT e frases; sem curinga.
- Semantic Scholar: consulta em `+` (E), `|` (OU) e `-` (NÃO); ano, tipo e revista são filtros.

Quando a estratégia usa algo que a base não entende (`ti:(...)` no OpenAlex, OU entre campos),
ela é corrigida e a correção volta em `corrections` como `código` ou `código: detalhe`, que a
interface traduz. Nada é recusado.
"""

import re
from dataclasses import dataclass, field

FIELDS = (
    "title_abstract",
    "title",
    "abstract",
    "fulltext",
    "author",
    "keyword",
    "mesh",
    "journal",
    "affiliation",
    "year",
    "language",
    "type",
    "condition",
    "intervention",
)
OPERATORS = ("AND", "OR", "NOT")
DEFAULT_FIELD = "title_abstract"

PUBMED = {
    "title_abstract": "tiab",
    "title": "ti",
    "author": "au",
    "mesh": "mh",
    "journal": "ta",
    "affiliation": "ad",
    "year": "dp",
    "language": "la",
    "type": "pt",
}
EUROPEPMC = {
    "title_abstract": "TITLE_ABS",
    "title": "TITLE",
    "abstract": "ABSTRACT",
    "author": "AUTH",
    "keyword": "KW",
    "journal": "JOURNAL",
    "affiliation": "AFF",
    "year": "PUB_YEAR",
    "language": "LANG",
    "type": "PUB_TYPE",
}
# Na busca direta, um campo pode virar vários da base (título e resumo): o valor é a tupla
ERIC = {
    "title_abstract": ("title", "description"),
    "title": "title",
    "abstract": "description",
    "author": "author",
    "keyword": "subject",
    "journal": "source",
    "year": "publicationdateyear",
    "language": "language",
    "type": "publicationtype",
}
ARXIV = {
    "title_abstract": ("ti", "abs"),
    "title": "ti",
    "abstract": "abs",
    "author": "au",
    "journal": "jr",
}
CLINICALTRIALS = {
    "title_abstract": ("BriefTitle", "OfficialTitle", "BriefSummary"),
    "title": ("BriefTitle", "OfficialTitle"),
    "abstract": "BriefSummary",
    "keyword": "Keyword",
    "condition": "Condition",
    "intervention": "InterventionName",
    "year": "StartDate",
    "type": "StudyType",
}
DOAJ = {
    "title_abstract": ("bibjson.title", "bibjson.abstract"),
    "title": "bibjson.title",
    "abstract": "bibjson.abstract",
    "author": "bibjson.author.name",
    "keyword": "bibjson.keywords",
    "journal": "bibjson.journal.title",
    "year": "bibjson.year",
    "language": "bibjson.journal.language",
}
# O OpenAIRE não tem um campo só de título e resumo: `search` varre todos os metadados
OPENAIRE = {
    "title_abstract": "search",
    "title": "mainTitle",
    "abstract": "description",
    "author": "authorFullName",
    "year": "publicationDate",
}
# O Semantic Scholar busca texto em título e resumo; o resto são filtros
SEMANTICSCHOLAR = {
    "title_abstract": "query",
    "year": "year",
    "type": "publicationTypes",
    "journal": "venue",
}
# Bases em que um curinga é erro (DOAJ) ou vira texto literal (OpenAIRE)
NO_WILDCARD = ("doaj", "openaire")
# Como a base escreve o campo antes do termo (o padrão é `CAMPO:termo`)
TAG_FORMAT = {"clinicaltrials": "AREA[{tag}]{value}"}
# O NOT de algumas bases tem outro nome
NOT_AS = {"arxiv": "ANDNOT", "clinicaltrials": "AND NOT", "doaj": "AND NOT"}
ERIC_LANGUAGES = {
    "pt": "Portuguese",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
}
OPENALEX_SEARCH = {
    "title_abstract": "title_and_abstract.search",
    "title": "title.search",
    "abstract": "abstract.search",
    "fulltext": "fulltext.search",
    "author": "raw_author_name.search",
    "affiliation": "raw_affiliation_strings.search",
}
OPENALEX_VALUE = {"year": "publication_year", "language": "language", "type": "type"}
OPENALEX = {**OPENALEX_SEARCH, **OPENALEX_VALUE}
OPENALEX_FAMILY = ("openalex", "scielo", "pepsic")
BY_SOURCE: dict[str, dict[str, str | tuple[str, ...]]] = {
    "pubmed": PUBMED,
    "europepmc": EUROPEPMC,
    "preprints": EUROPEPMC,
    "eric": ERIC,
    "arxiv": ARXIV,
    "clinicaltrials": CLINICALTRIALS,
    "doaj": DOAJ,
    "openaire": OPENAIRE,
    "semanticscholar": SEMANTICSCHOLAR,
    **{s: OPENALEX for s in OPENALEX_FAMILY},
}
# Título e resumo se unem num só filtro; é a única forma de OU entre campos que o OpenAlex tem
TITLE_ABSTRACT_GROUP = {"title", "abstract", "title_abstract"}

# Siglas que as pessoas escrevem no texto (de outras bases) e o campo a que correspondem
TEXT_TAGS = {
    "ti": "title",
    "title": "title",
    "ab": "abstract",
    "abstract": "abstract",
    "tiab": "title_abstract",
    "tw": "title_abstract",
    "title_abs": "title_abstract",
    "au": "author",
    "auth": "author",
    "author": "author",
    "kw": "keyword",
    "mh": "mesh",
    "mesh": "mesh",
    "ta": "journal",
    "journal": "journal",
    "ad": "affiliation",
    "aff": "affiliation",
    "dp": "year",
    "pub_year": "year",
    "la": "language",
    "lang": "language",
    "pt": "type",
    "pub_type": "type",
    # Siglas nativas do ERIC e do arXiv
    "description": "abstract",
    "abs": "abstract",
    "subject": "keyword",
    "source": "journal",
    "jr": "journal",
    "publicationdateyear": "year",
    "language": "language",
    "publicationtype": "type",
    "condition": "condition",
    "intervention": "intervention",
}
# Siglas que são da própria base: escrevê-las não é uma correção
NATIVE_TAGS = {
    "europepmc": set(EUROPEPMC.values()),
    "eric": {
        "title",
        "description",
        "author",
        "subject",
        "source",
        "publicationdateyear",
        "language",
        "publicationtype",
    },
    "arxiv": {"ti", "abs", "au", "jr"},
}
# Siglas que o PubMed põe depois do termo e o campo a que correspondem
PUBMED_SUFFIX = {
    "tiab": "title_abstract",
    "tw": "title_abstract",
    "ti": "title",
    "au": "author",
    "mh": "mesh",
    "ta": "journal",
    "ad": "affiliation",
    "dp": "year",
    "la": "language",
    "pt": "type",
}
# Códigos de idioma por base: PubMed e Europe PMC usam 3 letras, o OpenAlex 2
LANGUAGES = {"pt": "por", "en": "eng", "es": "spa", "fr": "fre", "de": "ger", "it": "ita"}
_LANG_ALIASES = {v: k for k, v in LANGUAGES.items()} | {k: k for k in LANGUAGES}

_YEAR = re.compile(r"^\s*(\d{4})\s*(?:[-–—:]|to|a|até)?\s*(\d{4})?\s*$", re.IGNORECASE)
_TOKEN = re.compile(r'\s*(?:(\()|(\))|("[^"]*"(?:\[[^\]]*\])?)|([^\s()"]+)|(")|(\S))')
_TAG_WORD = re.compile(r"^([A-Za-z_]+):(.*)$")
_QUOTED = re.compile(r'"[^"]*"')


@dataclass
class Row:
    term: str
    field: str = DEFAULT_FIELD
    op: str = "AND"


@dataclass
class Compiled:
    """A estratégia pronta para a base. `native` é o que fica salvo na busca; `filters` só é
    usado pelo OpenAlex, SciELO e PePSIC."""

    source: str
    native: str
    filters: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    # O texto como a base o recebeu, quando mudou em relação ao que a pessoa escreveu
    shown: str = ""


def available_fields(source: str) -> list[str]:
    spec = BY_SOURCE[source]
    return [f for f in FIELDS if f in spec]


# Bases em que cada campo é um filtro à parte: filtros se combinam só com E
FILTER_SOURCES = (*OPENALEX_FAMILY, "openaire", "semanticscholar")


def mixes_fields_with_or(source: str) -> bool:
    """Falso nas bases que só combinam campos diferentes com E."""
    return source not in FILTER_SOURCES


def adapt_query(query: str) -> str:
    """O OpenAlex recusa curingas dentro de frases entre aspas ("efeito* adverso*"). A frase
    vira as palavras ligadas por AND, o que é um pouco mais amplo mas é aceito."""

    def unquote(m: re.Match) -> str:
        phrase = m.group(0)[1:-1]
        if "*" not in phrase and "?" not in phrase:
            return m.group(0)
        words = phrase.split()
        return words[0] if len(words) == 1 else "(" + " AND ".join(words) + ")"

    return _QUOTED.sub(unquote, query)


def _rename(notes: list[str], old: str, new: str) -> list[str]:
    return [new + n[len(old) :] if n.startswith(old) else n for n in notes]


def _note(notes: list[str], code: str, detail: str = "") -> None:
    item = f"{code}: {detail}" if detail else code
    if item not in notes:
        notes.append(item)


# --- Leitura do texto --------------------------------------------------------------


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos, text = 0, text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        if m.group(1):
            tokens.append(("(", "("))
        elif m.group(2):
            tokens.append((")", ")"))
        elif m.group(3):
            tokens.append(("term", m.group(3)))
        elif m.group(4):
            tokens.append(("word", m.group(4)))
        # aspas soltas e símbolos isolados são ignorados
    return tokens


def _classify(
    source: str, tokens: list[tuple[str, str]], notes: list[str]
) -> list[tuple[str, str]]:
    """Separa operadores, siglas de campo (`ti:`, `[tiab]`) e termos, corrigindo o que a base
    não lê. Fora do PubMed, a sigla vira o campo nativo da base."""
    out: list[tuple[str, str]] = []
    found: list[str] = []

    def term(value: str) -> None:
        m = re.match(r"^(.*?)\[([A-Za-z/ ]+)\]$", value)
        if not m or source == "pubmed":
            out.append(("term", value))
            return
        core, name = m.group(1), m.group(2).lower()
        if name in PUBMED_SUFFIX and core:
            out.append(("tag", PUBMED_SUFFIX[name]))
            found.append(name)
            out.append(("term", core))
        else:
            _note(notes, "pubmed_tags_removed")
            if core:
                out.append(("term", core))

    for i, (kind, value) in enumerate(tokens):
        if kind == "term":
            term(value)
        elif kind != "word":
            out.append((kind, value))
        elif value in OPERATORS:
            out.append(("op", value))
        elif value.startswith("[") and value.endswith("]"):
            # Sigla depois de um grupo: o PubMed a ignora; nas outras bases não há onde aplicá-la
            if source == "pubmed":
                out.append(("suffix", value))
            else:
                _note(notes, "pubmed_tags_removed")
        elif (
            value.lower() in ("and", "or", "not")
            and 0 < i < len(tokens) - 1
            and out
            and out[-1][0] in ("term", ")")
            and tokens[i + 1][0] in ("term", "word", "(")
        ):
            out.append(("op", value.upper()))
            _note(notes, "operators_uppercased")
        else:
            m = _TAG_WORD.match(value)
            if m and m.group(1).lower() in TEXT_TAGS:
                out.append(("tag", TEXT_TAGS[m.group(1).lower()]))
                # A sigla da própria base (TITLE_ABS: no Europe PMC) não é uma correção
                if m.group(1) not in NATIVE_TAGS.get(source, ()):
                    found.append(m.group(1).lower())
                if m.group(2):
                    term(m.group(2))
            else:
                term(value)
    if found:
        _note(notes, "field_tags_found", ", ".join(dict.fromkeys(found)))
    return out


def _annotate(
    items: list[tuple[str, str]], default: str | None
) -> list[tuple[str, str, str | None]]:
    """Dá a cada termo o campo da sigla que o antecede (valendo para o grupo, se for um)."""
    out: list[tuple[str, str, str | None]] = []
    stack: list[str | None] = [default]
    pending: str | None = None
    for kind, value in items:
        if kind == "tag":
            pending = value
        elif kind == "(":
            stack.append(pending or stack[-1])
            pending = None
            out.append((kind, value, None))
        elif kind == ")":
            if len(stack) > 1:
                stack.pop()
            out.append((kind, value, None))
        elif kind == "term":
            out.append((kind, value, pending or stack[-1]))
            pending = None
        else:
            out.append((kind, value, None))
    return out


def _join(parts: list[tuple[str, str]]) -> str:
    text = ""
    for kind, value in parts:
        if not text or text.endswith("(") or kind in (")", "suffix"):
            text += value
        else:
            text += " " + value
    return text


def _no_commas(text: str) -> str:
    """O OpenAlex separa filtros por vírgula; fora de aspas ela vira espaço."""
    out, last = [], 0
    for m in _QUOTED.finditer(text):
        out.append(text[last : m.start()].replace(",", " "))
        out.append(m.group(0))
        last = m.end()
    out.append(text[last:].replace(",", " "))
    return re.sub(r"\s+", " ", "".join(out)).strip()


# --- PubMed e Europe PMC -----------------------------------------------------------


def _supported(source: str, fld: str | None, notes: list[str]) -> str | None:
    if fld is None or fld in BY_SOURCE[source]:
        return fld
    _note(notes, "field_unavailable", fld)
    return DEFAULT_FIELD


PHRASE_FIELDS = {"author", "journal", "affiliation"}


def _phrase(term: str, fld: str | None) -> str:
    """Nome de autor, revista e afiliação são uma frase: sem aspas, cada palavra viraria um
    termo solto."""
    if fld in PHRASE_FIELDS and not re.search(r'["()]|\b(?:AND|OR|NOT)\b', term) and " " in term:
        return f'"{term}"'
    return term


def _year_value(term: str) -> tuple[str, str] | None:
    m = _YEAR.match(term)
    if not m:
        return None
    return m.group(1), m.group(2) or ""


def _language(term: str, source: str) -> str:
    code = _LANG_ALIASES.get(term.strip().lower())
    if not code:
        return term.strip()
    if source == "eric":
        return ERIC_LANGUAGES[code]
    if source == "doaj":
        return code.upper()
    return code if source in OPENALEX_FAMILY else LANGUAGES[code]


def _tagged(source: str, tags: str | tuple[str, ...], value: str) -> str:
    """O termo com o campo da base; vários campos viram `(a:x OR b:x)`."""
    fmt = TAG_FORMAT.get(source, "{tag}:{value}")
    items = [fmt.format(tag=t, value=value) for t in ([tags] if isinstance(tags, str) else tags)]
    return items[0] if len(items) == 1 else "(" + " OR ".join(items) + ")"


def _year_text(source: str, start: str, end: str) -> str:
    if source == "pubmed":
        return f"{start}:{end}[dp]" if end else f"{start}[dp]"
    if source == "clinicaltrials":
        return f"AREA[StartDate]RANGE[{start}-01-01,{end or start}-12-31]"
    tag = {"eric": "publicationdateyear", "doaj": "bibjson.year"}.get(source, "PUB_YEAR")
    return f"{tag}:[{start} TO {end}]" if end else f"{tag}:{start}"


def _native_text(
    source: str, items: list[tuple[str, str, str | None]], notes: list[str]
) -> tuple[str, int]:
    """Renderiza os termos de uma linha; devolve o texto e quantos termos de topo tem."""
    spec = BY_SOURCE[source]
    parts: list[tuple[str, str]] = []
    for kind, value, fld in items:
        if kind != "term":
            if kind == "op" and value == "NOT":
                value = NOT_AS.get(source, value)
            parts.append((kind, value))
            continue
        fld = _supported(source, fld, notes)
        if fld is None or (source == "pubmed" and value.endswith("]")):
            if fld is None and source == "arxiv" and ":" not in value:
                value = f"all:{value}"
            parts.append(("term", value))
        elif source == "pubmed":
            parts.append(("term", f"{value}[{spec[fld]}]"))
        else:
            parts.append(("term", _tagged(source, spec[fld], value)))
    top = sum(1 for k, _ in parts if k in ("term", "op"))
    return _join(parts), top


def _row_native(source: str, row: Row, notes: list[str]) -> tuple[str, bool]:
    fld = _supported(source, row.field if row.field in FIELDS else DEFAULT_FIELD, notes)
    term = row.term.strip()
    if source in NO_WILDCARD:
        term = _no_wildcards(term, notes)
    if fld == "year":
        year = _year_value(term)
        if year is None:
            _note(notes, "year_invalid", term)
            return "", False
        return _year_text(source, *year), False
    if fld == "language":
        term = _language(term, source)
    term = _phrase(term, fld)
    items = _annotate(_classify(source, _tokenize(term), notes), fld)
    text, top = _native_text(source, items, notes)
    return text, top > 1


def _compile_rows_native(source: str, rows: list[Row], notes: list[str]) -> str:
    result, last_op = "", ""
    for row in rows:
        text, compound = _row_native(source, row, notes)
        if not text:
            continue
        if compound:
            text = f"({text})"
        if not result:
            result = text
            continue
        op = row.op if row.op in OPERATORS else "AND"
        # Da esquerda para a direita; o mesmo operador em sequência não precisa de parênteses
        if last_op and op != last_op:
            result = f"({result})"
        result = f"{result} {NOT_AS.get(source, op) if op == 'NOT' else op} {text}"
        last_op = op
    return result


def _no_wildcards(text: str, notes: list[str]) -> str:
    """O DOAJ recusa curingas e o OpenAIRE os trata como letra: saem, com aviso."""
    if "*" not in text and "?" not in text:
        return text
    _note(notes, "truncation_removed")
    return re.sub(r"[*?]", "", text)


# --- OpenAIRE ----------------------------------------------------------------------


def _param_text(source: str, term: str, notes: list[str]) -> str:
    """Texto de um parâmetro de busca: sem siglas de campo, sem curinga."""
    items = _annotate(_classify(source, _tokenize(term), notes), None)
    return _no_wildcards(_join([(k, v) for k, v, _ in items]), notes)


def _compile_rows_openaire(rows: list[Row], notes: list[str]) -> list[str]:
    """Um parâmetro por campo; linhas do mesmo campo se juntam com o operador da linha."""
    values: dict[str, str] = {}
    years: tuple[str, str] | None = None
    for row in rows:
        fld = row.field if row.field in FIELDS else DEFAULT_FIELD
        if fld not in OPENAIRE:
            _note(notes, "field_unavailable", fld)
            fld = DEFAULT_FIELD
        if fld == "year":
            years = _year_value(row.term.strip())
            if years is None:
                _note(notes, "year_invalid", row.term.strip())
            continue
        key = OPENAIRE[fld]
        text = _param_text("openaire", _phrase(row.term.strip(), fld), notes)
        if not text:
            continue
        op = row.op if row.op in OPERATORS else "AND"
        if key not in values:
            if op == "NOT":
                _note(notes, "not_across_fields", fld)
                continue
            if op == "OR" and values:
                _note(notes, "or_across_fields", fld)
            values[key] = text
        else:
            values[key] = f"({values[key]}) {op} ({text})"
    # Vários termos num parâmetro vão entre parênteses: o `OR` não vaza para o parâmetro seguinte
    out = [
        f"{k}=({v})"
        if re.search(r"\b(?:AND|OR|NOT)\b", v) and not v.startswith("(")
        else f"{k}={v}"
        for k, v in values.items()
    ]
    if years:
        out.append(f"fromPublicationDate={years[0]}-01-01")
        out.append(f"toPublicationDate={years[1] or years[0]}-12-31")
    return out


# --- Semantic Scholar --------------------------------------------------------------


def _s2_syntax(text: str) -> str:
    """AND, OR e NOT viram `+`, `|` e `-`; o que está entre aspas fica como está."""
    pieces, quoted = _QUOTED.split(text), _QUOTED.findall(text)
    out: list[str] = []
    for i, seg in enumerate(pieces):
        seg = re.sub(r"\s*\bAND\s+NOT\s+", " -", seg)
        seg = re.sub(r"\s*\bNOT\s+", " -", seg)
        seg = re.sub(r"\s*\bAND\s+", " + ", seg)
        seg = re.sub(r"\s*\bOR\s+", " | ", seg)
        out.append(seg)
        if i < len(quoted):
            out.append(quoted[i])
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _compile_semanticscholar(query: str, rows: list[Row] | None, notes: list[str]) -> Compiled:
    text, filters = "", []
    used = [r for r in rows or [] if r.term.strip()]
    if not used:
        items = _annotate(_classify("semanticscholar", _tokenize(query), notes), None)
        text = _s2_syntax(_join([(k, v) for k, v, _ in items]))
    for row in used:
        fld = row.field if row.field in FIELDS else DEFAULT_FIELD
        if fld not in SEMANTICSCHOLAR:
            _note(notes, "field_unavailable", fld)
            fld = DEFAULT_FIELD
        term = row.term.strip()
        if fld == "year":
            year = _year_value(term)
            if year is None:
                _note(notes, "year_invalid", term)
            else:
                filters.append(f"year={year[0]}-{year[1]}" if year[1] else f"year={year[0]}")
        elif fld != DEFAULT_FIELD:
            filters.append(f"{SEMANTICSCHOLAR[fld]}={term}")
        else:
            items = _annotate(
                _classify("semanticscholar", _tokenize(_phrase(term, fld)), notes), None
            )
            part = _s2_syntax(_join([(k, v) for k, v, _ in items]))
            if not part:
                continue
            if " " in part and not part.startswith("("):
                part = f"({part})"
            if text:
                op = row.op if row.op in OPERATORS else "AND"
                glue = {"AND": " + ", "OR": " | ", "NOT": " -"}[op]
                text = f"{text}{glue}{part}"
            else:
                text = part
    notes[:] = _rename(notes, "field_tags_found", "field_tags_removed")
    native = " AND ".join([f"query={text}", *filters]) if filters else text
    return Compiled("semanticscholar", native, [f"query={text}", *filters], notes, native)


# --- OpenAlex, SciELO e PePSIC -----------------------------------------------------


def _oa_text(term: str, notes: list[str]) -> tuple[str, bool, bool]:
    """Texto de um filtro de busca: sem siglas de campo, sem vírgula solta, com as frases com
    curinga reescritas. Devolve também se há curinga e se é composto (precisa de parênteses)."""
    items = _annotate(_classify("openalex", _tokenize(term), notes), None)
    text = _no_commas(adapt_query(_join([(k, v) for k, v, _ in items])))
    wildcard = "*" in text or "?" in text
    compound = len([1 for k, _, _ in items if k in ("term", "op")]) > 1
    return text, wildcard, compound


@dataclass
class _Group:
    field: str
    text: str
    wildcard: bool = False
    compound: bool = False
    negated: bool = False


def _oa_filter(g: _Group) -> str:
    if g.field in OPENALEX_VALUE:
        return f"{OPENALEX_VALUE[g.field]}:{'!' if g.negated else ''}{g.text}"
    name = OPENALEX_SEARCH[g.field] + (".exact" if g.wildcard else "")
    value = f"({g.text})" if g.compound or g.negated else g.text
    return f"{name}:{'!' if g.negated else ''}{value}"


def _oa_group(row: Row, notes: list[str]) -> _Group | None:
    fld = row.field if row.field in FIELDS else DEFAULT_FIELD
    if fld not in OPENALEX:
        _note(notes, "field_unavailable", fld)
        fld = DEFAULT_FIELD
    term = row.term.strip()
    if fld == "year":
        year = _year_value(term)
        if year is None:
            _note(notes, "year_invalid", term)
            return None
        return _Group(fld, f"{year[0]}-{year[1]}" if year[1] else year[0])
    if fld in OPENALEX_VALUE:
        value = _language(term, "openalex") if fld == "language" else term
        return _Group(fld, _no_commas(value.lower()))
    text, wildcard, compound = _oa_text(_phrase(term, fld), notes)
    return _Group(fld, text, wildcard, compound) if text else None


def _compile_rows_oa(rows: list[Row], notes: list[str]) -> list[str]:
    groups: list[_Group] = []
    for row in rows:
        group = _oa_group(row, notes)
        if group is None:
            continue
        op = row.op if row.op in OPERATORS and groups else "AND"
        if op == "NOT":
            group.negated = True
        elif op == "OR":
            prev = groups[-1]
            same = prev.field == group.field
            if not prev.negated and same and group.field in OPENALEX_VALUE:
                prev.text = f"{prev.text}|{group.text}"
                continue
            if (
                not prev.negated
                and prev.field in TITLE_ABSTRACT_GROUP
                and group.field in TITLE_ABSTRACT_GROUP
            ):
                if not same:
                    _note(notes, "or_merged_title_abstract")
                    prev.field = DEFAULT_FIELD
                prev.text = f"({prev.text}) OR ({group.text})"
                prev.wildcard = prev.wildcard or group.wildcard
                prev.compound = True
                continue
            _note(notes, "or_across_fields", f"{prev.field}, {group.field}")
        groups.append(group)
    return [_oa_filter(g) for g in groups]


# --- Entrada -----------------------------------------------------------------------


def compile_strategy(source: str, query: str = "", rows: list[Row] | None = None) -> Compiled:
    """Compila o texto (ou as linhas) para a base. As linhas valem mais que o texto."""
    if source == "preprints":
        # Os preprints são o Europe PMC restrito à fonte PPR
        inner = compile_strategy("europepmc", query, rows)
        if not inner.native.strip():
            return Compiled(source, "", [], inner.corrections)
        shown = f"({inner.shown}) AND SRC:PPR" if inner.shown else ""
        return Compiled(source, f"({inner.native}) AND SRC:PPR", [], inner.corrections, shown)
    notes: list[str] = []
    if source == "semanticscholar":
        return _compile_semanticscholar(query, rows, notes)
    used = [r for r in rows or [] if r.term.strip()]
    if source == "openaire":
        if not used:
            text = _param_text("openaire", query.strip(), notes)
            notes = _rename(notes, "field_tags_found", "field_tags_removed")
            return Compiled(source, f"search={text}", [f"search={text}"], notes, f"search={text}")
        filters = _compile_rows_openaire(used, notes)
        notes = _rename(notes, "field_tags_found", "field_tags_removed")
        native = " AND ".join(filters)
        return Compiled(source, native, filters, notes, native)
    if used:
        if source in OPENALEX_FAMILY:
            filters = _compile_rows_oa(used, notes)
            native = " AND ".join(filters)
            notes = _rename(notes, "field_tags_found", "field_tags_removed")
            return Compiled(source, native, filters, notes, native)
        native = _compile_rows_native(source, used, notes)
        notes = _rename(notes, "field_tags_found", "field_tags_converted")
        return Compiled(source, native, [], notes, native)

    query = query.strip()
    if source in NO_WILDCARD:
        query = _no_wildcards(query, notes)
    if source in OPENALEX_FAMILY:
        text, wildcard, compound = _oa_text(query, notes)
        name = OPENALEX_SEARCH[DEFAULT_FIELD] + (".exact" if wildcard else "")
        flt = f"{name}:({text})" if compound else f"{name}:{text}"
        notes = _rename(notes, "field_tags_found", "field_tags_removed")
        return Compiled(source, flt, [flt], notes, text if text != query else "")

    if source == "clinicaltrials" and "AREA[" in query:
        # Expressão Essie escrita à mão: vai como está
        return Compiled(source, query)
    items = _annotate(_classify(source, _tokenize(query), notes), None)
    if not notes and source not in NOT_AS:
        # Sem nada a corrigir, a base recebe exatamente o que foi escrito
        return Compiled(source, query)
    text, _ = _native_text(source, items, notes)
    notes = _rename(notes, "field_tags_found", "field_tags_converted")
    return Compiled(source, text, [], notes, text)
