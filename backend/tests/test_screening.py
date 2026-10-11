from revalli.modules.screening.service import kappa
from tests.conftest import invite_and_join
from tests.test_records import _import, _ris

TA = "title_abstract"


async def _setup(admin, n_records=4, reviewers=2):
    pid = (await admin.post("/api/projects", json={"title": "T"})).json()["id"]
    content = b"".join(
        _ris(f"Study number {i} about anxiety and sleep quality", author=f"A{i}, X") + b"\n"
        for i in range(n_records)
    )
    assert (await _import(admin, pid, "x.ris", content=content)).status_code == 201
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["reviewers_title_abstract"] = reviewers
    assert (await admin.put(f"/api/projects/{pid}/screening/settings", json=s)).status_code == 200
    ana = await invite_and_join(admin, "ana@ex.org", pid, "reviewer", name="Ana")
    bia = await invite_and_join(admin, "bia@ex.org", pid, "reviewer", name="Bia")
    return pid, ana, bia


async def _decide(client, pid, rid, decision, **kw):
    return await client.post(
        f"/api/projects/{pid}/screening/{TA}/decisions",
        json={"record_id": rid, "decision": decision, **kw},
    )


async def test_settings_defaults_and_validation(admin):
    pid = (await admin.post("/api/projects", json={"title": "T"})).json()["id"]
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    assert s["blind"] is True and s["reviewers_title_abstract"] == 2
    s["highlight_include"] = ["random*", " Random* ", "", "trial"]
    s["reviewers_full_text"] = 9
    assert (await admin.put(f"/api/projects/{pid}/screening/settings", json=s)).status_code == 422
    s["reviewers_full_text"] = 1
    r = await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    assert r.json()["highlight_include"] == ["random*", "trial"]


async def test_queue_and_decisions(admin):
    pid, ana, bia = await _setup(admin)
    q = (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()
    assert q["remaining"] == 4 and len(q["items"]) == 4
    rid = q["items"][0]["id"]
    assert (await _decide(ana, pid, rid, "include", labels=["RCT", "rct", " "])).status_code == 200
    q = (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()
    assert q["remaining"] == 3 and rid not in [i["id"] for i in q["items"]]
    # Ana muda de ideia: continua contando uma decisão só
    assert (await _decide(ana, pid, rid, "maybe")).status_code == 200
    mine = (await ana.get(f"/api/projects/{pid}/screening/{TA}/screened?state=mine")).json()
    assert mine["total"] == 1 and mine["items"][0]["record"]["my_decision"]["decision"] == "maybe"
    labels = (await admin.get(f"/api/projects/{pid}/screening/labels")).json()
    assert labels == ["RCT"]
    # Desfazer devolve o registro para a fila
    assert (await _decide(ana, pid, rid, None)).status_code == 200
    assert (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["remaining"] == 4
    await ana.aclose()
    await bia.aclose()


async def test_observer_cannot_screen(admin):
    pid, ana, bia = await _setup(admin)
    obs = await invite_and_join(admin, "obs@ex.org", pid, "observer")
    assert (await obs.get(f"/api/projects/{pid}/screening/{TA}/queue")).status_code == 403
    for c in (ana, bia, obs):
        await c.aclose()


async def test_agreement_conflicts_and_resolution(admin):
    pid, ana, bia = await _setup(admin)
    ids = [i["id"] for i in (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"]]
    reason = (
        await admin.post(f"/api/projects/{pid}/screening/reasons", json={"label": "População errada"})
    ).json()
    # r0: ambos incluem; r1: ambos excluem; r2: conflito; r3: só Ana
    await _decide(ana, pid, ids[0], "include")
    await _decide(bia, pid, ids[0], "include")
    await _decide(ana, pid, ids[1], "exclude", reason_ids=[reason["id"]])
    await _decide(bia, pid, ids[1], "exclude")
    await _decide(ana, pid, ids[2], "include")
    await _decide(bia, pid, ids[2], "exclude")
    await _decide(ana, pid, ids[3], "include")

    prog = (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()
    assert (prog["eligible"], prog["included"], prog["excluded"], prog["conflicts"], prog["pending"]) == (
        4,
        1,
        1,
        1,
        1,
    )
    # r0..r2 já têm 2 decisões; para o líder só falta r3
    assert prog["remaining_for_me"] == 1
    by_name = {r["full_name"]: r for r in prog["reviewers"]}
    assert by_name["Ana"]["decided"] == 4 and by_name["Bia"]["decided"] == 3

    # Com 2 revisores por registro, um terceiro não recebe r0..r2
    q = (await admin.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()
    assert [i["id"] for i in q["items"]] == [ids[3]]
    assert (await _decide(admin, pid, ids[0], "include")).status_code == 409

    # Cegamento ligado: líder não vê conflitos
    assert (await admin.get(f"/api/projects/{pid}/screening/{TA}/conflicts")).status_code == 409
    s = (await admin.get(f"/api/projects/{pid}/screening/settings")).json()
    s["blind"] = False
    await admin.put(f"/api/projects/{pid}/screening/settings", json=s)
    conf = (await admin.get(f"/api/projects/{pid}/screening/{TA}/conflicts")).json()
    assert conf["total"] == 1 and conf["items"][0]["record"]["id"] == ids[2]
    assert {d["user_name"] for d in conf["items"][0]["decisions"]} == {"Ana", "Bia"}

    # Revisores não resolvem
    r = await ana.post(
        f"/api/projects/{pid}/screening/{TA}/resolve", json={"record_id": ids[2], "decision": "include"}
    )
    assert r.status_code == 403
    r = await admin.post(
        f"/api/projects/{pid}/screening/{TA}/resolve", json={"record_id": ids[2], "decision": "maybe"}
    )
    assert r.status_code == 422
    r = await admin.post(
        f"/api/projects/{pid}/screening/{TA}/resolve",
        json={"record_id": ids[2], "decision": "exclude", "reason_ids": [reason["id"]]},
    )
    assert r.status_code == 200
    prog = (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()
    assert (prog["excluded"], prog["conflicts"]) == (2, 0)
    # Depois de resolvido, revisores não mudam mais
    assert (await _decide(ana, pid, ids[2], "include")).status_code == 409

    ag = (await admin.get(f"/api/projects/{pid}/screening/{TA}/agreement")).json()["pairs"]
    assert len(ag) == 1 and ag[0]["n"] == 3
    assert ag[0]["percent"] == 66.7

    # Reabrir o registro devolve o conflito
    await admin.post(
        f"/api/projects/{pid}/screening/{TA}/resolve", json={"record_id": ids[2], "decision": None}
    )
    assert (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()["conflicts"] == 1
    await ana.aclose()
    await bia.aclose()


async def test_arbitrator_sees_conflicts_even_when_blind(admin):
    pid, ana, bia = await _setup(admin, n_records=1)
    arb = await invite_and_join(admin, "arb@ex.org", pid, "arbitrator")
    rid = (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"][0]["id"]
    await _decide(ana, pid, rid, "include")
    await _decide(bia, pid, rid, "maybe")
    conf = (await arb.get(f"/api/projects/{pid}/screening/{TA}/conflicts")).json()
    assert conf["total"] == 1
    # Arbitro não tria
    assert (await arb.get(f"/api/projects/{pid}/screening/{TA}/queue")).status_code == 403
    for c in (ana, bia, arb):
        await c.aclose()


async def test_blind_hides_others_decisions(admin):
    pid, ana, bia = await _setup(admin, n_records=2)
    ids = [i["id"] for i in (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"]]
    await _decide(ana, pid, ids[0], "include", note="nota da Ana")
    await _decide(bia, pid, ids[0], "exclude")
    page = (await bia.get(f"/api/projects/{pid}/screening/{TA}/screened")).json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["state"] == "hidden"
    assert [d["user_name"] for d in item["decisions"]] == ["Bia"]
    await ana.aclose()
    await bia.aclose()


async def test_invalid_reason_and_unknown_record(admin):
    pid, ana, bia = await _setup(admin, n_records=1)
    rid = (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"][0]["id"]
    r = await _decide(ana, pid, rid, "exclude", reason_ids=["00000000-0000-0000-0000-000000000000"])
    assert r.status_code == 422
    r = await _decide(ana, pid, "00000000-0000-0000-0000-000000000000", "include")
    assert r.status_code == 404
    await ana.aclose()
    await bia.aclose()


async def test_duplicates_are_not_screened(admin):
    pid = (await admin.post("/api/projects", json={"title": "T"})).json()["id"]
    await _import(admin, pid, "a.ris", content=_ris("Same paper", doi="10.1000/same"))
    await _import(admin, pid, "b.ris", content=_ris("Same paper", doi="10.1000/same"))
    prog = (await admin.get(f"/api/projects/{pid}/screening/{TA}/progress")).json()
    assert prog["eligible"] == 1


async def test_full_text_phase_gets_only_included(admin):
    pid, ana, bia = await _setup(admin, n_records=3, reviewers=1)
    ids = [i["id"] for i in (await ana.get(f"/api/projects/{pid}/screening/{TA}/queue")).json()["items"]]
    await _decide(ana, pid, ids[0], "include")
    await _decide(ana, pid, ids[1], "exclude")
    ft = (await admin.get(f"/api/projects/{pid}/screening/full_text/progress")).json()
    assert ft["eligible"] == 1
    await ana.aclose()
    await bia.aclose()


def test_kappa():
    k, pct = kappa([("include", "include"), ("exclude", "exclude")])
    assert (k, pct) == (1.0, 1.0)
    k, pct = kappa([("include", "exclude"), ("exclude", "include")])
    assert pct == 0 and k == -1.0
    k, pct = kappa([("include", "include")] * 3)
    assert (k, pct) == (1.0, 1.0)
    assert kappa([]) == (None, None)
