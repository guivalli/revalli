"""Leitura de PDFs com PyMuPDF: texto por página, título dos metadados e DOI."""

import re
from dataclasses import dataclass

import pymupdf

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)


class PDFError(Exception):
    pass


@dataclass
class PDFInfo:
    pages: list[str]
    title: str
    doi: str | None

    @property
    def has_text(self) -> bool:
        # PDFs escaneados não têm camada de texto; basta uma página com texto de verdade
        return any(len(p.strip()) > 50 for p in self.pages)


def looks_like_pdf(data: bytes) -> bool:
    return data[:1024].lstrip().startswith(b"%PDF-")


def read_pdf(data: bytes, max_pages: int = 2000) -> PDFInfo:
    if not looks_like_pdf(data):
        raise PDFError("not_a_pdf")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF levanta vários tipos diferentes
        raise PDFError("invalid_pdf") from exc
    with doc:
        if doc.needs_pass:
            raise PDFError("encrypted_pdf")
        pages = [doc[i].get_text("text") for i in range(min(doc.page_count, max_pages))]
        title = (doc.metadata or {}).get("title") or ""
    head = "\n".join(pages[:2])
    m = DOI_RE.search(head)
    doi = m.group(1).rstrip(".,;)]").lower() if m else None
    # Remove caracteres nulos, que o Postgres não aceita em texto
    return PDFInfo(pages=[p.replace("\x00", "") for p in pages], title=title.strip(), doi=doi)
