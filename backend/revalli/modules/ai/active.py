"""Aprendizado ativo: embeddings dos registros, ordenação da fila por relevância provável,
curva de inclusões e uma regra de parada configurável."""

import hashlib
import uuid
from collections.abc import Callable

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revalli.models import AIUsage, DecisionEvent, Project, Record, RecordEmbedding
from revalli.modules.ai import client
from revalli.modules.ai.service import bot_user, project_ai, resolve
from revalli.modules.screening.models import Decision, Phase
from revalli.modules.screening.service import UNDO, compute_states

BATCH = 32
MAX_CHARS = 4000
MIN_LABELS = 2  # pelo menos um incluído e um excluído

# Último modelo treinado por projeto, para não treinar de novo a cada pedido da fila
_MODELS: dict[uuid.UUID, tuple[str, np.ndarray]] = {}


def record_text(r: Record) -> str:
    return f"{r.title}\n\n{r.abstract}"[:MAX_CHARS]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def embed_project(
    db: AsyncSession, project: Project, progress: Callable[[int, int], None] | None = None
) -> dict:
    """Calcula os embeddings que faltam (ou que mudaram desde a última vez)."""
    res = await resolve(db, "embeddings", project_ai(project).local_only)
    ids = list(await compute_states(db, project, Phase.title_abstract))
    records = (await db.execute(select(Record).where(Record.id.in_(ids)))).scalars().all()
    existing = {
        e.record_id: e.text_hash
        for e in (
            await db.execute(
                select(RecordEmbedding.record_id, RecordEmbedding.text_hash).where(
                    RecordEmbedding.record_id.in_(ids), RecordEmbedding.model_key == res.model_key
                )
            )
        ).all()
    }
    todo = [r for r in records if existing.get(r.id) != text_hash(record_text(r))]
    done = 0
    for start in range(0, len(todo), BATCH):
        chunk = todo[start : start + BATCH]
        texts = [record_text(r) for r in chunk]
        vectors, tokens = await client.embed(res.endpoint, texts)
        db.add(
            AIUsage(
                project_id=project.id,
                provider_id=res.provider.id,
                model=res.choice.model,
                task="embeddings",
                input_tokens=tokens,
                cost_usd=res.cost(tokens, 0),
            )
        )
        for r, text, vec in zip(chunk, texts, vectors, strict=True):
            row = await db.get(RecordEmbedding, (r.id, res.model_key))
            data = np.asarray(vec, dtype=np.float32).tobytes()
            if row is None:
                db.add(
                    RecordEmbedding(
                        record_id=r.id,
                        model_key=res.model_key,
                        text_hash=text_hash(text),
                        vector=data,
                    )
                )
            else:
                row.text_hash, row.vector = text_hash(text), data
        await db.commit()
        done += len(chunk)
        if progress:
            progress(done, len(todo))
    return {"embedded": done, "total": len(records), "model": res.choice.model}


async def load_vectors(
    db: AsyncSession, record_ids: list[uuid.UUID], model_key: str
) -> dict[uuid.UUID, np.ndarray]:
    rows = await db.execute(
        select(RecordEmbedding.record_id, RecordEmbedding.vector).where(
            RecordEmbedding.record_id.in_(record_ids), RecordEmbedding.model_key == model_key
        )
    )
    return {rid: np.frombuffer(v, dtype=np.float32) for rid, v in rows.all()}


def train_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0, steps: int = 300) -> np.ndarray:
    """Regressão logística com pesos de classe balanceados, por gradiente descendente.

    Inclusões costumam ser raras; o balanceamento evita que o modelo aprenda só a excluir.
    """
    n, d = x.shape
    xb = np.hstack([x, np.ones((n, 1), dtype=np.float32)])
    pos = max(int(y.sum()), 1)
    neg = max(n - pos, 1)
    weights = np.where(y == 1, n / (2 * pos), n / (2 * neg))
    w = np.zeros(d + 1, dtype=np.float64)
    lr = 0.5
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(xb @ w)))
        grad = xb.T @ ((p - y) * weights) / n
        grad[:-1] += l2 * w[:-1] / n
        w -= lr * grad
    return w


def predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.hstack([x, np.ones((x.shape[0], 1), dtype=np.float32)])
    return 1 / (1 + np.exp(-(xb @ w)))


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


async def human_labels(db: AsyncSession, project: Project) -> dict[uuid.UUID, int]:
    """Rótulos para treinar: 1 = incluído ou talvez por algum humano, 0 = excluído por todos."""
    bot = await bot_user(db)
    states = await compute_states(db, project, Phase.title_abstract)
    labels: dict[uuid.UUID, int] = {}
    for rid, st in states.items():
        if st.final is not None:
            labels[rid] = int(st.final.decision == Decision.include)
            continue
        votes = [v for u, v in st.votes.items() if u != bot.id]
        if votes:
            labels[rid] = int(any(v.decision != Decision.exclude for v in votes))
    return labels


async def relevance_scores(
    db: AsyncSession, project: Project, record_ids: list[uuid.UUID]
) -> dict[uuid.UUID, float] | None:
    """Probabilidade de relevância dos registros pedidos, ou None se ainda não dá para treinar."""
    ai = project_ai(project)
    if not ai.enabled or not ai.active_learning:
        return None
    try:
        res = await resolve(db, "embeddings", ai.local_only)
    except client.AIError:
        return None
    labels = await human_labels(db, project)
    if len(set(labels.values())) < 2 or len(labels) < MIN_LABELS:
        return None
    vecs = await load_vectors(db, list(set(labels) | set(record_ids)), res.model_key)
    train = [rid for rid in labels if rid in vecs]
    if len({labels[r] for r in train}) < 2:
        return None
    # O modelo só é treinado de novo quando os rótulos mudam
    key = hashlib.sha256(
        (res.model_key + "".join(f"{r}{labels[r]}" for r in sorted(train))).encode()
    ).hexdigest()
    cached_key, w = _MODELS.get(project.id, ("", None))
    if cached_key != key or w is None:
        x = _normalize(np.stack([vecs[r] for r in train]))
        y = np.array([labels[r] for r in train], dtype=np.float64)
        w = train_logistic(x, y)
        _MODELS[project.id] = (key, w)
    targets = [r for r in record_ids if r in vecs]
    if not targets:
        return None
    probs = predict(w, _normalize(np.stack([vecs[r] for r in targets])))
    return dict(zip(targets, probs.tolist(), strict=True))


async def screening_curve(db: AsyncSession, project: Project) -> dict:
    """Inclusões encontradas ao longo da triagem humana e a sugestão de parada."""
    ai = project_ai(project)
    bot = await bot_user(db)
    states = await compute_states(db, project, Phase.title_abstract)
    events = (
        await db.execute(
            select(DecisionEvent.record_id, DecisionEvent.decision, DecisionEvent.created_at)
            .where(
                DecisionEvent.project_id == project.id,
                DecisionEvent.phase == Phase.title_abstract,
                DecisionEvent.user_id != bot.id,
                DecisionEvent.is_final.is_(False),
                DecisionEvent.decision != UNDO,
            )
            .order_by(DecisionEvent.created_at)
        )
    ).all()
    labels = await human_labels(db, project)
    # Ordem em que cada registro foi visto pela primeira vez por um humano
    seen: list[uuid.UUID] = []
    first: set[uuid.UUID] = set()
    for rid, _, _ in events:
        if rid in states and rid not in first and rid in labels:
            first.add(rid)
            seen.append(rid)
    curve, found, since_last = [], 0, 0
    for rid in seen:
        if labels[rid]:
            found += 1
            since_last = 0
        else:
            since_last += 1
        curve.append(found)
    unseen = [rid for rid, st in states.items() if rid not in labels]
    scores = await relevance_scores(db, project, unseen) if unseen else None
    expected = round(sum(scores.values()), 1) if scores else None
    threshold = ai.stop_after_irrelevant
    should_stop = bool(seen) and since_last >= threshold and (expected is None or expected < 1)
    # Curva reduzida para no máximo 200 pontos
    step = max(1, len(curve) // 200)
    points = [{"screened": i + 1, "found": curve[i]} for i in range(0, len(curve), step)]
    if curve and points[-1]["screened"] != len(curve):
        points.append({"screened": len(curve), "found": curve[-1]})
    return {
        "total": len(states),
        "screened": len(seen),
        "found": found,
        "since_last_include": since_last,
        "expected_remaining": expected,
        "stop_after_irrelevant": threshold,
        "should_stop": should_stop and len(unseen) > 0,
        "prioritized": scores is not None,
        "points": points,
    }


def order_by_scores(ids: list[uuid.UUID], scores: dict[uuid.UUID, float] | None) -> list[uuid.UUID]:
    if not scores:
        return ids
    return sorted(ids, key=lambda r: -scores.get(r, -1.0))
