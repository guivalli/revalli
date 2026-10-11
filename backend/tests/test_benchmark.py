import csv
import random

import numpy as np

from revalli.benchmark import hashing_embed, load_csv, main, simulate, wss

TOPIC = "exercise anxiety adults randomized trial physical activity symptoms".split()
NOISE = (
    "liver rats toxicity protein cell kidney mice dose plasma enzyme gene expression "
    "surgery outcome hospital cohort cancer imaging bone fracture diet children school"
).split()


def _synthetic(path, n=600, relevant=20, seed=1):
    rnd = random.Random(seed)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "abstract", "label_included"])
        for i in range(n):
            rel = i < relevant
            words = rnd.sample(TOPIC, 4) + rnd.sample(NOISE, 3) if rel else rnd.sample(NOISE, 8)
            w.writerow([" ".join(words[:5]), " ".join(rnd.choices(words, k=30)), int(rel)])


def test_active_learning_beats_random_order(tmp_path):
    path = tmp_path / "data.csv"
    _synthetic(path)
    data = load_csv(path)
    x = hashing_embed(data.texts, dim=256)
    sim = simulate(x, data.labels, stop_after=50, seed=0)
    total, rel = len(data.labels), int(data.labels.sum())
    assert sorted(sim.order) == list(range(total))
    assert sim.found[-1] == rel
    # Com tópicos bem separados, quase todo o trabalho é economizado
    assert wss(sim, total, rel) > 0.6
    assert sim.stop_at is not None and sim.recall_at(sim.stop_at, rel) >= 0.95


def test_cli_writes_report(tmp_path):
    path = tmp_path / "tiny.csv"
    _synthetic(path, n=120, relevant=8)
    out = tmp_path / "report.md"
    assert main([str(path), "--runs", "2", "--stop-after", "20", "--out", str(out)]) == 0
    text = out.read_text()
    assert "WSS@95" in text and text.count("\n| ") >= 3


def test_hashing_embed_is_normalized():
    m = hashing_embed(["anxiety anxiety exercise", ""], dim=64)
    assert np.isclose(np.linalg.norm(m[0]), 1.0) and np.linalg.norm(m[1]) == 0
