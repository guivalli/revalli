"""Modelos prontos de formulário e os algoritmos de julgamento dos instrumentos de risco de viés.

As perguntas são paráfrases em português, não o texto oficial dos instrumentos. Consulte
sempre a orientação oficial de cada instrumento ao avaliar um estudo:

- RoB 2 (Sterne et al., BMJ 2019;366:l4898), versão para ensaios com randomização individual
  e efeito da atribuição à intervenção.
- ROBINS-I (Sterne et al., BMJ 2016;355:i4919), com julgamento por domínio.
"""

from collections.abc import Callable

SIGNAL = ["Y", "PY", "PN", "N", "NI"]
ROB2_SCALE = ["low", "some", "high"]
ROBINS_SCALE = ["low", "moderate", "serious", "critical", "ni"]
YES = ("Y", "PY")
NO = ("N", "PN")


def _sig(fid: str, label: str, domain: str, *conds: tuple[str, list[str]], help: str = "") -> dict:
    return {
        "id": fid,
        "label": label,
        "type": "signal",
        "options": SIGNAL,
        "domain": domain,
        "help": help,
        "ai": True,
        "show_if": [{"field": f, "values": v} for f, v in conds],
    }


def _judgement(fid: str, label: str, domain: str, algorithm: str, scale: list[str]) -> dict:
    return {
        "id": fid,
        "label": label,
        "type": "judgement",
        "options": scale,
        "domain": domain,
        "algorithm": algorithm,
    }


def _notes(fid: str, domain: str) -> dict:
    return {"id": fid, "label": "Justificativa", "type": "long_text", "domain": domain}


ROB2_DOMAINS = [
    ("d1", "Processo de randomização"),
    ("d2", "Desvios das intervenções pretendidas"),
    ("d3", "Dados faltantes do desfecho"),
    ("d4", "Medição do desfecho"),
    ("d5", "Seleção do resultado relatado"),
]

ROBINS_DOMAINS = [
    ("d1", "Confundimento"),
    ("d2", "Seleção dos participantes"),
    ("d3", "Classificação das intervenções"),
    ("d4", "Desvios das intervenções pretendidas"),
    ("d5", "Dados faltantes"),
    ("d6", "Medição dos desfechos"),
    ("d7", "Seleção do resultado relatado"),
]


def rob2_fields() -> list[dict]:
    n = NO + ("NI",)
    yni = YES + ("NI",)
    d = dict(ROB2_DOMAINS)
    return [
        {"id": "outcome", "label": "Desfecho e resultado avaliados", "type": "text"},
        {"id": "s_d1", "label": f"D1. {d['d1']}", "type": "section", "domain": "d1"},
        _sig("d1_1", "1.1 A sequência de alocação foi aleatória?", "d1"),
        _sig(
            "d1_2",
            "1.2 A sequência ficou oculta até a inclusão e alocação dos participantes?",
            "d1",
        ),
        _sig(
            "d1_3",
            "1.3 As diferenças entre os grupos no início sugerem problema na randomização?",
            "d1",
        ),
        _judgement("d1_j", "Risco de viés no domínio 1", "d1", "rob2_d1", ROB2_SCALE),
        _notes("d1_n", "d1"),
        {"id": "s_d2", "label": f"D2. {d['d2']}", "type": "section", "domain": "d2"},
        _sig("d2_1", "2.1 Os participantes sabiam a que intervenção foram alocados?", "d2"),
        _sig(
            "d2_2",
            "2.2 Os cuidadores e quem aplicou as intervenções sabiam a alocação?",
            "d2",
        ),
        _sig(
            "d2_3",
            "2.3 Houve desvios da intervenção pretendida por causa do contexto do estudo?",
            "d2",
            help="Responda se 2.1 ou 2.2 for sim, provavelmente sim ou sem informação.",
        ),
        _sig("d2_4", "2.4 Esses desvios podem ter afetado o desfecho?", "d2", ("d2_3", list(YES))),
        _sig(
            "d2_5",
            "2.5 Esses desvios ficaram equilibrados entre os grupos?",
            "d2",
            ("d2_3", list(YES)),
            ("d2_4", list(yni)),
        ),
        _sig(
            "d2_6",
            "2.6 A análise foi adequada para estimar o efeito da atribuição (ex.: intenção de tratar)?",
            "d2",
        ),
        _sig(
            "d2_7",
            "2.7 A falha na análise pode ter tido impacto importante no resultado?",
            "d2",
            ("d2_6", list(n)),
        ),
        _judgement("d2_j", "Risco de viés no domínio 2", "d2", "rob2_d2", ROB2_SCALE),
        _notes("d2_n", "d2"),
        {"id": "s_d3", "label": f"D3. {d['d3']}", "type": "section", "domain": "d3"},
        _sig(
            "d3_1",
            "3.1 Havia dados do desfecho para todos ou quase todos os participantes randomizados?",
            "d3",
        ),
        _sig(
            "d3_2",
            "3.2 Há evidência de que o resultado não foi enviesado pelos dados faltantes?",
            "d3",
            ("d3_1", list(n)),
        ),
        _sig(
            "d3_3",
            "3.3 A falta de dados pode depender do valor real do desfecho?",
            "d3",
            ("d3_1", list(n)),
            ("d3_2", list(n)),
        ),
        _sig(
            "d3_4",
            "3.4 É provável que a falta de dados dependa do valor real do desfecho?",
            "d3",
            ("d3_1", list(n)),
            ("d3_2", list(n)),
            ("d3_3", list(yni)),
        ),
        _judgement("d3_j", "Risco de viés no domínio 3", "d3", "rob2_d3", ROB2_SCALE),
        _notes("d3_n", "d3"),
        {"id": "s_d4", "label": f"D4. {d['d4']}", "type": "section", "domain": "d4"},
        _sig("d4_1", "4.1 O método de medir o desfecho foi inadequado?", "d4"),
        _sig(
            "d4_2",
            "4.2 A medição ou a verificação do desfecho pode ter sido diferente entre os grupos?",
            "d4",
        ),
        _sig(
            "d4_3",
            "4.3 Quem avaliou o desfecho sabia a intervenção recebida?",
            "d4",
            ("d4_1", list(n)),
            ("d4_2", list(n)),
        ),
        _sig(
            "d4_4",
            "4.4 Saber a intervenção pode ter influenciado a avaliação do desfecho?",
            "d4",
            ("d4_1", list(n)),
            ("d4_2", list(n)),
            ("d4_3", list(yni)),
        ),
        _sig(
            "d4_5",
            "4.5 É provável que saber a intervenção tenha influenciado a avaliação?",
            "d4",
            ("d4_1", list(n)),
            ("d4_2", list(n)),
            ("d4_3", list(yni)),
            ("d4_4", list(yni)),
        ),
        _judgement("d4_j", "Risco de viés no domínio 4", "d4", "rob2_d4", ROB2_SCALE),
        _notes("d4_n", "d4"),
        {"id": "s_d5", "label": f"D5. {d['d5']}", "type": "section", "domain": "d5"},
        _sig(
            "d5_1",
            "5.1 Os dados foram analisados segundo um plano pré-especificado, "
            "finalizado antes de os dados não cegos estarem disponíveis?",
            "d5",
        ),
        _sig(
            "d5_2",
            "5.2 O resultado pode ter sido escolhido entre várias medidas do desfecho?",
            "d5",
        ),
        _sig(
            "d5_3",
            "5.3 O resultado pode ter sido escolhido entre várias análises dos dados?",
            "d5",
        ),
        _judgement("d5_j", "Risco de viés no domínio 5", "d5", "rob2_d5", ROB2_SCALE),
        _notes("d5_n", "d5"),
        {"id": "s_overall", "label": "Julgamento geral", "type": "section", "domain": "overall"},
        _judgement("overall_j", "Risco de viés geral", "overall", "rob2_overall", ROB2_SCALE),
        _notes("overall_n", "overall"),
    ]


def robins_fields() -> list[dict]:
    out: list[dict] = [
        {"id": "outcome", "label": "Desfecho e resultado avaliados", "type": "text"},
        {
            "id": "confounders",
            "label": "Fatores de confusão considerados",
            "type": "long_text",
            "ai": True,
        },
    ]
    for did, label in ROBINS_DOMAINS:
        n = did[1:]
        out += [
            {"id": f"s_{did}", "label": f"D{n}. {label}", "type": "section", "domain": did},
            {
                "id": f"{did}_j",
                "label": f"Risco de viés no domínio {n}",
                "type": "judgement",
                "options": ROBINS_SCALE,
                "domain": did,
            },
            _notes(f"{did}_n", did),
        ]
    out += [
        {"id": "s_overall", "label": "Julgamento geral", "type": "section", "domain": "overall"},
        _judgement("overall_j", "Risco de viés geral", "overall", "robins_overall", ROBINS_SCALE),
        _notes("overall_n", "overall"),
    ]
    return out


DESIGNS = [
    "Ensaio clínico randomizado",
    "Ensaio não randomizado",
    "Coorte",
    "Caso-controle",
    "Transversal",
    "Qualitativo",
    "Métodos mistos",
    "Outro",
]


def characteristics_fields() -> list[dict]:
    def f(fid, label, type_="text", **kw):
        return {"id": fid, "label": label, "type": type_, "ai": True, **kw}

    return [
        {"id": "s_study", "label": "Estudo", "type": "section"},
        f("country", "País"),
        f("design", "Delineamento", "choice", options=DESIGNS),
        f("setting", "Local e contexto"),
        f("period", "Período de recrutamento"),
        f("funding", "Financiamento"),
        {"id": "s_participants", "label": "Participantes", "type": "section"},
        f("population", "População e critérios de elegibilidade", "long_text"),
        f("n_total", "Número de participantes", "integer"),
        f("age", "Idade (média ou mediana)"),
        f("female_pct", "Mulheres (%)", "number"),
        {"id": "s_interventions", "label": "Intervenções", "type": "section"},
        f("intervention", "Intervenção", "long_text"),
        f("comparator", "Comparador", "long_text"),
        f("followup", "Tempo de seguimento"),
        {"id": "s_outcomes", "label": "Desfechos e resultados", "type": "section"},
        f("outcomes", "Desfechos avaliados", "long_text"),
        f(
            "arms",
            "Resultados por grupo",
            "table",
            columns=[
                {"id": "group", "label": "Grupo", "type": "text"},
                {"id": "n", "label": "N", "type": "integer"},
                {"id": "mean", "label": "Média", "type": "number"},
                {"id": "sd", "label": "DP", "type": "number"},
                {"id": "events", "label": "Eventos", "type": "integer"},
            ],
            ai_hint="Uma linha por grupo para o desfecho principal.",
        ),
        f("main_result", "Resultado principal (texto)", "long_text"),
        {"id": "notes", "label": "Observações", "type": "long_text"},
    ]


TEMPLATES: dict[str, dict] = {
    "rob2": {"name": "RoB 2", "kind": "rob", "fields": rob2_fields},
    "robins_i": {"name": "ROBINS-I", "kind": "rob", "fields": robins_fields},
    "study_characteristics": {
        "name": "Características dos estudos",
        "kind": "extraction",
        "fields": characteristics_fields,
    },
}


# --- Algoritmos ----------------------------------------------------------------------


def _yes(v):
    return v in YES


def _no(v):
    return v in NO


def _worst(values: list[str | None], scale: list[str]) -> str | None:
    if any(v is None for v in values):
        return None
    return max(values, key=scale.index)


def rob2_d1(v: dict) -> str | None:
    q1, q2, q3 = v.get("d1_1"), v.get("d1_2"), v.get("d1_3")
    if not (q1 and q2 and q3):
        return None
    if _no(q2):
        return "high"
    if q2 == "NI":
        return "high" if _yes(q3) else "some"
    if _yes(q3) or _no(q1):
        return "some"
    return "low"


def rob2_d2(v: dict) -> str | None:
    q = [v.get(f"d2_{i}") for i in range(1, 8)]
    if not (q[0] and q[1]):
        return None
    if _no(q[0]) and _no(q[1]):
        part1 = "low"
    elif not q[2]:
        return None
    elif _no(q[2]):
        part1 = "low"
    elif q[2] == "NI":
        part1 = "some"
    elif not q[3]:
        return None
    elif _no(q[3]):
        part1 = "some"
    elif not q[4]:
        return None
    else:
        part1 = "some" if _yes(q[4]) else "high"
    if not q[5]:
        return None
    if _yes(q[5]):
        part2 = "low"
    elif not q[6]:
        return None
    else:
        part2 = "some" if _no(q[6]) else "high"
    return _worst([part1, part2], ROB2_SCALE)


def rob2_d3(v: dict) -> str | None:
    q1, q2, q3, q4 = (v.get(f"d3_{i}") for i in range(1, 5))
    if not q1:
        return None
    if _yes(q1):
        return "low"
    if not q2:
        return None
    if _yes(q2):
        return "low"
    if not q3:
        return None
    if _no(q3):
        return "low"
    if not q4:
        return None
    return "some" if _no(q4) else "high"


def rob2_d4(v: dict) -> str | None:
    q1, q2, q3, q4, q5 = (v.get(f"d4_{i}") for i in range(1, 6))
    if not (q1 and q2):
        return None
    if _yes(q1) or _yes(q2):
        return "high"
    if not q3:
        return None
    if _no(q3):
        base = "low"
    elif not q4:
        return None
    elif _no(q4):
        base = "low"
    elif not q5:
        return None
    else:
        base = "some" if _no(q5) else "high"
    if q2 == "NI" and base == "low":
        return "some"
    return base


def rob2_d5(v: dict) -> str | None:
    q1, q2, q3 = (v.get(f"d5_{i}") for i in range(1, 4))
    if _yes(q2) or _yes(q3):
        return "high"
    if not (q1 and q2 and q3):
        return None
    if _yes(q1) and _no(q2) and _no(q3):
        return "low"
    return "some"


def _effective(v: dict, suggested: dict, fid: str) -> str | None:
    return v.get(fid) or suggested.get(fid)


def rob2_overall(v: dict, suggested: dict) -> str | None:
    return _worst([_effective(v, suggested, f"d{i}_j") for i in range(1, 6)], ROB2_SCALE)


def robins_overall(v: dict, suggested: dict) -> str | None:
    judgements = [_effective(v, suggested, f"d{i}_j") for i in range(1, 8)]
    if any(j is None for j in judgements):
        return None
    for level in ("critical", "serious"):
        if level in judgements:
            return level
    if "ni" in judgements:
        return "ni"
    return "moderate" if "moderate" in judgements else "low"


DOMAIN_ALGORITHMS: dict[str, Callable[[dict], str | None]] = {
    "rob2_d1": rob2_d1,
    "rob2_d2": rob2_d2,
    "rob2_d3": rob2_d3,
    "rob2_d4": rob2_d4,
    "rob2_d5": rob2_d5,
}
OVERALL_ALGORITHMS: dict[str, Callable[[dict, dict], str | None]] = {
    "rob2_overall": rob2_overall,
    "robins_overall": robins_overall,
}


def suggest(fields: list[dict], values: dict) -> dict[str, str]:
    """Julgamentos calculados. O valor escolhido pela pessoa, se houver, prevalece."""
    out: dict[str, str] = {}
    for f in fields:
        alg = DOMAIN_ALGORITHMS.get(f.get("algorithm", ""))
        if alg and (res := alg(values)):
            out[f["id"]] = res
    for f in fields:
        alg = OVERALL_ALGORITHMS.get(f.get("algorithm", ""))
        if alg and (res := alg(values, out)):
            out[f["id"]] = res
    return out


def effective_values(fields: list[dict], values: dict) -> dict:
    """Valores com os julgamentos calculados no lugar dos que ficaram em branco."""
    sug = suggest(fields, values)
    return {**values, **{k: v for k, v in sug.items() if not values.get(k)}}
