import csv
import io

from tests.test_screening import TA, _decide, _setup

FT = "full_text"


async def _ids(client, pid, phase=TA):
    q = (await client.get(f"/api/projects/{pid}/screening/{phase}/queue")).json()
    return [i["id"] for i in q["items"]]


async def test_prisma_counts(admin):
    pid, ana, bia = await _setup(admin, n_records=4)
    reason = (
        await admin.post(f"/api/projects/{pid}/screening/reasons", json={"label": "Desenho errado"})
    ).json()["id"]
    ids = await _ids(ana, pid)
    # 0 e 1 incluídos, 2 excluído, 3 em conflito
    for c in (ana, bia):
        await _decide(c, pid, ids[0], "include")
        await _decide(c, pid, ids[1], "include")
        await _decide(c, pid, ids[2], "exclude")
    await _decide(ana, pid, ids[3], "include")
    await _decide(bia, pid, ids[3], "exclude")
    # Texto completo: 0 excluído com motivo, 1 incluído
    for c in (ana, bia):
        await c.post(
            f"/api/projects/{pid}/screening/{FT}/decisions",
            json={"record_id": ids[0], "decision": "exclude", "reason_ids": [reason]},
        )
        await c.post(
            f"/api/projects/{pid}/screening/{FT}/decisions",
            json={"record_id": ids[1], "decision": "include"},
        )
    p = (await ana.get(f"/api/projects/{pid}/report/prisma")).json()
    assert p["identification"]["total"] == 4
    assert p["identification"]["by_source"] == [{"source": "PubMed", "records": 4}]
    assert p["screening"] == {"screened": 4, "excluded": 1, "pending": 1}
    assert p["retrieval"]["sought"] == 2
    assert p["eligibility"]["assessed"] == 2
    assert p["eligibility"]["reasons"] == [{"reason": "Desenho errado", "count": 1}]
    assert p["included"] == 1
    await ana.aclose()
    await bia.aclose()


async def test_export_respects_blinding(admin):
    pid, ana, bia = await _setup(admin, n_records=2)
    ids = await _ids(ana, pid)
    await _decide(ana, pid, ids[0], "include", labels=["RCT"], note="ótimo")
    await _decide(bia, pid, ids[0], "maybe", note="dúvida")
    r = await ana.get(f"/api/projects/{pid}/export?format=csv")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    row = next(x for x in rows if x["id"] == ids[0])
    assert row["state"] == "conflito"
    # Com cegamento a Ana só vê a própria decisão
    assert row["decisions"] == "Ana: incluir" and "dúvida" not in row["notes"]
    assert row["labels"] == "RCT"

    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["blind"] = False
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    r = await ana.get(f"/api/projects/{pid}/export?format=ris&state=conflict")
    text = r.content.decode()
    assert text.count("ER  - ") == 1
    assert "N1  - ReValli, título e resumo: conflito" in text
    r = await ana.get(f"/api/projects/{pid}/export?format=csv&state=conflict")
    row = next(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert "Bia: talvez" in row["decisions"] and "Bia: dúvida" in row["notes"]
    await ana.aclose()
    await bia.aclose()


async def test_export_csv_neutralizes_formulas(admin):
    from tests.test_records import _import, _ris

    pid = (await admin.post("/api/projects", json={"title": "T"})).json()["id"]
    await _import(admin, pid, "x.ris", content=_ris("=HYPERLINK(1)", author="A, B"))
    r = await admin.get(f"/api/projects/{pid}/export?format=csv")
    row = next(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert row["title"] == "'=HYPERLINK(1)"


def test_slug_strips_accents():
    from revalli.modules.reports.router import _slug

    assert _slug("Exercício e ansiedade!") == "exercicio-e-ansiedade"
    assert _slug("***") == "projeto"
