"""Benchmark da IA do ReValli sobre um conjunto de dados já rotulado.

Mede duas coisas:

1. Aprendizado ativo: simula a triagem na ordem sugerida pelo modelo e calcula o recall ao
   longo do caminho, o trabalho economizado (WSS@95) e onde a regra de parada teria parado.
2. Triagem por IA (opcional): pergunta ao modelo de chat sobre cada registro e compara com os
   rótulos (sensibilidade e especificidade).

Entrada: um CSV com as colunas ``title``, ``abstract`` e ``label_included`` (1 ou 0), como os
conjuntos do SYNERGY (doi:10.34894/HE6NAQ). Exemplos:

    python -m revalli.benchmark dados.csv --embedder hashing
    python -m revalli.benchmark dados.csv --embedder api --base-url http://localhost:11434/v1 \\
        --embed-model bge-m3
    python -m revalli.benchmark dados.csv --screen --base-url http://localhost:11434/v1 \\
        --model qwen3:8b --criteria criterios.txt --limit 300

O relatório sai em Markdown na saída padrão (ou em ``--out``).
"""

import argparse
import asyncio
import csv
import hashlib
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from revalli.modules.ai.active import predict, train_logistic

LABEL_COLUMNS = ("label_included", "included", "label")


@dataclass
class Dataset:
    titles: list[str]
    abstracts: list[str]
    labels: np.ndarray

    @property
    def texts(self) -> list[str]:
        return [f"{t}\n\n{a}" for t, a in zip(self.titles, self.abstracts, strict=True)]


def load_csv(path: str | Path) -> Dataset:
    csv.field_size_limit(sys.maxsize)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("empty dataset")
    col = next((c for c in LABEL_COLUMNS if c in rows[0]), None)
    if col is None:
        raise ValueError(f"missing label column (one of {', '.join(LABEL_COLUMNS)})")
    return Dataset(
        titles=[r.get("title") or "" for r in rows],
        abstracts=[r.get("abstract") or "" for r in rows],
        labels=np.array([int(float(r[col] or 0)) for r in rows], dtype=np.int64),
    )


# --- Embeddings ------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-zà-ÿ0-9]+")


def hashing_embed(texts: list[str], dim: int = 1024) -> np.ndarray:
    """Vetor de termos com hashing e TF logarítmico. Não precisa de modelo nem de rede."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        for tok in _TOKEN.findall(text.lower()):
            if len(tok) < 3:
                continue
            h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "little")
            out[i, h % dim] += 1
    np.log1p(out, out=out)
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.where(norms == 0, 1, norms)


async def api_embed(texts: list[str], base_url: str, model: str, api_key: str = "") -> np.ndarray:
    from revalli.modules.ai import client

    ep = client.Endpoint(base_url=base_url, api_key=api_key, model=model)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 32):
        chunk, _ = await client.embed(ep, [t[:4000] for t in texts[start : start + 32]])
        vectors.extend(chunk)
    m = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


# --- Simulação do aprendizado ativo -------------------------------------------------------


@dataclass
class Simulation:
    order: list[int]
    found: list[int] = field(default_factory=list)
    stop_at: int | None = None

    def recall_at(self, n: int, total_relevant: int) -> float:
        return self.found[n - 1] / total_relevant if n else 0.0

    def screened_for_recall(self, target: float, total_relevant: int) -> int:
        need = math.ceil(target * total_relevant)
        return next(i + 1 for i, f in enumerate(self.found) if f >= need)


def simulate(
    x: np.ndarray,
    y: np.ndarray,
    *,
    batch: int = 10,
    stop_after: int = 100,
    seed: int = 0,
) -> Simulation:
    """Triagem simulada: começa com um relevante e um irrelevante sorteados (o "conhecimento
    prévio" de praxe nesses estudos) e retreina o modelo a cada ``batch`` decisões."""
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    if len(pos) == 0 or len(neg) == 0:
        raise ValueError("dataset needs both included and excluded records")
    order = [int(rng.choice(pos)), int(rng.choice(neg))]
    seen = np.zeros(len(y), dtype=bool)
    seen[order] = True
    w = None
    while not seen.all():
        idx = np.flatnonzero(seen)
        # Começa do modelo anterior; o lote cresce com o que já foi lido para o custo não explodir
        w = train_logistic(x[idx], y[idx].astype(np.float64), steps=100, w0=w)
        rest = np.flatnonzero(~seen)
        scores = predict(w, x[rest])
        step = max(batch, len(idx) // 20)
        take = rest[np.argsort(-scores, kind="stable")[:step]]
        order.extend(int(i) for i in take)
        seen[take] = True
    sim = Simulation(order=order)
    found = since_last = 0
    for n, i in enumerate(order, 1):
        if y[i]:
            found += 1
            since_last = 0
        else:
            since_last += 1
        sim.found.append(found)
        if sim.stop_at is None and n > 2 and since_last >= stop_after:
            sim.stop_at = n
    return sim


def wss(sim: Simulation, total: int, total_relevant: int, recall: float = 0.95) -> float:
    """Trabalho economizado em relação à leitura em ordem aleatória, no recall pedido."""
    n = sim.screened_for_recall(recall, total_relevant)
    return (total - n) / total - (1 - recall)


# --- Triagem por IA -------------------------------------------------------------------------


async def ai_screen(
    data: Dataset,
    base_url: str,
    model: str,
    criteria: str,
    api_key: str = "",
    limit: int | None = None,
) -> dict:
    from revalli.modules.ai import client
    from revalli.modules.ai.prompts import build_messages
    from revalli.modules.ai.service import normalize_answer
    from revalli.modules.screening.schemas import ScreeningSettings

    ep = client.Endpoint(base_url=base_url, api_key=api_key, model=model)
    project = SimpleNamespace(title="Benchmark", review_type="systematic")
    settings = ScreeningSettings(inclusion_criteria=criteria)
    n = min(limit or len(data.labels), len(data.labels))
    # Amostra estável e com os incluídos representados
    idx = sorted(range(len(data.labels)), key=lambda i: hashlib.sha256(str(i).encode()).digest())[
        :n
    ]
    tp = fp = tn = fn = errors = 0
    for i in idx:
        record = SimpleNamespace(
            title=data.titles[i],
            abstract=data.abstracts[i],
            year=None,
            journal="",
            publication_type="",
            language="",
            keywords=[],
        )
        try:
            result = await client.chat(ep, build_messages(project, settings, record))
            ans = normalize_answer(client.parse_json(result.content))
        except client.AIError:
            errors += 1
            continue
        inc = ans["decision"] != "exclude"
        if data.labels[i]:
            tp, fn = tp + inc, fn + (not inc)
        else:
            fp, tn = fp + inc, tn + (not inc)
    return {
        "n": n,
        "errors": errors,
        "sensitivity": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


# --- Relatório ---------------------------------------------------------------------------


def report(name: str, data: Dataset, sims: list[Simulation], screen: dict | None) -> str:
    total, rel = len(data.labels), int(data.labels.sum())
    lines = [
        f"# Benchmark do ReValli: {name}",
        "",
        f"- Registros: {total}",
        f"- Incluídos: {rel} ({rel / total:.1%})",
        "",
        "## Aprendizado ativo",
        "",
        "| Execução | Lidos p/ 95% | WSS@95 | Recall após 10% | Parada sugerida em | Recall na parada |",
        "|---|---|---|---|---|---|",
    ]
    for k, s in enumerate(sims, 1):
        n95 = s.screened_for_recall(0.95, rel)
        r10 = s.recall_at(max(1, total // 10), rel)
        stop = s.stop_at or total
        lines.append(
            f"| {k} | {n95} ({n95 / total:.1%}) | {wss(s, total, rel):.3f} | {r10:.1%} "
            f"| {stop} ({stop / total:.1%}) | {s.recall_at(stop, rel):.1%} |"
        )
    if screen:
        sens = screen["sensitivity"]
        spec = screen["specificity"]
        lines += [
            "",
            "## Triagem por IA",
            "",
            f"- Registros avaliados: {screen['n']} (respostas inválidas: {screen['errors']})",
            f"- Sensibilidade: {sens:.1%}" if sens is not None else "- Sensibilidade: –",
            f"- Especificidade: {spec:.1%}" if spec is not None else "- Especificidade: –",
            f"- VP {screen['tp']} · FN {screen['fn']} · VN {screen['tn']} · FP {screen['fp']}",
            "",
            "Meta do marco M3: sensibilidade de pelo menos 95% no modo segunda revisora.",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("dataset")
    ap.add_argument("--embedder", choices=["hashing", "api"], default="hashing")
    ap.add_argument("--base-url", default=os.environ.get("REVALLI_AI_BASE_URL", ""))
    ap.add_argument("--api-key", default=os.environ.get("REVALLI_AI_API_KEY", ""))
    ap.add_argument("--embed-model", default="bge-m3")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--stop-after", type=int, default=100)
    ap.add_argument("--screen", action="store_true", help="também roda a triagem por IA")
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--criteria", help="arquivo de texto com os critérios de inclusão")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    data = load_csv(args.dataset)
    if args.embedder == "api":
        x = asyncio.run(api_embed(data.texts, args.base_url, args.embed_model, args.api_key))
    else:
        x = hashing_embed(data.texts)
    sims = [simulate(x, data.labels, stop_after=args.stop_after, seed=s) for s in range(args.runs)]
    screen = None
    if args.screen:
        criteria = Path(args.criteria).read_text() if args.criteria else ""
        screen = asyncio.run(
            ai_screen(data, args.base_url, args.model, criteria, args.api_key, args.limit)
        )
    text = report(Path(args.dataset).stem, data, sims, screen)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
