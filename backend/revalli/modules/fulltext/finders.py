"""Onde procurar a versão aberta de um artigo, além do OpenAlex.

Cada função devolve endereços candidatos (de PDF ou de página); quem baixa confere que o
arquivo é mesmo um PDF. Nenhuma contorna bloqueio: se a base recusar, o registro segue para
a lista de pendentes.
"""

import html.parser
import re
from urllib.parse import quote, urljoin, urlsplit

import httpx

from revalli.core import safefetch
from revalli.core.config import get_settings

PAGE_MAX_BYTES = 2 * 1024 * 1024
PAGE_TIMEOUT = 20
_OPEN = {"free", "open access", "open"}


def _unique(urls: list[str]) -> list[str]:
    seen: list[str] = []
    for u in urls:
        if u and u.startswith(("http://", "https://")) and u not in seen:
            seen.append(u)
    return seen


async def unpaywall(client: httpx.AsyncClient, doi: str) -> tuple[list[str], list[str]]:
    """PDFs e páginas das cópias abertas que o Unpaywall conhece. Exige o e-mail de contato."""
    s = get_settings()
    if not s.enrichment_contact_email:
        raise PermissionError("contact_email_missing")
    r = await client.get(
        f"{s.unpaywall_url.rstrip('/')}/{quote(doi, safe='/')}",
        params={"email": s.enrichment_contact_email},
    )
    if r.status_code in (404, 422):
        return [], []
    r.raise_for_status()
    data = r.json()
    pdfs, pages = [], []
    for loc in [data.get("best_oa_location") or {}, *(data.get("oa_locations") or [])]:
        pdfs.append(loc.get("url_for_pdf") or "")
        pages.append(loc.get("url_for_landing_page") or loc.get("url") or "")
    return _unique(pdfs), _unique(pages)


async def europepmc(
    client: httpx.AsyncClient, doi: str | None, pmid: str | None
) -> tuple[list[str], list[str]]:
    """PDFs de acesso aberto indexados pelo Europe PMC (PubMed Central e preprints)."""
    base = get_settings().europepmc_url.rstrip("/")
    query = f"EXT_ID:{pmid} AND SRC:MED" if pmid else f'DOI:"{doi}"'
    r = await client.get(
        f"{base}/search",
        params={"query": query, "resultType": "core", "format": "json", "pageSize": 1},
    )
    r.raise_for_status()
    results = (r.json().get("resultList") or {}).get("result") or []
    if not results:
        return [], []
    work = results[0]
    pdfs, pages = [], []
    for item in (work.get("fullTextUrlList") or {}).get("fullTextUrl") or []:
        if str(item.get("availability", "")).lower() not in _OPEN:
            continue
        style = str(item.get("documentStyle", "")).lower()
        (pdfs if style == "pdf" else pages).append(item.get("url") or "")
    pmcid = work.get("pmcid")
    if pmcid and work.get("isOpenAccess") == "Y":
        pdfs.append(f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf")
    return _unique(pdfs), _unique(pages)


class _PdfLinks(html.parser.HTMLParser):
    """Lê as marcas que as revistas (SciELO, PePSIC, OJS e a maioria das editoras) publicam
    para os indexadores: `citation_pdf_url` e `<link rel="alternate" type="application/pdf">`."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("name", "").lower() == "citation_pdf_url":
            self.urls.append(a.get("content", "").strip())
        elif (
            tag == "link" and "pdf" in a.get("type", "").lower() and "alternate" in a.get("rel", "")
        ):
            self.urls.append(a.get("href", "").strip())


def pdf_links_in_html(markup: str, base_url: str) -> list[str]:
    parser = _PdfLinks()
    try:
        parser.feed(markup)
    except Exception:  # HTML quebrado: usa o que já foi lido
        pass
    return _unique([urljoin(base_url, u) for u in parser.urls if u])


async def article_page(client: httpx.AsyncClient, url: str) -> list[str]:
    """Abre a página do artigo e devolve os PDFs que ela declara. Se o endereço já for o PDF,
    devolve o próprio endereço."""
    got = await safefetch.get_bytes(
        client,
        url,
        max_bytes=PAGE_MAX_BYTES,
        headers={"Accept": "text/html,application/pdf"},
        # Páginas de revista que travam não podem segurar a busca inteira
        read_timeout=PAGE_TIMEOUT,
    )
    if got.data[:1024].lstrip().startswith(b"%PDF-"):
        return [got.url]
    markup = got.data.decode("utf-8", errors="replace")
    return pdf_links_in_html(markup, got.url)


DOI_LINK = re.compile(r"^10\.\d{4,9}/\S+$")


def doi_link(doi: str | None) -> str:
    return f"https://doi.org/{doi}" if doi and DOI_LINK.match(doi) else ""


PROXY_PLACEHOLDERS = ("{url}", "{host}", "{host_ez}", "{path}")


def valid_proxy_template(template: str) -> bool:
    """Modelo do proxy da instituição: começa por http(s)://, não tem espaço e usa {url} ou {host}."""
    if not template.startswith(("http://", "https://")) or re.search(r"\s", template):
        return False
    if not any(ph in template for ph in ("{url}", "{host}", "{host_ez}")):
        return False
    rest = template
    for ph in PROXY_PLACEHOLDERS:
        rest = rest.replace(ph, "")
    return "{" not in rest and "}" not in rest


def proxy_link(template: str, target: str) -> str:
    """Endereço do artigo aberto pelo proxy da instituição (CAFe, EZproxy...).

    {url}: endereço inteiro; {host}: o servidor com os pontos trocados por hífens (é o que o
    Portal CAPES faz: alz-journals.onlinelibrary.wiley.com vira
    alz-journals-onlinelibrary-wiley-com); {host_ez}: igual, mas hífens do nome viram dois,
    como o EZproxy padrão faz; {path}: o resto do endereço."""
    parts = urlsplit(target)
    if not template or not target or not parts.hostname:
        return ""
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    if parts.fragment:
        path += "#" + parts.fragment
    host = parts.hostname.replace(".", "-")
    host_ez = parts.hostname.replace("-", "--").replace(".", "-")
    return (
        template.replace("{url}", target)
        .replace("{host_ez}", host_ez)
        .replace("{host}", host)
        .replace("{path}", path)
    )
