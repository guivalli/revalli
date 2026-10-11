import base64
import io
import zipfile

import pymupdf

from tests.test_extraction import _project_included
from tests.test_meta import _bcg_rows


def _png(shade: int = 220) -> str:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 200), 0)
    pix.clear_with(shade)
    return base64.b64encode(pix.tobytes("png")).decode()


async def _setup(admin):
    pid, _ = await _project_included(admin)
    aid = (
        await admin.post(
            f"/api/projects/{pid}/meta",
            json={"name": "Tuberculose", "measure": "RR", "rows": _bcg_rows()},
        )
    ).json()["id"]
    await admin.post(
        f"/api/projects/{pid}/grade",
        json={
            "outcome": "Casos de tuberculose",
            "analysis_id": aid,
            "effect": "RR 0,49",
            "domains": {"inconsistency": {"rating": -1, "reason": "I² de 92%"}},
        },
    )
    await admin.put(
        f"/api/projects/{pid}/checklists/prisma2020/1",
        json={"status": "done", "location": "Título", "note": ""},
    )
    return pid, aid


def _docx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return z.read("word/document.xml").decode()


async def test_docx_report(admin):
    pid, aid = await _setup(admin)
    url = f"/api/projects/{pid}/report/document"
    body = {
        "format": "docx",
        "figures": {"prisma": _png(), f"meta:{aid}": "data:image/png;base64," + _png(180)},
        "checklist_items": {"1": "Identifique o relatório como revisão sistemática."},
    }
    r = await admin.post(url, json=body)
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].endswith('.docx"')
    xml = _docx_text(r.content)
    for text in (
        "Métodos",
        "Seleção dos estudos",
        "Estudos incluídos",
        "Casos de tuberculose",
        "⊕⊕⊕◯ Moderada",
        "inconsistência (-1): I² de 92%",
        "13 estudo(s): RR 0,49 (IC 95% 0,34 a 0,70)",
        "Apêndice C. Checklist PRISMA 2020",
        "Identifique o relatório como revisão sistemática.",
        "vibecodado",
    ):
        assert text in xml, text
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert len([n for n in z.namelist() if n.startswith("word/media/")]) == 2

    # Em inglês, só métodos
    r = await admin.post(url, json={"format": "docx", "lang": "en", "sections": ["methods"]})
    xml = _docx_text(r.content)
    assert "Methods" in xml and "Study selection" not in xml and "random effects" in xml


async def test_pdf_report_and_figure_checks(admin):
    pid, aid = await _setup(admin)
    url = f"/api/projects/{pid}/report/document"
    r = await admin.post(url, json={"format": "pdf", "figures": {"prisma": _png()}})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    doc = pymupdf.open("pdf", r.content)
    text = "".join(p.get_text() for p in doc)
    assert "Sumário de achados" in text and "Apêndice B. Registro de uso da IA" in text
    assert doc.metadata["title"] and sum(len(p.get_images()) for p in doc) == 1

    bad = base64.b64encode(b"GIF89a-not-a-png").decode()
    r = await admin.post(url, json={"format": "pdf", "figures": {"prisma": bad}})
    assert r.status_code == 422
    r = await admin.post(url, json={"format": "pdf", "figures": {"prisma": "%%%"}})
    assert r.status_code == 422
