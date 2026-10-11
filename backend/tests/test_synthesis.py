import csv
import io

from tests.conftest import invite_and_join
from tests.test_extraction import _project_included
from tests.test_fulltext import _upload, make_pdf


async def test_codes_tree_excerpts_matrix_and_export(admin):
    pid, (a, b, c) = await _project_included(admin)
    base = f"/api/projects/{pid}/coding"
    rev = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    obs = await invite_and_join(admin, "obs@ex.org", pid, "observer")

    barriers = (await admin.post(f"{base}/codes", json={"name": "Barreiras"})).json()
    cost = (
        await rev.post(f"{base}/codes", json={"name": "Custo", "parent_id": barriers["id"]})
    ).json()
    time = (
        await rev.post(f"{base}/codes", json={"name": "Tempo", "parent_id": barriers["id"]})
    ).json()
    fac = (await admin.post(f"{base}/codes", json={"name": "Facilitadores"})).json()
    assert (await obs.post(f"{base}/codes", json={"name": "X"})).status_code == 403
    assert cost["position"] == 0 and time["position"] == 1
    # Não pode mover um código para dentro de um filho dele
    r = await admin.patch(
        f"{base}/codes/{barriers['id']}", json={"move": True, "parent_id": cost["id"]}
    )
    assert r.status_code == 422

    up = await _upload(admin, pid, a, make_pdf("Cost was the main barrier to exercise."))
    file_id = up.json()["id"]
    r = await rev.post(
        f"{base}/excerpts",
        json={
            "record_id": a,
            "text": "Cost was the main barrier",
            "file_id": file_id,
            "page": 1,
            "code_ids": [cost["id"]],
        },
    )
    assert r.status_code == 201, r.text
    ex1 = r.json()
    assert ex1["study"] and ex1["user_name"] and ex1["code_ids"] == [cost["id"]]
    ex2 = (
        await admin.post(
            f"{base}/excerpts",
            json={
                "record_id": b,
                "text": "No time after work",
                "code_ids": [time["id"], fac["id"]],
            },
        )
    ).json()
    # Arquivo de outro estudo e código inexistente são recusados
    bad = {"record_id": b, "text": "x", "file_id": file_id, "code_ids": [cost["id"]]}
    assert (await admin.post(f"{base}/excerpts", json=bad)).status_code == 404
    bad = {"record_id": b, "text": "x", "code_ids": [pid]}
    assert (await admin.post(f"{base}/excerpts", json=bad)).status_code == 404
    # Só estudos incluídos
    rid_other = "00000000-0000-0000-0000-000000000000"
    bad = {"record_id": rid_other, "text": "x", "code_ids": [cost["id"]]}
    assert (await admin.post(f"{base}/excerpts", json=bad)).status_code == 404

    # Trechos de um código incluem os subcódigos
    under = (await obs.get(f"{base}/excerpts?code_id={barriers['id']}")).json()
    assert {e["id"] for e in under} == {ex1["id"], ex2["id"]}
    assert len((await obs.get(f"{base}/excerpts?record_id={a}")).json()) == 1

    m = (await obs.get(f"{base}/matrix")).json()
    assert len(m["units"]) == 3
    assert m["cells"][cost["id"]] == {a: 1}
    assert m["cells"][fac["id"]] == {b: 1}
    units = {u["record_id"]: u for u in m["units"]}
    assert units[a]["excerpts"] == 1 and units[a]["has_pdf"] and not units[c]["has_pdf"]

    codes = {x["name"]: x for x in (await obs.get(f"{base}/codes")).json()}
    assert codes["Custo"]["excerpts"] == 1 and codes["Barreiras"]["excerpts"] == 0

    # Quem não é dono nem líder não mexe no trecho dos outros
    r = await rev.patch(f"{base}/excerpts/{ex2['id']}", json={"note": "x"})
    assert r.status_code == 403
    r = await rev.patch(
        f"{base}/excerpts/{ex1['id']}", json={"note": "Citado 3x", "code_ids": [cost["id"]]}
    )
    assert r.json()["note"] == "Citado 3x"

    text = (await obs.get(f"{base}/export")).text.lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert {(r["code_path"], r["excerpt"]) for r in rows} == {
        ("Barreiras > Custo", "Cost was the main barrier"),
        ("Barreiras > Tempo", "No time after work"),
        ("Facilitadores", "No time after work"),
    }

    # Mesclar Tempo em Custo leva os trechos
    assert (
        await rev.post(f"{base}/codes/{time['id']}/merge", json={"into": cost["id"]})
    ).status_code == 403
    r = await admin.post(f"{base}/codes/{time['id']}/merge", json={"into": cost["id"]})
    assert r.json()["excerpts"] == 2
    # Apagar Facilitadores mantém o trecho (ainda tem Custo); apagar Barreiras leva tudo
    assert (await admin.delete(f"{base}/codes/{fac['id']}")).status_code == 204
    assert len((await obs.get(f"{base}/excerpts")).json()) == 2
    assert (await rev.delete(f"{base}/codes/{barriers['id']}")).status_code == 403
    assert (await admin.delete(f"{base}/codes/{barriers['id']}")).status_code == 204
    assert (await obs.get(f"{base}/excerpts")).json() == []
    assert (await obs.get(f"{base}/codes")).json() == []


async def test_checklist(admin):
    pid, _ = await _project_included(admin)
    base = f"/api/projects/{pid}/checklists"
    rev = await invite_and_join(admin, "rev@ex.org", pid, "reviewer")
    r = (await rev.get(f"{base}/prisma2020")).json()
    assert len(r["entries"]) == 42 and r["entries"][9]["item"] == "10a"
    assert all(e["status"] == "pending" for e in r["entries"])
    facts = r["facts"]
    assert facts["searches"][0]["source"] == "PubMed"
    assert facts["screening"]["reviewers_full_text"] == 1
    assert facts["prisma"]["included"] == 3
    assert len((await rev.get(f"{base}/prisma_scr")).json()["entries"]) == 22

    body = {"status": "done", "location": "Métodos, p. 4", "note": ""}
    assert (await rev.put(f"{base}/prisma2020/7", json=body)).status_code == 403
    assert (await admin.put(f"{base}/prisma2020/99", json=body)).status_code == 404
    r = await admin.put(f"{base}/prisma2020/7", json=body)
    assert r.status_code == 200 and r.json()["location"] == "Métodos, p. 4"
    r = await admin.put(f"{base}/prisma2020/7", json={**body, "status": "na"})
    entries = {e["item"]: e for e in (await rev.get(f"{base}/prisma2020")).json()["entries"]}
    assert entries["7"]["status"] == "na"
    text = (await rev.get(f"{base}/prisma2020/export")).text
    assert '"7","na","Métodos, p. 4",""' in text
